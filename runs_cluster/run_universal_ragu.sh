#!/bin/bash

# ============================================================
# Универсальный скрипт для RAGU: индексация + генерация ответов.
# Поднимает два vLLM: LLM и эмбеддер. Замер скорости индексации
# пишется в generated/.../index_summary.json тем же IndexTimer,
# что и у Wikontic — числа сравнимы напрямую.
# ============================================================

#SBATCH --job-name=ragu
#SBATCH --partition=a800
#SBATCH --error="/userspace/sse/natural_rag/logs/ragu.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/ragu.log"
#SBATCH --open-mode=append

# Токен ЛОКАЛЬНЫХ vLLM-серверов, которые этот же скрипт поднимает ниже.
# Это не секрет: он только авторизует запросы к localhost-эндпоинтам джобы.
VLLM_SERVE_TOKEN="${VLLM_SERVE_TOKEN:-local-vllm-placeholder}"

# ---------------- НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ------------------
# Любую переменную можно переопределить из окружения при запуске, не трогая файл:
#   DATASET_NAME=bioasq SHORT_ANSWERS=1 sbatch runs_cluster/run_universal_ragu.sh
# Готовые наборы запусков — в runs_cluster/launch_*.sh.

DATASET_NAME="${DATASET_NAME:-musique}"        # папка в datasets/
DATASET_PATH="${DATASET_PATH:-}"               # пусто -> datasets/${DATASET_NAME}

# Модели
BIG_LLM_MODEL="${BIG_LLM_MODEL:-/userspace/kms/models/gigachat-3.1-lightning}"
BIG_LLM_NAME="${BIG_LLM_NAME:-gigachat-3.1-lightning}"
EMBED_MODEL="${EMBED_MODEL:-/userspace/kms/models/gte-multilingual-base}"
EMBED_MODEL_NAME="${EMBED_MODEL_NAME:-gte-multilingual-base}"
EMBEDDING_DIM="${EMBEDDING_DIM:-768}"
# Для gte-multilingual-base нужен hf-override; для других эмбеддеров передайте
# EMBED_HF_OVERRIDES="" — пустое значение сохраняется и флаг не добавляется.
# Значение содержит фигурные скобки, поэтому дефолт задаётся явным if, а не
# ${VAR-default}: там первая же } закрыла бы подстановку.
if [ -z "${EMBED_HF_OVERRIDES+set}" ]; then
    EMBED_HF_OVERRIDES='{"architectures": ["GteNewModel"]}'
fi

BIG_LLM_PORT="${BIG_LLM_PORT:-8000}"
EMBED_PORT="${EMBED_PORT:-8002}"

# RAGU
QUERY_ENGINE="${QUERY_ENGINE:-query_plan}"     # local | query_plan | naive
CHUNKER="${CHUNKER:-simple}"
SHORT_ANSWERS="${SHORT_ANSWERS:-0}"            # 1 для коротких ответов (musique/bioasq)
EMBED_BATCH_SIZE="${EMBED_BATCH_SIZE:-32}"

# Этапы
DO_INDEX="${DO_INDEX:-1}"
DO_ANSWER="${DO_ANSWER:-1}"
# Смоук-режим: проиндексировать/ответить только первые N (0 = без ограничения)
LIMIT_DOCS="${LIMIT_DOCS:-0}"
LIMIT_QUESTIONS="${LIMIT_QUESTIONS:-0}"

# ===================== КОНФИГУРАЦИЯ GPU =====================
NUM_GPUS="${NUM_GPUS:-1}"

if [ ${NUM_GPUS} -ge 10 ]; then
    LLM_GPUS=0,1,2,3,4,5,6,7
    EMBED_GPUS=8,9
    LLM_TENSOR_PARALLEL=8
    LLM_MEM_UTIL=0.85
    EMBED_MEM_UTIL=0.9
elif [ ${NUM_GPUS} -ge 2 ]; then
    LLM_GPUS=0
    EMBED_GPUS=1
    LLM_TENSOR_PARALLEL=1
    LLM_MEM_UTIL=0.65
    EMBED_MEM_UTIL=0.2
else
    LLM_GPUS=0
    EMBED_GPUS=0
    LLM_TENSOR_PARALLEL=1
    LLM_MEM_UTIL=0.65
    EMBED_MEM_UTIL=0.2
fi

RUN_ID="${RUN_ID:-ragu_${DATASET_NAME}_${BIG_LLM_NAME}}"
# --------------------------------------------------------------

set -o pipefail

project_root="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
miniconda_dir="/userspace/sse/miniconda3"
conda_env="${CONDA_ENV:-ragu}"   # ragu | ragu_dev — как называется conda-env с нужной версией RAGU

if [ -z "${DATASET_PATH}" ]; then
    DATASET_PATH="${project_root}/datasets/${DATASET_NAME}"
fi

logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
mkdir -p "${logs_dir}" "${cache_root}"

log_file="${logs_dir}/main.log"
BIG_LLM_LOG="${logs_dir}/vllm_llm.log"
EMBED_LOG="${logs_dir}/vllm_embed.log"

