#!/bin/bash

# ============================================================
# Универсальный sbatch-скрипт для RAG-экспериментов с LightRAG /
# FastGraphRAG на кластере: vLLM-серверы (LLM + эмбеддер), индексация,
# генерация ответов, конвертация в JSON и оценка LLM-судьёй.
# Все пути (логи, кэш, ответы) изолированы через RUN_ID.
#
# Заменяет бывшие ~30 копий runs_universal/run_*.sh, отличавшихся
# только блоком переменных. Любую настройку можно переопределить из
# окружения, не трогая файл:
#
#   sbatch --export=ALL,RAG_ENGINE=lightrag,DATASET_NAME=chegeka \
#       runs_cluster/run_universal.sh
#
# (SLURM по умолчанию пробрасывает окружение: --export=ALL.)
# Готовые комбинации «датасет × движок × модель» — таблицей примеров
# в runs_cluster/README.md.
#
# Вызывает канонические раннеры из runs/ (lightrag_run.py,
# fast_graphrag_run.py, convert_answers.py, jsonl_llm_judge_evaluate.py).
# ============================================================

#SBATCH --job-name=rag_universal
#SBATCH --partition=a100
#SBATCH --error="logs/%x-%j.err"
#SBATCH --output="logs/%x-%j.log"
#SBATCH --open-mode=append

# ---------------- НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ ИЛИ ЧЕРЕЗ ОКРУЖЕНИЕ) -------
RAG_ENGINE="${RAG_ENGINE:-fast_graphrag}"   # lightrag | fast_graphrag
DATASET_NAME="${DATASET_NAME:-multiq}"      # папка в datasets/

# Модели (пути на кластере + имена, под которыми их отдаёт vLLM)
BIG_LLM_MODEL="${BIG_LLM_MODEL:-/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct}"
EMBED_MODEL="${EMBED_MODEL:-/userspace/kms/models/gte-multilingual-base}"
JUDGE_MODEL="${JUDGE_MODEL:-/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct}"

BIG_LLM_NAME="${BIG_LLM_NAME:-Qwen2.5-14B-Instruct}"
EMBED_MODEL_NAME="${EMBED_MODEL_NAME:-gte-multilingual-base}"
JUDGE_MODEL_NAME="${JUDGE_MODEL_NAME:-Qwen2.5-14B-Instruct}"

EMBEDDING_DIM="${EMBEDDING_DIM:-768}"

# Порты
BIG_LLM_PORT="${BIG_LLM_PORT:-8000}"
EMBED_PORT="${EMBED_PORT:-8002}"
JUDGE_PORT="${JUDGE_PORT:-8200}"

# Токен ЛОКАЛЬНЫХ vLLM-серверов, которые этот же скрипт поднимает ниже.
# Это не секрет: он только авторизует запросы к localhost-эндпоинтам джобы.
VLLM_SERVE_TOKEN="${VLLM_SERVE_TOKEN:-local-vllm-placeholder}"

# ===================== КОНФИГУРАЦИЯ GPU =====================
NUM_GPUS="${NUM_GPUS:-1}"   # количество GPU на ноде (1,2,8,10...)

if [ "${NUM_GPUS}" -ge 10 ]; then
    LLM_GPUS=0,1,2,3,4,5,6,7
    EMBED_GPUS=8,9
    LLM_TENSOR_PARALLEL=8
    LLM_MEM_UTIL_D=0.85
    EMBED_MEM_UTIL_D=0.9
elif [ "${NUM_GPUS}" -ge 2 ]; then
    LLM_GPUS=0
    EMBED_GPUS=1
    LLM_TENSOR_PARALLEL=1
    LLM_MEM_UTIL_D=0.65
    EMBED_MEM_UTIL_D=0.2
else
    LLM_GPUS=0
    EMBED_GPUS=0
    LLM_TENSOR_PARALLEL=1
    LLM_MEM_UTIL_D=0.65
    EMBED_MEM_UTIL_D=0.2
fi
# Env переопределяет выбранную ветку: например, для 14B bf16 на 40ГБ-узле
# 0.65 не хватает (веса ~28ГБ, KV-кэш уходит в минус) — ставьте 0.85+.
LLM_MEM_UTIL="${LLM_MEM_UTIL:-$LLM_MEM_UTIL_D}"
EMBED_MEM_UTIL="${EMBED_MEM_UTIL:-$EMBED_MEM_UTIL_D}"
JUDGE_GPUS=0

