#!/bin/bash

# ============================================================
# Универсальный скрипт ТОЛЬКО ДЛЯ ОЦЕНКИ (LLM-судья)
# Использует уже сгенерированные ответы (txt -> json).
# Все логи и кэш изолированы по RUN_ID.
# ============================================================

#SBATCH --job-name=eval_bl_qwen
#SBATCH --partition=a800
#SBATCH --error="/userspace/sse/natural_rag/logs/eval_universal.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/eval_universal.log"
#SBATCH --open-mode=append

# ---------------- НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ------------------
RAG_ENGINE="lightrag"          # lightrag или fast_graphrag (только для формирования RUN_ID)
DATASET_NAME="bl"              # имя датасета (папка в datasets/)

# Модель, которая использовалась для генерации ответов (нужна для RUN_ID)
BIG_LLM_NAME="Qwen2.5-14B-Instruct"

# Модель-судья и её путь
JUDGE_MODEL="/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct"
JUDGE_MODEL_NAME="Qwen2.5-14B-Instruct"
JUDGE_PORT=8200

# Количество GPU (обычно 1 для судьи, можно оставить 0)
NUM_GPUS=1
JUDGE_GPUS=0
# --------------------------------------------------------------

project_root="/userspace/sse/natural_rag"
miniconda_dir="/userspace/sse/miniconda3"
eval_conda_env="lightrag"   # всегда lightrag для оценки

# Идентификатор запуска (должен совпадать с тем, что использовался при генерации ответов)
RUN_ID="${RAG_ENGINE}_${DATASET_NAME}_${BIG_LLM_NAME}"

# Уникальные папки для логов и кэша оценки
logs_dir="${project_root}/logs/${RUN_ID}_eval"
cache_root="/userspace/sse/cache/${RUN_ID}_eval"
eval_cache_dir="${cache_root}/judge"

mkdir -p "${logs_dir}" "${eval_cache_dir}"

log_file="${logs_dir}/eval.log"
err_file="${logs_dir}/eval.err"
JUDGE_LOG="${logs_dir}/vllm_judge.log"

echo "=== Evaluation job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${eval_conda_env}"

# Очистка процессов
echo "=== Killing leftover vllm/torch processes ===" | tee -a "${log_file}"
pkill -u "$(whoami)" -f vllm 2>/dev/null || true
pkill -u "$(whoami)" -f "EngineCore" 2>/dev/null || true
sleep 5
nvidia-smi >> "${log_file}"

# Переменные окружения для кэша
export HOME="/userspace/sse"
export PIP_CACHE_DIR="${cache_root}/pip"
export HF_HOME="${cache_root}/huggingface"
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export DO_NOT_TRACK=1

export DATASET_NAME="${DATASET_NAME}"
export VLLM_CACHE_DIR="${cache_root}/vllm_cache"
export TORCH_HOME="${cache_root}/torch_cache"
export XDG_CACHE_HOME="${cache_root}/xdg_cache"
export TRITON_CACHE_DIR="${cache_root}/triton_cache"
export FLASHINFER_WORKSPACE_DIR="${cache_root}/flashinfer_workspace"
mkdir -p "$FLASHINFER_WORKSPACE_DIR" "$VLLM_CACHE_DIR" "$TORCH_HOME" "$XDG_CACHE_HOME" "$TRITON_CACHE_DIR" "$PIP_CACHE_DIR"

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

# ---------- ЗАПУСК СУДЬИ ----------
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
export OPENAI_API_KEY="token-abc123"
export JUDGE_MODEL_NAME="${JUDGE_MODEL_NAME}"

# ---------- ПРОВЕРКА / СОЗДАНИЕ JSON С ОТВЕТАМИ ----------
# Определяем пути (как в универсальном скрипте генерации)
ANSWERS_DIR="${project_root}/generated/${RUN_ID}/answers"
if [ "${DATASET_NAME}" = "multiq" ]; then
    ANSWERS_PATTERN="multi_q_*.json"
    ANSWERS_JSON_FILE="multi_q_answers.json"
else
    ANSWERS_PATTERN="${DATASET_NAME}_*.json"
    ANSWERS_JSON_FILE="${DATASET_NAME}_answers.json"
fi
export ANSWERS_DIR ANSWERS_PATTERN ANSWERS_JSON_FILE

# Если JSON-файла нет, создаём его из txt
if ! ls "${ANSWERS_DIR}"/${ANSWERS_PATTERN} 1>/dev/null 2>&1; then
    echo "=== JSON answers not found. Converting from txt... ===" | tee -a "${log_file}"
    cd "${project_root}" || exit 1
    python runs_universal/convert_answers_bl.py >> "${log_file}" 2>&1
else
    echo "=== JSON answers found, skipping conversion ===" | tee -a "${log_file}"
fi

# ---------- ЗАПУСК ОЦЕНКИ ----------
echo "=== Starting evaluation ===" | tee -a "${log_file}"
cd "${project_root}" || exit 1
python runs_universal/evaluate_bl.py >> "${log_file}" 2>&1
echo "=== Evaluation finished ===" | tee -a "${log_file}"

# Очистка
kill ${JUDGE_PID} 2>/dev/null
wait ${JUDGE_PID} 2>/dev/null
echo "=== Job finished at $(date) ===" | tee -a "${log_file}"