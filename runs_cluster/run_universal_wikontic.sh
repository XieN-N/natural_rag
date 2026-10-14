#!/bin/bash

# ============================================================
# Универсальный скрипт для Wikontic: индексация + генерация ответов.
# Все пути (логи, кэш, индекс, ответы) изолированы с помощью RUN_ID.
# Вызывает канонический раннер runs/wikontic_run.py.
#
# Отличия от скриптов LightRAG/FastGraphRAG:
#   * vLLM для эмбеддера НЕ поднимается — Wikontic использует локальный
#     facebook/contriever (путь задаётся через HF_MODEL_PATH);
#   * поднимается хранилище (Qdrant-бинарь или уже готовый MongoDB);
#   * несколько индексов живут в одном хранилище за счёт префикса коллекций.
# ============================================================

#SBATCH --job-name=wikontic
#SBATCH --partition=a800
#SBATCH --error="/userspace/sse/natural_rag/logs/wikontic.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/wikontic.log"
#SBATCH --open-mode=append

# Токен ЛОКАЛЬНЫХ vLLM-серверов, которые этот же скрипт поднимает ниже.
# Это не секрет: он только авторизует запросы к localhost-эндпоинтам джобы.
VLLM_SERVE_TOKEN="${VLLM_SERVE_TOKEN:-local-vllm-placeholder}"

# ---------------- НАСТРОЙКИ (МЕНЯЙТЕ ЗДЕСЬ) ------------------
# Любую переменную можно переопределить из окружения при запуске, не трогая файл:
#   WIKONTIC_MODE=dynamic DATASET_NAME=bioasq sbatch runs_cluster/run_universal_wikontic.sh
# SLURM по умолчанию пробрасывает окружение в job (--export=ALL).
# Готовые наборы запусков — в runs_cluster/launch_*.sh.

DATASET_NAME="${DATASET_NAME:-musique}"        # папка в datasets/
DATASET_PATH="${DATASET_PATH:-}"               # пусто -> datasets/${DATASET_NAME}

# Модели
BIG_LLM_MODEL="${BIG_LLM_MODEL:-/userspace/kms/models/gigachat-3.1-lightning}"
BIG_LLM_NAME="${BIG_LLM_NAME:-gigachat-3.1-lightning}"
BIG_LLM_PORT="${BIG_LLM_PORT:-8000}"

# Локальный contriever (захардкоженный эмбеддер Wikontic)
CONTRIEVER_PATH="${CONTRIEVER_PATH:-/userspace/sse/models/contriever}"

# Режим Wikontic
WIKONTIC_MODE="${WIKONTIC_MODE:-structured}"   # structured | dynamic
WIKONTIC_SCOPE="${WIKONTIC_SCOPE:-corpus}"     # corpus | per_sample
WIKONTIC_PER_SAMPLE_DOCS="${WIKONTIC_PER_SAMPLE_DOCS:-20}"   # только для per_sample
# 1 = как в апстриме (там индексация строго последовательная) — честная цифра
# «скорость как есть». Значения >1 включают нашу внешнюю добавку.
WIKONTIC_WORKERS="${WIKONTIC_WORKERS:-1}"
WIKONTIC_QA_COLLAPSING="${WIKONTIC_QA_COLLAPSING:-0}"        # 1 = как в их qa_eval_*
SHORT_ANSWERS="${SHORT_ANSWERS:-0}"            # 1 для коротких ответов (musique/bioasq)
LIMIT_DOCS="${LIMIT_DOCS:-0}"                  # >0 — только первые N документов (смоук)

