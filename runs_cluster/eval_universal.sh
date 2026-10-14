#!/bin/bash

# ============================================================
# Универсальный скрипт ОЦЕНКИ ответов (любой движок).
# Читает уже сгенерированные answers/<i>.txt и считает EM / F1 /
# accuracy по LLM-судье, а также готовит вход для GraphRAG-Benchmark.
# ============================================================

#SBATCH --job-name=eval_rag
#SBATCH --partition=a800
#SBATCH --error="/userspace/sse/natural_rag/logs/eval_universal.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/eval_universal.log"
#SBATCH --open-mode=append

# Токен ЛОКАЛЬНЫХ vLLM-серверов, которые этот же скрипт поднимает ниже.
# Это не секрет: он только авторизует запросы к localhost-эндпоинтам джобы.
VLLM_SERVE_TOKEN="${VLLM_SERVE_TOKEN:-local-vllm-placeholder}"

# ---------------- НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ------------------
RAG_ENGINE="wikontic"                 # wikontic | ragu  (только для путей)
DATASET_NAME="musique"
INDEX_MODEL="gigachat-3.1-lightning"  # тот же --index-model, что при генерации
# Имя каталога в generated/. Пусто -> ${RAG_ENGINE}_${DATASET_NAME}.
# У выделенных скриптов musique_wikontic_* оно равно их RUN_ID, например
# "wikontic_musique_structured" или "wikontic_musique_dynamic".
OUTPUT_DIR_NAME=""

JUDGE_MODEL="/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct"
JUDGE_MODEL_NAME="Qwen2.5-14B-Instruct"
JUDGE_PORT=8200
JUDGE_GPUS=0

BUILD_GRAPHRAG_BENCH_INPUT=1          # 1 = собрать graphrag_bench_input.json
# --------------------------------------------------------------

set -o pipefail

project_root="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
miniconda_dir="/userspace/sse/miniconda3"
eval_conda_env="lightrag"             # судья не зависит от движка

RUN_ID="eval_${RAG_ENGINE}_${DATASET_NAME}_${INDEX_MODEL}"
logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
eval_cache_dir="${cache_root}/judge"
mkdir -p "${logs_dir}" "${eval_cache_dir}"

log_file="${logs_dir}/eval.log"
JUDGE_LOG="${logs_dir}/vllm_judge.log"

DATASET_PATH="${project_root}/datasets/${DATASET_NAME}"
OUTPUT_DIR="${project_root}/generated/${OUTPUT_DIR_NAME:-${RAG_ENGINE}_${DATASET_NAME}}"

echo "=== Evaluation job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${eval_conda_env}"

wait_for_vllm() {
    local log_path="$1"
    local name="$2"
    echo "=== Waiting for ${name} to start ===" | tee -a "${log_file}"
    while ! grep -q "Starting vLLM API server" "${log_path}" 2>/dev/null; do
        sleep 5
    done
    echo "=== ${name} started ===" | tee -a "${log_file}"
}

cleanup() {
    [ -n "${JUDGE_PID}" ] && kill "${JUDGE_PID}" 2>/dev/null
    wait 2>/dev/null
}
trap cleanup EXIT

echo "=== Killing leftover vllm/torch processes ===" | tee -a "${log_file}"
pkill -u "$(whoami)" -f vllm 2>/dev/null || true
pkill -u "$(whoami)" -f "EngineCore" 2>/dev/null || true
sleep 5
nvidia-smi >> "${log_file}"

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

cd "${project_root}" || exit 1

# ---------- ЭТАП 1: Вход для GraphRAG-Benchmark ----------
if [ "${BUILD_GRAPHRAG_BENCH_INPUT}" = "1" ]; then
    echo "=== Building GraphRAG-Benchmark input JSON ===" | tee -a "${log_file}"
    python runs/build_graphrag_bench_input.py \
        --dataset-path "${DATASET_PATH}" \
        --output-dir "${OUTPUT_DIR}" \
        --index-model "${INDEX_MODEL}" \
        --skip-missing >> "${log_file}" 2>&1 || true
fi

# ---------- ЭТАП 2: Судья ----------
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
wait_for_vllm "${JUDGE_LOG}" "Judge"

export OPENAI_BASE_URL="http://localhost:${JUDGE_PORT}/v1"
export OPENAI_API_KEY="${VLLM_SERVE_TOKEN}"
export JUDGE_MODEL_NAME="${JUDGE_MODEL_NAME}"

# ---------- ЭТАП 3: Оценка ----------
echo "=== Starting evaluation ===" | tee -a "${log_file}"
python runs/judge_answers.py \
    --dataset-path "${DATASET_PATH}" \
    --output-dir "${OUTPUT_DIR}" \
    --index-model "${INDEX_MODEL}" \
    --judge-model "${JUDGE_MODEL_NAME}" >> "${log_file}" 2>&1
status=$?
echo "=== Evaluation finished (exit ${status}) ===" | tee -a "${log_file}"

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit ${status}
