#!/bin/bash

# ============================================================
# Универсальный скрипт для RAG-экспериментов (LightRAG / Fast GraphRAG)
# с индексацией, генерацией ответов, конвертацией и оценкой LLM-судьёй.
# Все пути (логи, кэш, ответы) изолированы с помощью RUN_ID.
# Настройка GPU – укажите NUM_GPUS, остальное подстроится.
# ============================================================

#SBATCH --job-name=bl_fast_qwen
#SBATCH --partition=a800
#SBATCH --error="/userspace/sse/natural_rag/logs/rag_universal.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/rag_universal.log"
#SBATCH --open-mode=append

# ---------------- НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ------------------
RAG_ENGINE="fast_graphrag"                # lightrag или fast_graphrag
DATASET_NAME="bl"                # имя датасета (папка в datasets/)

# Модели
BIG_LLM_MODEL="/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct"
EMBED_MODEL="/userspace/kms/models/gte-multilingual-base"
JUDGE_MODEL="/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct"

BIG_LLM_NAME="Qwen2.5-14B-Instruct"
EMBED_MODEL_NAME="gte-multilingual-base"
JUDGE_MODEL_NAME="Qwen2.5-14B-Instruct"

# Порты
BIG_LLM_PORT=8000
EMBED_PORT=8002
JUDGE_PORT=8200

# ===================== КОНФИГУРАЦИЯ GPU =====================
NUM_GPUS=10   # укажите количество GPU на ноде (1,2,8,10...)

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
JUDGE_GPUS=0

# Идентификатор запуска
RUN_ID="${RAG_ENGINE}_${DATASET_NAME}_${BIG_LLM_NAME}"
# --------------------------------------------------------------

project_root="/userspace/sse/natural_rag"
miniconda_dir="/userspace/sse/miniconda3"

# Окружение для индексации и генерации
conda_env="${RAG_ENGINE}"
# Окружение для оценки (всегда lightrag)
eval_conda_env="lightrag"

# Уникальные папки для логов и кэша
logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
eval_cache_dir="${cache_root}/eval"

mkdir -p "${logs_dir}" "${cache_root}" "${eval_cache_dir}"

log_file="${logs_dir}/main.log"
err_file="${logs_dir}/main.err"
BIG_LLM_LOG="${logs_dir}/vllm_llm.log"
EMBED_LOG="${logs_dir}/vllm_embed.log"
JUDGE_LOG="${logs_dir}/vllm_judge.log"

echo "=== Job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}" | tee -a "${log_file}"
echo "GPU config: NUM_GPUS=${NUM_GPUS}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

# Функция ожидания vLLM
wait_for_vllm() {
    local log_path="$1"
    local name="$2"
    echo "=== Waiting for ${name} to start ===" | tee -a "${log_file}"
    while ! grep -q "Starting vLLM API server" "${log_path}" 2>/dev/null; do
        sleep 5
    done
    echo "=== ${name} started ===" | tee -a "${log_file}"
}

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

# Пути индекса и ответов
INDEX_DIR="${project_root}/generated/${RUN_ID}/index"
ANSWERS_DIR="${project_root}/generated/${RUN_ID}/answers"
mkdir -p "${INDEX_DIR}" "${ANSWERS_DIR}"