# Хранилище
STORAGE="${STORAGE:-qdrant_server}"            # qdrant_server | qdrant_local | mongo
QDRANT_BIN="${QDRANT_BIN:-/userspace/sse/qdrant/qdrant}"
QDRANT_STORAGE_ROOT="${QDRANT_STORAGE_ROOT:-/userspace/sse/qdrant_storage}"
# Пусто -> своя директория на каждый прогон (= RUN_ID). Так два процесса Qdrant
# никогда не окажутся поверх одной директории: на сетевой ФС это не «второй не
# стартует», а порча данных. Задавайте явно только чтобы переиспользовать чужой индекс.
QDRANT_STORAGE_ID="${QDRANT_STORAGE_ID:-}"
# Эталон с собранной онтологией: копируется в новую storage-директорию, чтобы не
# пересобирать её на каждом прогоне.
QDRANT_ONTOLOGY_BASE="${QDRANT_ONTOLOGY_BASE:-_ontology_base}"
MONGO_URI="${MONGO_URI:-}"                     # ветка mongo не используется, см. README
MONGO_TRIPLETS_DB="${MONGO_TRIPLETS_DB:-ragu_db}"
MONGO_ONTOLOGY_DB="${MONGO_ONTOLOGY_DB:-ragu_db}"

BUILD_ONTOLOGY="${BUILD_ONTOLOGY:-0}"          # 1 ТОЛЬКО на разовой сборке онтологии

# Этапы
DO_INDEX="${DO_INDEX:-1}"
DO_ANSWER="${DO_ANSWER:-1}"
# 1 = перегенерировать уже существующие ответы. Нужно, когда индекс расширился:
# иначе ответы, полученные на прежнем (неполном) графе, останутся как есть.
FORCE="${FORCE:-0}"

# ===================== КОНФИГУРАЦИЯ GPU =====================
NUM_GPUS="${NUM_GPUS:-1}"

if [ ${NUM_GPUS} -ge 10 ]; then
    LLM_GPUS=0,1,2,3,4,5,6,7
    LLM_TENSOR_PARALLEL=8
    LLM_MEM_UTIL=0.85
else
    LLM_GPUS=0
    LLM_TENSOR_PARALLEL=1
    LLM_MEM_UTIL=0.80
fi
# contriever крутится в том же процессе, что и python-прогон
CONTRIEVER_DEVICE="${CONTRIEVER_DEVICE:-cuda}"

# Идентификатор запуска
RUN_ID="${RUN_ID:-wikontic_${DATASET_NAME}_${BIG_LLM_NAME}_${WIKONTIC_MODE}_${WIKONTIC_SCOPE}}"
# --------------------------------------------------------------

set -o pipefail

project_root="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
miniconda_dir="/userspace/sse/miniconda3"
conda_env="wikontic"

if [ -z "${DATASET_PATH}" ]; then
    DATASET_PATH="${project_root}/datasets/${DATASET_NAME}"
fi

# Своя storage-директория на прогон, если не задана явно. Прогоны разных
# бенчмарков тогда можно гнать параллельно на разных нодах.
if [ -z "${QDRANT_STORAGE_ID}" ]; then
    QDRANT_STORAGE_ID="${RUN_ID}"
fi
mkdir -p "${QDRANT_STORAGE_ROOT}"

logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
mkdir -p "${logs_dir}" "${cache_root}"

log_file="${logs_dir}/main.log"
BIG_LLM_LOG="${logs_dir}/vllm_llm.log"
QDRANT_LOG="${logs_dir}/qdrant.log"

echo "=== Job started at $(date) ===" | tee -a "${log_file}"
echo "RUN_ID: ${RUN_ID}" | tee -a "${log_file}"
echo "mode=${WIKONTIC_MODE} scope=${WIKONTIC_SCOPE} storage=${STORAGE} workers=${WIKONTIC_WORKERS}" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

wait_for_vllm() {
    local log_path="$1"
    local name="$2"
    echo "=== Waiting for ${name} to start ===" | tee -a "${log_file}"
    while ! grep -q "Starting vLLM API server" "${log_path}" 2>/dev/null; do
        sleep 5
    done
    echo "=== ${name} started ===" | tee -a "${log_file}"
}