echo "=== Job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

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
    echo "=== Cleanup ===" | tee -a "${log_file}"
    [ -n "${LLM_PID}" ]   && kill "${LLM_PID}"   2>/dev/null
    [ -n "${EMBED_PID}" ] && kill "${EMBED_PID}" 2>/dev/null
    wait 2>/dev/null
}
trap cleanup EXIT

echo "=== Killing leftover vllm/torch processes ===" | tee -a "${log_file}"
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
# FlashInfer собирает CUDA-ядра JIT'ом системным nvcc, а на нодах CUDA 11 —
# у vLLM есть родной torch-сэмплер, он и нужен.
export VLLM_USE_FLASHINFER_SAMPLER=0

export VLLM_CACHE_ROOT="${cache_root}/vllm_cache"
export TORCH_HOME="${cache_root}/torch_cache"
export XDG_CACHE_HOME="${cache_root}/xdg_cache"
export TRITON_CACHE_DIR="${cache_root}/triton_cache"
export FLASHINFER_WORKSPACE_DIR="${cache_root}/flashinfer_workspace"
mkdir -p "${FLASHINFER_WORKSPACE_DIR}" "${VLLM_CACHE_ROOT}" "${TORCH_HOME}" "${XDG_CACHE_HOME}" "${TRITON_CACHE_DIR}" "${PIP_CACHE_DIR}"

# Переопределяемо: например, чтобы разведти выводы разных версий RAGU
# (0.0.3 vs dev) по разным каталогам при одном датасете.
OUTPUT_DIR="${OUTPUT_DIR:-${project_root}/generated/ragu_${DATASET_NAME}}"

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
LLM_PID=$!
wait_for_vllm "${BIG_LLM_LOG}" "LLM" "$!" || exit 1

echo "=== Starting vLLM for embeddings (${EMBED_MODEL_NAME}) ===" | tee -a "${log_file}"
EMBED_EXTRA=()
[ -n "${EMBED_HF_OVERRIDES}" ] && EMBED_EXTRA+=(--hf-overrides "${EMBED_HF_OVERRIDES}")
CUDA_VISIBLE_DEVICES=${EMBED_GPUS} vllm serve "${EMBED_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key "${VLLM_SERVE_TOKEN}" \
    --gpu-memory-utilization ${EMBED_MEM_UTIL} \
    --served-model-name "${EMBED_MODEL_NAME}" \
    --port "${EMBED_PORT}" \
    "${EMBED_EXTRA[@]}" \
    --trust_remote_code \
    > "${EMBED_LOG}" 2>&1 &
EMBED_PID=$!
wait_for_vllm "${EMBED_LOG}" "Embedder" "$!" || exit 1

export OPENAI_BASE_URL="http://localhost:${BIG_LLM_PORT}/v1"
export EMBED_BASE_URL="http://localhost:${EMBED_PORT}/v1"
export OPENAI_API_KEY="${VLLM_SERVE_TOKEN}"
export LLM_MODEL="${BIG_LLM_NAME}"
export EMBED_MODEL="${EMBED_MODEL_NAME}"
export EMBEDDING_DIM="${EMBEDDING_DIM}"

# ---------- ЭТАП 2: Индексация и ответы ----------
cd "${project_root}" || exit 1

RUN_ARGS=(
    --dataset-path "${DATASET_PATH}"
    --output-dir "${OUTPUT_DIR}"
    --index-model "${BIG_LLM_NAME}"
    --builder-model-name "${BIG_LLM_NAME}"
    --assistant-model-name "${BIG_LLM_NAME}"
    --embedding-model-name "${EMBED_MODEL_NAME}"
    --embedding-dim "${EMBEDDING_DIM}"
    --embed-batch-size "${EMBED_BATCH_SIZE}"
    --query-engine "${QUERY_ENGINE}"
    --chunker "${CHUNKER}"
    --llm-cache "${cache_root}/llm_cache"
    --llm-debug-cache "${cache_root}/llm_debug_cache"
)
[ "${DO_INDEX}"  = "1" ] && RUN_ARGS+=(--build-index) || RUN_ARGS+=(--no-build-index)
[ "${DO_ANSWER}" = "1" ] && RUN_ARGS+=(--answer)      || RUN_ARGS+=(--no-answer)
[ "${SHORT_ANSWERS}" = "1" ] && RUN_ARGS+=(--short-answers)
[ "${LIMIT_DOCS}" -gt 0 ] 2>/dev/null && RUN_ARGS+=(--limit-docs "${LIMIT_DOCS}")
[ "${LIMIT_QUESTIONS}" -gt 0 ] 2>/dev/null && RUN_ARGS+=(--limit-questions "${LIMIT_QUESTIONS}")

echo "=== Starting RAGU pipeline ===" | tee -a "${log_file}"
python runs/ragu_run.py "${RUN_ARGS[@]}" >> "${log_file}" 2>&1
status=$?
echo "=== RAGU pipeline finished (exit ${status}) ===" | tee -a "${log_file}"

# ---------- ЭТАП 3: Сводка по скорости индексации ----------
python runs/index_stats.py "${OUTPUT_DIR}" >> "${log_file}" 2>&1 || true

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit ${status}