# ---------- ЭТАП 1: Запуск LLM и эмбеддера ----------
echo "=== Starting vLLM for LLM (${BIG_LLM_NAME}) ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=${LLM_GPUS} vllm serve "${BIG_LLM_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key token-abc123 \
    --gpu-memory-utilization ${LLM_MEM_UTIL} \
    --max-model-len 32768 \
    --served-model-name "${BIG_LLM_NAME}" \
    --port "${BIG_LLM_PORT}" \
    --tensor-parallel-size ${LLM_TENSOR_PARALLEL} \
    > "${BIG_LLM_LOG}" 2>&1 &

wait_for_vllm "${BIG_LLM_LOG}" "LLM"

echo "=== Starting vLLM for embeddings (${EMBED_MODEL_NAME}) ===" | tee -a "${log_file}"
CUDA_VISIBLE_DEVICES=${EMBED_GPUS} vllm serve "${EMBED_MODEL}" \
    --download-dir "${cache_root}" \
    --api-key token-abc123 \
    --gpu-memory-utilization ${EMBED_MEM_UTIL} \
    --served-model-name "${EMBED_MODEL_NAME}" \
    --port "${EMBED_PORT}" \
    --hf-overrides '{"architectures": ["GteNewModel"]}' \
    --trust_remote_code \
    > "${EMBED_LOG}" 2>&1 &

wait_for_vllm "${EMBED_LOG}" "Embedder"

# Экспорт переменных для Python-скриптов
export OPENAI_BASE_URL="http://localhost:${BIG_LLM_PORT}/v1"
export EMBED_BASE_URL="http://localhost:${EMBED_PORT}/v1"
export OPENAI_API_KEY="token-abc123"
export LLM_MODEL="${BIG_LLM_NAME}"
export EMBED_MODEL="${EMBED_MODEL_NAME}"
export EMBEDDING_DIM=768
export CONCURRENT_TASK_LIMIT=128

export RAG_ENGINE="${RAG_ENGINE}"
export DATASET_NAME="${DATASET_NAME}"
export INDEX_DIR="${INDEX_DIR}"
export ANSWERS_DIR="${ANSWERS_DIR}"

# ---------- ЭТАП 2: Индексация и генерация ответов ----------
echo "=== Starting RAG pipeline (${RAG_ENGINE}) ===" | tee -a "${log_file}"
cd "${project_root}" || exit 1

if [ "${RAG_ENGINE}" = "fast_graphrag" ]; then
    python runs_universal/fast_graphrag_run_bl.py >> "${log_file}" 2>&1
else
    python runs_universal/lightrag_run_bl.py >> "${log_file}" 2>&1
fi
echo "=== RAG pipeline finished ===" | tee -a "${log_file}"

# ---------- ЭТАП 3: Конвертация ответов в JSON ----------
# Определяем паттерн и имя файла для ответов
if [ "${DATASET_NAME}" = "multiq" ]; then
    ANSWERS_PATTERN="multi_q_*.json"
    ANSWERS_JSON_FILE="multi_q_answers.json"
else
    ANSWERS_PATTERN="${DATASET_NAME}_*.json"
    ANSWERS_JSON_FILE="${DATASET_NAME}_answers.json"
fi
export ANSWERS_PATTERN ANSWERS_JSON_FILE

echo "=== Converting answers to JSON ===" | tee -a "${log_file}"
python runs_universal/convert_answers_bl.py >> "${log_file}" 2>&1

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
    --api-key token-abc123 \
    --gpu-memory-utilization 0.8 \
    --max-model-len 8192 \
    --served-model-name "${JUDGE_MODEL_NAME}" \
    --port "${JUDGE_PORT}" \
    > "${JUDGE_LOG}" 2>&1 &

JUDGE_PID=$!

wait_for_vllm "${JUDGE_LOG}" "Judge"

export OPENAI_BASE_URL="http://localhost:${JUDGE_PORT}/v1"
export JUDGE_MODEL_NAME="${JUDGE_MODEL_NAME}"

# Паттерн для JSON с ответами
if [ "${DATASET_NAME}" = "multiq" ]; then
    export ANSWERS_PATTERN="multi_q_*.json"
else
    export ANSWERS_PATTERN="${DATASET_NAME}_*.json"
fi

echo "=== Starting evaluation ===" | tee -a "${log_file}"
python runs_universal/evaluate_bl.py >> "${log_file}" 2>&1
echo "=== Evaluation finished ===" | tee -a "${log_file}"

# Очистка
kill ${JUDGE_PID} 2>/dev/null
wait ${JUDGE_PID} 2>/dev/null

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"