# Идентификатор запуска
RUN_ID="${RUN_ID:-${RAG_ENGINE}_${DATASET_NAME}_${BIG_LLM_NAME}}"
# --------------------------------------------------------------

PROJECT_ROOT="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
project_root="${PROJECT_ROOT}"
miniconda_dir="/userspace/sse/miniconda3"

# Окружение для индексации и генерации (conda-env на движок)
conda_env="${RAG_ENGINE}"
# Окружение для оценки (судья не зависит от движка)
eval_conda_env="lightrag"

# Уникальные папки для логов и кэша
logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
eval_cache_dir="${cache_root}/eval"

mkdir -p "${project_root}/logs" "${logs_dir}" "${cache_root}" "${eval_cache_dir}"

log_file="${logs_dir}/main.log"
BIG_LLM_LOG="${logs_dir}/vllm_llm.log"
EMBED_LOG="${logs_dir}/vllm_embed.log"
JUDGE_LOG="${logs_dir}/vllm_judge.log"

echo "=== Job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}" | tee -a "${log_file}"
echo "GPU config: NUM_GPUS=${NUM_GPUS}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

# Функция ожидания vLLM. Таймаут обязателен: без него умерший при старте
# сервер (например, OOM) оставляет джобу навсегда в "Waiting for ...".
wait_for_vllm() {
    local log_path="$1"
    local name="$2"
    local pid="${3:-}"
    local waited=0
    local timeout="${VLLM_WAIT_TIMEOUT:-2700}"   # 45 минут по умолчанию
    echo "=== Waiting for ${name} to start ===" | tee -a "${log_file}"
    while ! grep -q "Starting vLLM API server" "${log_path}" 2>/dev/null; do
        if [ -n "${pid}" ] && ! kill -0 "${pid}" 2>/dev/null; then
            echo "=== ${name} process died before starting — see ${log_path} ===" | tee -a "${log_file}"
            return 1
        fi
        if [ "${waited}" -ge "${timeout}" ]; then
            echo "=== TIMEOUT (${timeout}s) waiting for ${name} — see ${log_path} ===" | tee -a "${log_file}"
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done
    echo "=== ${name} started ===" | tee -a "${log_file}"
    return 0
}

cleanup() {
    kill %1 %2 2>/dev/null || true
    [ -n "${JUDGE_PID}" ] && kill "${JUDGE_PID}" 2>/dev/null || true
    wait 2>/dev/null
}
trap cleanup EXIT

# Очистка процессов
echo "=== Killing leftover vllm/torch processes ===" | tee -a "${log_file}"
pkill -u "$(whoami)" -f vllm 2>/dev/null || true
pkill -u "$(whoami)" -f "EngineCore" 2>/dev/null || true
sleep 10
nvidia-smi >> "${log_file}"

# Переменные окружения для кэша
export HOME="/userspace/sse"
export PIP_CACHE_DIR="${cache_root}/pip"
export HF_HOME="${cache_root}/huggingface"
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export DO_NOT_TRACK=1

export VLLM_CACHE_DIR="${cache_root}/vllm_cache"
export TORCH_HOME="${cache_root}/torch_cache"
export XDG_CACHE_HOME="${cache_root}/xdg_cache"
export TRITON_CACHE_DIR="${cache_root}/triton_cache"
export FLASHINFER_WORKSPACE_DIR="${cache_root}/flashinfer_workspace"
mkdir -p "${FLASHINFER_WORKSPACE_DIR}" "${VLLM_CACHE_DIR}" "${TORCH_HOME}" "${XDG_CACHE_HOME}" "${TRITON_CACHE_DIR}" "${PIP_CACHE_DIR}"

# Канонические раннеры раскладывают вывод как
#   <OUTPUT_DIR>/<датасет>/{index,answers}  (natural_rag.paths.resolve_run_dirs)
export OUTPUT_DIR="${project_root}/generated/${RUN_ID}"