# Первый свободный TCP-порт начиная с $1. Арифметика от SLURM_JOB_ID сталкивалась
# бы для job'ов на одной ноде с ID, различающимися на период.
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
    [ -n "${LLM_PID}" ]    && kill "${LLM_PID}"    2>/dev/null
    if [ -n "${QDRANT_PID}" ]; then
        # SIGTERM и даём Qdrant дописать сегменты, прежде чем job исчезнет
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
# FlashInfer собирает CUDA-ядра JIT'ом системным nvcc, а на нодах CUDA 11 —
# у vLLM есть родной torch-сэмплер, он и нужен.
export VLLM_USE_FLASHINFER_SAMPLER=0

export VLLM_CACHE_ROOT="${cache_root}/vllm_cache"
export TORCH_HOME="${cache_root}/torch_cache"
export XDG_CACHE_HOME="${cache_root}/xdg_cache"
export TRITON_CACHE_DIR="${cache_root}/triton_cache"
export FLASHINFER_WORKSPACE_DIR="${cache_root}/flashinfer_workspace"
mkdir -p "${FLASHINFER_WORKSPACE_DIR}" "${VLLM_CACHE_ROOT}" "${TORCH_HOME}" "${XDG_CACHE_HOME}" "${TRITON_CACHE_DIR}" "${PIP_CACHE_DIR}"

# Локальный contriever — обязателен, т.к. на compute-нодах TRANSFORMERS_OFFLINE=1
export HF_MODEL_PATH="${CONTRIEVER_PATH}"
export WIKONTIC_DEVICE="${CONTRIEVER_DEVICE}"
if [ ! -d "${HF_MODEL_PATH}" ]; then
    echo "ERROR: contriever not found at ${HF_MODEL_PATH}" | tee -a "${log_file}"
    echo "Download it on the login node, see runs_cluster/README.md" | tee -a "${log_file}"
    exit 1
fi

# Каталог результатов = RUN_ID: иначе два режима на одном датасете писали бы ответы
# и index_timing.jsonl в один и тот же generated/wikontic_<датасет>/<датасет>/<модель>/.
OUTPUT_DIR="${project_root}/generated/${RUN_ID}"

# ---------- ЭТАП 1: Хранилище ----------
STORAGE_ARGS=()
case "${STORAGE}" in
  qdrant_server)
    QDRANT_STORAGE="${QDRANT_STORAGE_ROOT}/${QDRANT_STORAGE_ID}"

    # Один живой процесс Qdrant на директорию. Блокировки на сетевой ФС
    # ненадёжны, а два процесса поверх одного storage портят данные.
    OWNER_FILE="${QDRANT_STORAGE}/.owner"
    if [ -f "${OWNER_FILE}" ]; then
        owner_job=$(cat "${OWNER_FILE}" 2>/dev/null)
        if [ -n "${owner_job}" ] && squeue -h -j "${owner_job}" >/dev/null 2>&1 \
           && [ -n "$(squeue -h -j "${owner_job}" 2>/dev/null)" ]; then
            echo "ERROR: storage dir ${QDRANT_STORAGE} is owned by running job ${owner_job}." | tee -a "${log_file}"
            echo "Wait for it, or use a different QDRANT_STORAGE_ID." | tee -a "${log_file}"
            OWNER_FILE=""   # чужой файл в cleanup не трогаем
            exit 1
        fi
        echo "=== Stale .owner from job ${owner_job}, taking over ===" | tee -a "${log_file}"
    fi

    # Новую директорию заводим из эталона с уже собранной онтологией.
    if [ ! -d "${QDRANT_STORAGE}" ]; then
        ontology_base="${QDRANT_STORAGE_ROOT}/${QDRANT_ONTOLOGY_BASE}"
        if [ "${WIKONTIC_MODE}" = "structured" ] && [ "${BUILD_ONTOLOGY}" != "1" ] \
           && [ -d "${ontology_base}" ]; then
            echo "=== Seeding ${QDRANT_STORAGE} from ${ontology_base} ===" | tee -a "${log_file}"
            cp -r "${ontology_base}" "${QDRANT_STORAGE}"
            rm -f "${QDRANT_STORAGE}/.owner"
        else
            mkdir -p "${QDRANT_STORAGE}"
        fi
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
    QDRANT_URL="http://127.0.0.1:${QDRANT_PORT}"
    STORAGE_ARGS=(--backend-type qdrant --qdrant-url "${QDRANT_URL}")
    ;;
  qdrant_local)
    QDRANT_LOCAL_PATH="${QDRANT_STORAGE_ROOT}/${QDRANT_STORAGE_ID}_local"
    mkdir -p "${QDRANT_LOCAL_PATH}"
    echo "=== Qdrant in local-file mode: ${QDRANT_LOCAL_PATH} (no server) ===" | tee -a "${log_file}"
    STORAGE_ARGS=(--backend-type qdrant --qdrant-local-path "${QDRANT_LOCAL_PATH}")
    ;;
  mongo)
    echo "=== Using MongoDB storage ===" | tee -a "${log_file}"
    STORAGE_ARGS=(--backend-type mongo --mongo-uri "${MONGO_URI}"
                  --triplets-db-name "${MONGO_TRIPLETS_DB}"
                  --ontology-db-name "${MONGO_ONTOLOGY_DB}")
    ;;
  *)
    echo "ERROR: unknown STORAGE=${STORAGE}" | tee -a "${log_file}"; exit 1 ;;
