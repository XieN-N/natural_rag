#!/bin/bash

# ============================================================
# RAGU на GraphRAG-Bench (medical), фаза индексации.
#
# Движок запускается раннером Ивана из bond005/GraphRAG-Benchmark, а не нашим
# runs/ragu_run.py: раннер уже отлажен против этого бенчмарка и сам пишет
# predictions_*.json в схеме, которую принимает Evaluation/generation_eval.py.
# Наше здесь только SLURM-обвязка и замер времени.
#
# Запускать голым sbatch, ничего не экспортируя:
#
#   sbatch runs_cluster/graphbench_ragu.sh
#
# Установка окружения и клонирование форков — GRAPHBENCH_ENGINES.md.
# ============================================================

#SBATCH --job-name=gb_ragu
#SBATCH --partition=a100
#SBATCH --error="/userspace/sse/natural_rag/logs/%x-%j.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/%x-%j.log"
#SBATCH --open-mode=append
#SBATCH --nodelist=ngpu05

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
#
# ВАЖНО, чем RAGU отличается от двух других: у него эмбеддер не локальная
# модель, а КЛИЕНТ OpenAI-совместимого API (EmbedderOpenAI поверх
# CachedAsyncOpenAI). --embed_model для него — имя модели в запросе, а не путь
# на диске, и при пустом --embed_base_url он ходит на llm_base_url, то есть в
# генеративный сервер, где эмбеддингов нет: «No embedding data received».
# Поэтому эмбеддер поднимается вторым vLLM, ровно как в run_universal_ragu.sh.
EMBED_MODEL="${EMBED_MODEL:-/userspace/sse/models/bge-large-en-v1.5}"
EMBED_MODEL_NAME="${EMBED_MODEL_NAME:-bge-large-en-v1.5}"
EMBED_SIZE="${EMBED_SIZE:-1024}"
EMBED_PORT="${EMBED_PORT:-8002}"

# У bge окно 512 токенов, и сервер отвечает 400 на всё, что длиннее. Без явного
# лимита RAGU шлёт тексты как есть, ICL-примеры в 2121 токен улетают в отказ, а
# вслед за ними падает извлечение сущностей по ВСЕМ чанкам — граф выходит
# пустой. 500 вместо 512 — запас на [CLS]/[SEP]. Токенизатор берём локальный, с
# самой модели: на ноде TRANSFORMERS_OFFLINE=1, скачать tiktoken неоткуда.
EMBED_TOKEN_LIMIT="${EMBED_TOKEN_LIMIT:-500}"

# Две модели на одной карте: генеративной 0.65, эмбеддеру 0.20. Те же доли, что
# в run_universal_ragu.sh для одногопушного случая.
LLM_MEM_UTIL="${LLM_MEM_UTIL:-0.65}"
EMBED_MEM_UTIL="${EMBED_MEM_UTIL:-0.20}"
LLM_GPUS="${LLM_GPUS:-0}"
EMBED_GPUS="${EMBED_GPUS:-0}"

# ICL задан статьёй, и дефолт раннера ему НЕ соответствует. Подпись к таблице 1:
# «RAGU rows use ICL=1 and Val=yes». У run_ragu.py --icl_enabled по умолчанию
# False, а --icl_num_examples равно 2 — то есть без этих двух строк получилась бы
# строка из абляции (ICL=0), а не заголовочная. Не «чинить» обратно на дефолт.
# Val=yes — это и есть дефолт, поэтому --noval не передаём.
ICL_NUM_EXAMPLES="${ICL_NUM_EXAMPLES:-1}"

# Движок поиска — local, как во всех остальных прогонах сравнения. Дефолт
# раннера здесь mix, но брать его нельзя: движок поиска должен быть один и тот
# же везде, иначе строки таблицы меряют разные вещи. Выбор у run_ragu.py:
# local | global | mix (query_plan из нашего runs/ragu_run.py тут недоступен).
SEARCH_ENGINE="${SEARCH_ENGINE:-local}"

# А про top-k статья молчит; остаётся дефолт раннера, одинаковый у всех трёх.
# См. «Что сверено со статьёй» в GRAPHBENCH_ENGINES.md.
RETRIEVE_TOPK="${RETRIEVE_TOPK:-5}"

ENGINE="ragu"
conda_env="${CONDA_ENV:-gb_ragu}"
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
EMBED_LOG="${logs_dir}/vllm_embed.log"

# Неудачная индексация оставляет отравленный каталог: чанки в vdb_chunk.json уже
# лежат, граф пустой, и следующий запуск видит «3053/3053 duplicated chunks by
# id ... Using 0 unique chunks» и «Nothing to build». Само это не рассосётся —
# resume считает работу сделанной. FRESH=1 сносит индекс движка перед стартом.
if [ "${FRESH:-0}" = "1" ]; then
    echo "=== FRESH=1: удаляю индекс ${BASE_DIR} ===" | tee -a "${log_file}"
    rm -rf "${BASE_DIR:?}"
    mkdir -p "${BASE_DIR}"
fi

echo "=== Job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}  engine=${ENGINE} phase=${PHASE} subset=${SUBSET}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