# ---------- ЭТАП 1: Запуск LLM и эмбеддера ----------
echo "=== Starting vLLM for LLM (${BIG_LLM_NAME}) ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=${LLM_GPUS} vllm serve "${BIG_LLM_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key "${VLLM_SERVE_TOKEN}" \
    --gpu-memory-utilization ${LLM_MEM_UTIL} \
    --max-model-len 32768 \
    --served-model-name "${BIG_LLM_NAME}" \
    --port "${BIG_LLM_PORT}" \
    --tensor-parallel-size ${LLM_TENSOR_PARALLEL} \
    > "${BIG_LLM_LOG}" 2>&1 &

wait_for_vllm "${BIG_LLM_LOG}" "LLM" "$!" || exit 1

echo "=== Starting vLLM for embeddings (${EMBED_MODEL_NAME}) ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=${EMBED_GPUS} vllm serve "${EMBED_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key "${VLLM_SERVE_TOKEN}" \
    --gpu-memory-utilization ${EMBED_MEM_UTIL} \
    --served-model-name "${EMBED_MODEL_NAME}" \
    --port "${EMBED_PORT}" \
    --hf-overrides '{"architectures": ["GteNewModel"]}' \
    --trust_remote_code \
    > "${EMBED_LOG}" 2>&1 &

wait_for_vllm "${EMBED_LOG}" "Embedder" "$!" || exit 1

# Экспорт переменных для канонических python-раннеров из runs/
export OPENAI_BASE_URL="http://localhost:${BIG_LLM_PORT}/v1"
export EMBED_BASE_URL="http://localhost:${EMBED_PORT}/v1"
export OPENAI_API_KEY="${VLLM_SERVE_TOKEN}"
export LLM_MODEL="${BIG_LLM_NAME}"
export EMBED_MODEL="${EMBED_MODEL_NAME}"
export EMBEDDING_DIM="${EMBEDDING_DIM}"
export CONCURRENT_TASK_LIMIT=128

export DATASET_PATH="${project_root}/datasets/${DATASET_NAME}"

# ---------- ЭТАП 2: Индексация и генерация ответов ----------
echo "=== Starting RAG pipeline (${RAG_ENGINE}) ===" | tee -a "${log_file}"
cd "${project_root}" || exit 1

if [ "${RAG_ENGINE}" = "fast_graphrag" ]; then
    python runs/fast_graphrag_run.py >> "${log_file}" 2>&1
else
    python runs/lightrag_run.py >> "${log_file}" 2>&1
fi
echo "=== RAG pipeline finished ===" | tee -a "${log_file}"

ANSWERS_DIR="${OUTPUT_DIR}/${DATASET_NAME}/answers"

# ---------- ЭТАП 3: Конвертация ответов в JSON ----------
echo "=== Converting answers to JSON ===" | tee -a "${log_file}"
python runs/convert_answers.py \
    --dataset-name "${DATASET_NAME}" \
    --answers-dir "${ANSWERS_DIR}" >> "${log_file}" 2>&1
echo "Convert exit: $?" | tee -a "${log_file}"

# ---------- ЭТАП 4: Остановка LLM и эмбеддера ----------
echo "=== Stopping LLM and Embedder ===" | tee -a "${log_file}"
kill %1 %2 2>/dev/null || true
wait 2>/dev/null
sleep 5

# ========== ПЕРЕКЛЮЧЕНИЕ НА lightrag ДЛЯ ОЦЕНКИ ==========
echo "=== Switching to '${eval_conda_env}' environment for evaluation ===" | tee -a "${log_file}"
conda deactivate 2>/dev/null
conda activate "/userspace/sse/.conda/envs/${eval_conda_env}"

# ---------- ЭТАП 5: Запуск судьи и оценка ----------
echo "=== Starting vLLM judge server (${JUDGE_MODEL_NAME}) ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=${JUDGE_GPUS} vllm serve "${JUDGE_MODEL}" \
    --download-dir "${eval_cache_dir}" \
    --api-key "${VLLM_SERVE_TOKEN}" \
    --gpu-memory-utilization 0.8 \
    --max-model-len 8192 \
    --served-model-name "${JUDGE_MODEL_NAME}" \
    --port "${JUDGE_PORT}" \
    > "${JUDGE_LOG}" 2>&1 &

JUDGE_PID=$!

wait_for_vllm "${JUDGE_LOG}" "Judge" "${JUDGE_PID}" || exit 1

echo "=== Starting evaluation ===" | tee -a "${log_file}"
OPENAI_BASE_URL="http://localhost:${JUDGE_PORT}/v1" \
OPENAI_API_KEY="${VLLM_SERVE_TOKEN}" \
python runs/jsonl_llm_judge_evaluate.py \
    --dataset-name "${DATASET_NAME}" \
    --answers-dir "${ANSWERS_DIR}" \
    --judge-model "${JUDGE_MODEL_NAME}" >> "${log_file}" 2>&1
judge_status=$?
echo "=== Evaluation finished (exit ${judge_status}) ===" | tee -a "${log_file}"

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit "${judge_status}"
