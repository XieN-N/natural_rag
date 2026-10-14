#!/bin/bash

# ============================================================
# LightRAG на GraphRAG-Bench (medical), фаза индексации.
#
# Движок запускается раннером Ивана из bond005/GraphRAG-Benchmark, а не нашим
# runs/lightrag_run.py: раннер уже отлажен против этого бенчмарка и сам пишет
# predictions_*.json в схеме, которую принимает Evaluation/generation_eval.py.
# Наше здесь только SLURM-обвязка и замер времени.
#
# Запускать голым sbatch, ничего не экспортируя:
#
#   sbatch runs_cluster/graphbench_lightrag.sh
#
# Установка окружения и клонирование форков — GRAPHBENCH_ENGINES.md.
# ============================================================

#SBATCH --job-name=gb_lightrag
#SBATCH --partition=a100
#SBATCH --error="/userspace/sse/natural_rag/logs/%x-%j.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/%x-%j.log"
#SBATCH --open-mode=append
#SBATCH --nodelist=ngpu07

# Токен ЛОКАЛЬНЫХ vLLM-серверов, которые этот же скрипт поднимает ниже.
# Это не секрет: он только авторизует запросы к localhost-эндпоинтам джобы.
VLLM_SERVE_TOKEN="${VLLM_SERVE_TOKEN:-local-vllm-placeholder}"

# ---------------- НАСТРОЙКИ ------------------
SUBSET="${SUBSET:-medical}"
PHASE="${PHASE:-index}"                        # index | query | all
SAMPLE="${SAMPLE:-0}"                          # >0 — смоук на N вопросах

# Индексная модель одна на все три движка — иначе сравнивать нечего.
BIG_LLM_MODEL="${BIG_LLM_MODEL:-/userspace/kms/models/gpt-oss-20b}"
BIG_LLM_NAME="${BIG_LLM_NAME:-gpt-oss-20b}"
BIG_LLM_PORT="${BIG_LLM_PORT:-8000}"

# Эмбеддер у ВСЕХ систем один — так в статье: «All systems use
# bge-large-en-v1.5 for embeddings ... only the graph-construction LLM varies»
# (подпись к таблице 1). Дефолты раннеров тут не годятся: там остатки от авторов
# апстрима, вплоть до чужого домашнего пути к contriever.
EMBED_MODEL="${EMBED_MODEL:-/userspace/sse/models/bge-large-en-v1.5}"
EMBED_SIZE="${EMBED_SIZE:-1024}"

RETRIEVE_TOPK="${RETRIEVE_TOPK:-5}"

ENGINE="lightrag"
conda_env="${CONDA_ENV:-gb_lightrag}"
RUN_ID="${RUN_ID:-graphbench_${SUBSET}_${ENGINE}_${BIG_LLM_NAME}}"
# ---------------------------------------------

set -o pipefail

project_root="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
graphbench_root="${GRAPHBENCH_ROOT:-/userspace/sse/GraphRAG-Benchmark}"
miniconda_dir="/userspace/sse/miniconda3"

# Индекс и результаты движка живут рядом с бенчмарком, а наш замер — в
# generated/, чтобы index_stats.py видел его вместе с остальными прогонами.
BASE_DIR="${BASE_DIR:-/userspace/sse/graphbench_work/${ENGINE}}"
RESULTS_DIR="${RESULTS_DIR:-/userspace/sse/graphbench_results/${ENGINE}}"
TIMING_DIR="${project_root}/generated/${RUN_ID}"

logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
mkdir -p "${logs_dir}" "${cache_root}" "${BASE_DIR}" "${RESULTS_DIR}" "${TIMING_DIR}"

log_file="${logs_dir}/main.log"
BIG_LLM_LOG="${logs_dir}/vllm_llm.log"

# Недостроенный индекс перезапуск не чинит: проверка *_index_exists видит
# каталог и считает работу сделанной. FRESH=1 сносит индекс движка перед стартом.
if [ "${FRESH:-0}" = "1" ]; then
    echo "=== FRESH=1: удаляю индекс ${BASE_DIR} ===" | tee -a "${log_file}"
    rm -rf "${BASE_DIR:?}"
    mkdir -p "${BASE_DIR}"
fi

echo "=== Job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}  engine=${ENGINE} phase=${PHASE} subset=${SUBSET}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

wait_for_vllm() {
    echo "=== Waiting for vLLM ===" | tee -a "${log_file}"
    local waited=0
    while ! grep -q "Starting vLLM API server" "${BIG_LLM_LOG}" 2>/dev/null; do
        if ! kill -0 "${LLM_PID}" 2>/dev/null; then
            echo "ERROR: vLLM умер на старте, см. ${BIG_LLM_LOG}" | tee -a "${log_file}"
            exit 1
        fi
        sleep 5
        waited=$((waited + 5))
        if [ ${waited} -gt 3600 ]; then
            echo "ERROR: vLLM не поднялся за час, см. ${BIG_LLM_LOG}" | tee -a "${log_file}"
            exit 1
        fi
    done
    echo "=== vLLM started ===" | tee -a "${log_file}"
}

