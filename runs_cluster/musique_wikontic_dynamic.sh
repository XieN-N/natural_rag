#!/bin/bash

# ============================================================
# Wikontic на musique, режим DYNAMIC (без онтологии Wikidata) —
# индексация корпусного графа + генерация ответов.
#
#   sbatch runs_cluster/musique_wikontic_dynamic.sh
#
# Парный скрипт: musique_wikontic_structured.sh. Можно запускать оба
# одновременно — у них разные порты vLLM, разные storage-директории
# Qdrant и разные префиксы коллекций. Сравнение s/doc между ними и
# покажет, во сколько раз онтология дороже.
#
# Онтология здесь не нужна, build_ontology.sh запускать не требуется.
#
# Прогресс: runs_cluster/show_progress.sh (работает на незавершённых
# прогонах — index_summary.json пишется сразу со статусом running).
# Упал по таймауту — просто поставьте этот же скрипт снова, --resume
# пропустит уже проиндексированные документы.
# ============================================================

#SBATCH --job-name=wiko_mus_dyn
#SBATCH --partition=a800
#SBATCH --error="/userspace/sse/natural_rag/logs/musique_wikontic_dynamic.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/musique_wikontic_dynamic.log"
#SBATCH --open-mode=append

# Токен ЛОКАЛЬНЫХ vLLM-серверов, которые этот же скрипт поднимает ниже.
# Это не секрет: он только авторизует запросы к localhost-эндпоинтам джобы.
VLLM_SERVE_TOKEN="${VLLM_SERVE_TOKEN:-local-vllm-placeholder}"

# ---------------- НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ------------------
DATASET_NAME="musique"

# Модель. Для прогона на большой модели меняются только эти три строки.
BIG_LLM_MODEL="/userspace/kms/models/gigachat-3.1-lightning"
BIG_LLM_NAME="gigachat-3.1-lightning"
BIG_LLM_PORT=8010                     # у structured-скрипта 8000

# Локальный contriever — захардкоженный эмбеддер Wikontic
CONTRIEVER_PATH="/userspace/sse/models/contriever"

# Wikontic
WIKONTIC_MODE="dynamic"
WIKONTIC_SCOPE="corpus"               # corpus | per_sample
WIKONTIC_PER_SAMPLE_DOCS=20           # только для per_sample
# 1 = как в апстриме (там индексация строго последовательная) — честная цифра
# «скорость как есть». Значения >1 включают нашу внешнюю добавку.
WIKONTIC_WORKERS=1
WIKONTIC_QA_COLLAPSING=0              # 1 = QA-путь из их статьи
SHORT_ANSWERS=1                       # musique — короткие ответы
LIMIT_DOCS=0                          # >0 — только первые N документов

# Хранилище
QDRANT_BIN="/userspace/sse/qdrant/qdrant"
QDRANT_STORAGE_ROOT="/userspace/sse/qdrant_storage"

# Этапы
DO_INDEX=1
DO_ANSWER=1
# 1 = перегенерировать уже существующие ответы (нужно, если индекс расширился)
FORCE=0

# GPU
NUM_GPUS=1
if [ ${NUM_GPUS} -ge 8 ]; then
    LLM_GPUS=0,1,2,3,4,5,6,7
    LLM_TENSOR_PARALLEL=8
    LLM_MEM_UTIL=0.85
else
    LLM_GPUS=0
    LLM_TENSOR_PARALLEL=1
    LLM_MEM_UTIL=0.80
fi
# --------------------------------------------------------------

set -o pipefail

RUN_ID="wikontic_musique_dynamic"
project_root="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
miniconda_dir="/userspace/sse/miniconda3"
conda_env="wikontic"

DATASET_PATH="${project_root}/datasets/${DATASET_NAME}"
# Каталог результатов включает режим: иначе structured и dynamic писали бы ответы
# и index_timing.jsonl в один и тот же generated/wikontic_musique/musique/<модель>/.
OUTPUT_DIR="${project_root}/generated/${RUN_ID}"
QDRANT_STORAGE="${QDRANT_STORAGE_ROOT}/${RUN_ID}"

logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
mkdir -p "${logs_dir}" "${cache_root}"

log_file="${logs_dir}/main.log"
BIG_LLM_LOG="${logs_dir}/vllm_llm.log"
QDRANT_LOG="${logs_dir}/qdrant.log"

echo "=== Job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID=${RUN_ID} mode=${WIKONTIC_MODE} scope=${WIKONTIC_SCOPE} workers=${WIKONTIC_WORKERS}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

wait_for_vllm() {
    echo "=== Waiting for vLLM to start ===" | tee -a "${log_file}"
    while ! grep -q "Starting vLLM API server" "${BIG_LLM_LOG}" 2>/dev/null; do
        if ! kill -0 "${LLM_PID}" 2>/dev/null; then
            echo "ERROR: vLLM died on startup, see ${BIG_LLM_LOG}" | tee -a "${log_file}"
            exit 1
        fi
        sleep 5
    done
    echo "=== vLLM started ===" | tee -a "${log_file}"
}

find_free_port() {
    python - "$1" <<'PY'
import socket, sys
start = int(sys.argv[1])
for port in range(start, start + 500):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        break
else:
    sys.exit("no free port found")
PY
}

cleanup() {
    echo "=== Cleanup ===" | tee -a "${log_file}"
    [ -n "${LLM_PID}" ] && kill "${LLM_PID}" 2>/dev/null
    if [ -n "${QDRANT_PID}" ]; then
        # даём Qdrant дописать сегменты, прежде чем job исчезнет
        kill "${QDRANT_PID}" 2>/dev/null
        for _ in $(seq 30); do
            kill -0 "${QDRANT_PID}" 2>/dev/null || break
            sleep 1
        done
    fi
    [ -n "${OWNER_FILE}" ] && rm -f "${OWNER_FILE}"
    wait 2>/dev/null
}
trap cleanup EXIT

# Убираем ТОЛЬКО свои остатки на этом порту. Веерный `pkill -f vllm` убил бы
# vLLM параллельного прогона, если SLURM положил нас на одну ноду.
echo "=== Killing leftover vLLM on port ${BIG_LLM_PORT} ===" | tee -a "${log_file}"
pkill -u "$(whoami)" -f "vllm serve.*--port ${BIG_LLM_PORT}" 2>/dev/null || true
sleep 5
nvidia-smi >> "${log_file}"

# Кэши — свои на прогон
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
mkdir -p "${FLASHINFER_WORKSPACE_DIR}" "${VLLM_CACHE_ROOT}" "${TORCH_HOME}" \
         "${XDG_CACHE_HOME}" "${TRITON_CACHE_DIR}" "${PIP_CACHE_DIR}"

export HF_MODEL_PATH="${CONTRIEVER_PATH}"
export WIKONTIC_DEVICE="cuda"
if [ ! -d "${HF_MODEL_PATH}" ]; then
    echo "ERROR: contriever not found at ${HF_MODEL_PATH}" | tee -a "${log_file}"
    echo "Скачайте его на login-ноде, см. runs_cluster/README.md" | tee -a "${log_file}"
    exit 1
fi

# ---------- ЭТАП 1: Qdrant ----------
# Своя storage-директория на прогон: два процесса Qdrant поверх одной директории
# на сетевой ФС портят данные, блокировки на NFS ненадёжны.
OWNER_FILE="${QDRANT_STORAGE}/.owner"
if [ -f "${OWNER_FILE}" ]; then
    owner_job=$(cat "${OWNER_FILE}" 2>/dev/null)
    if [ -n "${owner_job}" ] && [ -n "$(squeue -h -j "${owner_job}" 2>/dev/null)" ]; then
        echo "ERROR: ${QDRANT_STORAGE} занят живым job'ом ${owner_job}." | tee -a "${log_file}"
        OWNER_FILE=""   # чужой файл в cleanup не трогаем
        exit 1
    fi
    echo "=== Протухший .owner от job ${owner_job}, перехватываем ===" | tee -a "${log_file}"
fi
mkdir -p "${QDRANT_STORAGE}"
echo "${SLURM_JOB_ID:-$$}" > "${OWNER_FILE}"