# Два сервера, поэтому лог и pid — аргументы, а не глобальные переменные.
wait_for_vllm() {
    local log_path="$1" name="$2" pid="$3"
    echo "=== Waiting for vLLM (${name}) ===" | tee -a "${log_file}"
    local waited=0
    while ! grep -q "Starting vLLM API server" "${log_path}" 2>/dev/null; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            echo "ERROR: vLLM (${name}) умер на старте, см. ${log_path}" | tee -a "${log_file}"
            exit 1
        fi
        sleep 5
        waited=$((waited + 5))
        if [ ${waited} -gt 3600 ]; then
            echo "ERROR: vLLM (${name}) не поднялся за час, см. ${log_path}" | tee -a "${log_file}"
            exit 1
        fi
    done
    echo "=== vLLM (${name}) started ===" | tee -a "${log_file}"
}

cleanup() {
    echo "=== Cleanup ===" | tee -a "${log_file}"
    [ -n "${LLM_PID}" ] && kill "${LLM_PID}" 2>/dev/null
    [ -n "${EMBED_PID}" ] && kill "${EMBED_PID}" 2>/dev/null
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

if [ ! -d "${EMBED_MODEL}" ]; then
    echo "ERROR: нет эмбеддера ${EMBED_MODEL} — скачайте его на login-ноде" | tee -a "${log_file}"
    exit 1
fi
if [ ! -f "${graphbench_root}/Examples/run_ragu.py" ]; then
    echo "ERROR: нет ${graphbench_root}/Examples/run_ragu.py" | tee -a "${log_file}"
    echo "Клонируйте bond005/GraphRAG-Benchmark, см. GRAPHBENCH_ENGINES.md" | tee -a "${log_file}"
    exit 1
fi

# ---------- vLLM: генеративная модель ----------
echo "=== Starting vLLM (${BIG_LLM_NAME}) on port ${BIG_LLM_PORT} ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=${LLM_GPUS} vllm serve "${BIG_LLM_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key "${VLLM_SERVE_TOKEN}" \
    --gpu-memory-utilization ${LLM_MEM_UTIL} \
    --max-model-len 32768 \
    --served-model-name "${BIG_LLM_NAME}" \
    --port "${BIG_LLM_PORT}" \
    --tensor-parallel-size 1 \
    --trust_remote_code \
    > "${BIG_LLM_LOG}" 2>&1 &
LLM_PID=$!
wait_for_vllm "${BIG_LLM_LOG}" "LLM" "${LLM_PID}"

# ---------- vLLM: эмбеддер ----------
# bge-large-en-v1.5 — это BertModel, у него нет генеративной головы, и vLLM сам
# поднимает его в режиме пулинга. Отдельный флаг задачи не нужен: так же, без
# него, эмбеддер поднимается в run_universal_ragu.sh.
echo "=== Starting vLLM embeddings (${EMBED_MODEL_NAME}) on port ${EMBED_PORT} ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=${EMBED_GPUS} vllm serve "${EMBED_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key "${VLLM_SERVE_TOKEN}" \
    --gpu-memory-utilization ${EMBED_MEM_UTIL} \
    --served-model-name "${EMBED_MODEL_NAME}" \
    --port "${EMBED_PORT}" \
    --trust_remote_code \
    > "${EMBED_LOG}" 2>&1 &
EMBED_PID=$!
wait_for_vllm "${EMBED_LOG}" "Embedder" "${EMBED_PID}"

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
    --embed_model "${EMBED_MODEL_NAME}"
    --embed_base_url "http://localhost:${EMBED_PORT}/v1"
    --embed_size "${EMBED_SIZE}"
    --embedder_token_limit "${EMBED_TOKEN_LIMIT}"
    --tokenizer_embedder_backend local
    --tokenizer_embedder_name "${EMBED_MODEL}"
    --retrieve_topk "${RETRIEVE_TOPK}"
    --search_engine "${SEARCH_ENGINE}"
    --icl_enabled
    --icl_num_examples "${ICL_NUM_EXAMPLES}"
)
[ "${SAMPLE}" != "0" ] && RUN_ARGS+=(--sample "${SAMPLE}")

echo "=== Starting RAGU (${PHASE}) ===" | tee -a "${log_file}"
python "${project_root}/runs_cluster/time_phase.py" \
    --out-dir "${TIMING_DIR}" \
    --engine "${ENGINE}" \
    --dataset "graphrag_bench_${SUBSET}" \
    --model "${BIG_LLM_NAME}" \
    --corpus "${graphbench_root}/Datasets/Corpus/${SUBSET}.parquet" \
    --note "subset=${SUBSET}" \
    --note "harness=Examples/run_ragu.py" \
    -- python Examples/run_ragu.py "${RUN_ARGS[@]}" >> "${log_file}" 2>&1
status=$?
echo "=== RAGU finished (exit ${status}) ===" | tee -a "${log_file}"

python "${project_root}/runs/index_stats.py" "${TIMING_DIR}" >> "${log_file}" 2>&1 || true

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit ${status}