cleanup() {
    echo "=== Cleanup ===" | tee -a "${log_file}"
    [ -n "${LLM_PID}" ] && kill "${LLM_PID}" 2>/dev/null
    wait 2>/dev/null
}
trap cleanup EXIT

echo "=== Killing leftover vllm processes ===" | tee -a "${log_file}"
pkill -u "$(whoami)" -f vllm 2>/dev/null || true
pkill -u "$(whoami)" -f "EngineCore" 2>/dev/null || true
sleep 10
nvidia-smi >> "${log_file}"

export HOME="/userspace/sse"
export PIP_CACHE_DIR="${cache_root}/pip"
export HF_HOME="${cache_root}/huggingface"
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export DO_NOT_TRACK=1
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_CACHE_ROOT="${cache_root}/vllm_cache"
export TORCH_HOME="${cache_root}/torch_cache"
export XDG_CACHE_HOME="${cache_root}/xdg_cache"
export TRITON_CACHE_DIR="${cache_root}/triton_cache"
mkdir -p "${VLLM_CACHE_ROOT}" "${TORCH_HOME}" "${XDG_CACHE_HOME}" "${TRITON_CACHE_DIR}" "${PIP_CACHE_DIR}"

# LightRAG на импорте прогоняет pipmaster, и тот пытается ОБНОВИТЬ пакеты
# (в логе — «Updating package: ollama»). Интернета на ноде нет, поэтому pip
# молча висит на ретраях и съедает минуты до старта. Тремя переменными сводим
# эту попытку к мгновенному отказу; сами мы в job'е ничего не ставим, так что
# PIP_NO_INDEX ничему не мешает. Пакет ollama должен стоять заранее — см.
# GRAPHBENCH_ENGINES.md.
export PIP_NO_INDEX=1
export PIP_RETRIES=0
export PIP_TIMEOUT=5
export PIP_DISABLE_PIP_VERSION_CHECK=1

if [ ! -d "${EMBED_MODEL}" ]; then
    echo "ERROR: нет эмбеддера ${EMBED_MODEL} — скачайте его на login-ноде" | tee -a "${log_file}"
    exit 1
fi
if [ ! -f "${graphbench_root}/Examples/run_lightrag.py" ]; then
    echo "ERROR: нет ${graphbench_root}/Examples/run_lightrag.py" | tee -a "${log_file}"
    echo "Клонируйте bond005/GraphRAG-Benchmark, см. GRAPHBENCH_ENGINES.md" | tee -a "${log_file}"
    exit 1
fi

# ---------- vLLM ----------
echo "=== Starting vLLM (${BIG_LLM_NAME}) on port ${BIG_LLM_PORT} ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=0 vllm serve "${BIG_LLM_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key "${VLLM_SERVE_TOKEN}" \
    --gpu-memory-utilization 0.80 \
    --max-model-len 32768 \
    --served-model-name "${BIG_LLM_NAME}" \
    --port "${BIG_LLM_PORT}" \
    --tensor-parallel-size 1 \
    --trust_remote_code \
    > "${BIG_LLM_LOG}" 2>&1 &
LLM_PID=$!
wait_for_vllm

export LLM_API_KEY="${VLLM_SERVE_TOKEN}"
export OPENAI_API_KEY="${VLLM_SERVE_TOKEN}"

# ---------- Индексация ----------
# Раннеры читают ./Datasets/... относительными путями, поэтому только из корня
# репозитория бенчмарка.
cd "${graphbench_root}" || exit 1

RUN_ARGS=(
    --subset "${SUBSET}"
    --phase "${PHASE}"
    --base_dir "${BASE_DIR}"
    --results_dir "${RESULTS_DIR}"
    --model_name "${BIG_LLM_NAME}"
    --llm_base_url "http://localhost:${BIG_LLM_PORT}/v1"
    --embed_model "${EMBED_MODEL}"
    --embed_size "${EMBED_SIZE}"
    --retrieve_topk "${RETRIEVE_TOPK}"
    --mode API
)
[ "${SAMPLE}" != "0" ] && RUN_ARGS+=(--sample "${SAMPLE}")

echo "=== Starting LightRAG (${PHASE}) ===" | tee -a "${log_file}"
python "${project_root}/runs_cluster/time_phase.py" \
    --out-dir "${TIMING_DIR}" \
    --engine "${ENGINE}" \
    --dataset "graphrag_bench_${SUBSET}" \
    --model "${BIG_LLM_NAME}" \
    --corpus "${graphbench_root}/Datasets/Corpus/${SUBSET}.parquet" \
    --note "subset=${SUBSET}" \
    --note "harness=Examples/run_lightrag.py" \
    -- python Examples/run_lightrag.py "${RUN_ARGS[@]}" >> "${log_file}" 2>&1
status=$?
echo "=== LightRAG finished (exit ${status}) ===" | tee -a "${log_file}"

python "${project_root}/runs/index_stats.py" "${TIMING_DIR}" >> "${log_file}" 2>&1 || true

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit ${status}