esac

# ---------- ЭТАП 2: Запуск LLM ----------
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
wait_for_vllm "${BIG_LLM_LOG}" "LLM"

export OPENAI_BASE_URL="http://localhost:${BIG_LLM_PORT}/v1"
export OPENAI_API_KEY="${VLLM_SERVE_TOKEN}"
export LLM_MODEL="${BIG_LLM_NAME}"

cd "${project_root}" || exit 1

# ---------- ЭТАП 3: Разовая сборка онтологии ----------
if [ "${WIKONTIC_MODE}" = "structured" ] && [ "${BUILD_ONTOLOGY}" = "1" ]; then
    echo "=== Building Wikidata ontology DB (one-time) ===" | tee -a "${log_file}"
    if [ "${STORAGE}" = "mongo" ]; then
        python -m scripts.setup_wikontic_ontology --backend mongo \
            --mongo-uri "${MONGO_URI}" --ontology-db-name "${MONGO_ONTOLOGY_DB}" \
            >> "${log_file}" 2>&1
    else
        python -m scripts.setup_wikontic_ontology --backend qdrant \
            --qdrant-url "${QDRANT_URL:-:memory:}" >> "${log_file}" 2>&1
    fi
    echo "=== Ontology DB ready ===" | tee -a "${log_file}"
fi

# ---------- ЭТАП 4: Индексация и ответы ----------
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
    # На сетевой ФС один create_payload_index занимает ~10 с, а дефолтный
    # таймаут qdrant-client меньше десяти секунд.
    --qdrant-timeout 120
    --resume
    "${STORAGE_ARGS[@]}"
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

# ---------- ЭТАП 5: Проверка целостности индекса ----------
# Wikontic отчитывается 'failures: 0' и после того, как его Qdrant-адаптер
# удалил коллекцию: исключение ловится выше и оседает в filtered_triplets.
# Так уехал бандл, у которого линковка видела 5.8% графа. Проверяем явно.
if [ "${DO_INDEX}" = "1" ] && [ -n "${QDRANT_URL:-}" ]; then
    echo "=== Validating index ===" | tee -a "${log_file}"
    # ${PIPESTATUS[0]}, а не $?: через конвейер с tee возвращается код tee.
    python runs_local/validate_index.py \
        --qdrant-url "${QDRANT_URL}" \
        --collection-prefix "${RUN_ID}" 2>&1 | tee -a "${log_file}"
    validate_status=${PIPESTATUS[0]}
    if [ ${validate_status} -eq 0 ]; then
        echo "=== Index validated ===" | tee -a "${log_file}"
    else
        echo "ERROR: индекс не прошёл проверку — не вывозите его с кластера" \
            | tee -a "${log_file}"
        [ ${status} -eq 0 ] && status=1
    fi
fi

# ---------- ЭТАП 6: Сводка по скорости индексации ----------
python runs/index_stats.py "${OUTPUT_DIR}" >> "${log_file}" 2>&1 || true

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit ${status}