QDRANT_PORT=$(find_free_port 16333)
QDRANT_GRPC_PORT=$(find_free_port $((QDRANT_PORT + 10000)))
echo "=== Starting Qdrant on port ${QDRANT_PORT} (storage ${QDRANT_STORAGE}) ===" | tee -a "${log_file}"
QDRANT__SERVICE__HTTP_PORT=${QDRANT_PORT} \
QDRANT__SERVICE__GRPC_PORT=${QDRANT_GRPC_PORT} \
QDRANT__SERVICE__HOST=127.0.0.1 \
QDRANT__STORAGE__STORAGE_PATH="${QDRANT_STORAGE}" \
QDRANT__TELEMETRY_DISABLED=true \
QDRANT__STORAGE__WAL__WAL_CAPACITY_MB=1 \
QDRANT__SERVICE__MAX_REQUEST_SIZE_MB=256 \
"${QDRANT_BIN}" > "${QDRANT_LOG}" 2>&1 &
QDRANT_PID=$!
until curl -sf "http://127.0.0.1:${QDRANT_PORT}/healthz" >/dev/null; do
    if ! kill -0 ${QDRANT_PID} 2>/dev/null; then
        echo "ERROR: Qdrant died on startup, see ${QDRANT_LOG}" | tee -a "${log_file}"
        exit 1
    fi
    sleep 2
done
echo "=== Qdrant ready ===" | tee -a "${log_file}"

# ---------- ЭТАП 2: vLLM ----------
echo "=== Starting vLLM (${BIG_LLM_NAME}) on port ${BIG_LLM_PORT} ===" | tee -a "${log_file}"
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
wait_for_vllm

export OPENAI_BASE_URL="http://localhost:${BIG_LLM_PORT}/v1"
export OPENAI_API_KEY="${VLLM_SERVE_TOKEN}"
export LLM_MODEL="${BIG_LLM_NAME}"

# ---------- ЭТАП 3: Индексация и ответы ----------
cd "${project_root}" || exit 1

RUN_ARGS=(
    --dataset-path "${DATASET_PATH}"
    --output-dir "${OUTPUT_DIR}"
    --index-model "${BIG_LLM_NAME}"
    --model "${BIG_LLM_NAME}"
    --mode "${WIKONTIC_MODE}"
    --scope "${WIKONTIC_SCOPE}"
    --per-sample-docs "${WIKONTIC_PER_SAMPLE_DOCS}"
    --workers "${WIKONTIC_WORKERS}"
    --hf-model-path "${HF_MODEL_PATH}"
    --collection-prefix "${RUN_ID}"
    --backend-type qdrant
    --qdrant-url "http://127.0.0.1:${QDRANT_PORT}"
    # На сетевой ФС один create_payload_index занимает ~10 с, а дефолтный
    # таймаут qdrant-client меньше десяти секунд.
    --qdrant-timeout 120
    --resume
)
[ "${DO_INDEX}"  = "1" ] && RUN_ARGS+=(--build-index) || RUN_ARGS+=(--no-build-index)
[ "${DO_ANSWER}" = "1" ] && RUN_ARGS+=(--answer)      || RUN_ARGS+=(--no-answer)
[ "${FORCE}" = "1" ] && RUN_ARGS+=(--force)
[ "${WIKONTIC_QA_COLLAPSING}" = "1" ] && RUN_ARGS+=(--qa-collapsing)
[ "${SHORT_ANSWERS}" = "1" ] && RUN_ARGS+=(--short-answers)
[ "${LIMIT_DOCS}" != "0" ] && RUN_ARGS+=(--limit-docs "${LIMIT_DOCS}")

echo "=== Starting Wikontic pipeline ===" | tee -a "${log_file}"
python runs/wikontic_run.py "${RUN_ARGS[@]}" >> "${log_file}" 2>&1
status=$?
echo "=== Wikontic pipeline finished (exit ${status}) ===" | tee -a "${log_file}"

# ---------- ЭТАП 4: Сводка по скорости индексации ----------
python runs/index_stats.py "${OUTPUT_DIR}" >> "${log_file}" 2>&1 || true

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit ${status}
