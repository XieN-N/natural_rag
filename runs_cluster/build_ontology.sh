#!/bin/bash

# ============================================================
# Разовая сборка Wikidata-онтологии для режима structured.
#
# Пишет её в эталонную storage-директорию Qdrant; дальше каждый
# structured-прогон копирует её себе сам, так что запускать надо
# ОДИН РАЗ. Индексация и генерация ответов здесь отключены.
#
#   sbatch runs_cluster/build_ontology.sh
#
# Готовность: ls /userspace/sse/qdrant_storage/_ontology_base/collections
# ============================================================

#SBATCH --job-name=wiko_onto
#SBATCH --partition=a800
#SBATCH --error="/userspace/sse/natural_rag/logs/build_ontology.err"
#SBATCH --output="/userspace/sse/natural_rag/logs/build_ontology.log"
#SBATCH --open-mode=append

# ---------------- НАСТРОЙКИ ------------------
CONTRIEVER_PATH="/userspace/sse/models/contriever"
QDRANT_BIN="/userspace/sse/qdrant/qdrant"
QDRANT_STORAGE="/userspace/sse/qdrant_storage/_ontology_base"

RUN_ID="build_ontology"
GPUS=0
# ---------------------------------------------

set -o pipefail

project_root="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
miniconda_dir="/userspace/sse/miniconda3"
conda_env="wikontic"

logs_dir="${project_root}/logs/${RUN_ID}"
cache_root="/userspace/sse/cache/${RUN_ID}"
mkdir -p "${logs_dir}" "${cache_root}"

log_file="${logs_dir}/main.log"
QDRANT_LOG="${logs_dir}/qdrant.log"

echo "=== Job started at $(date) ===" | tee -a "${log_file}"

source "${miniconda_dir}/etc/profile.d/conda.sh"
conda activate "/userspace/sse/.conda/envs/${conda_env}"

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
    if [ -n "${QDRANT_PID}" ]; then
        kill "${QDRANT_PID}" 2>/dev/null
        for _ in $(seq 30); do
            kill -0 "${QDRANT_PID}" 2>/dev/null || break
            sleep 1
        done
    fi
    wait 2>/dev/null
}
trap cleanup EXIT

export HOME="/userspace/sse"
export PIP_CACHE_DIR="${cache_root}/pip"
export HF_HOME="${cache_root}/huggingface"
export HF_DATASETS_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export DO_NOT_TRACK=1
export TORCH_HOME="${cache_root}/torch_cache"
export XDG_CACHE_HOME="${cache_root}/xdg_cache"
mkdir -p "${TORCH_HOME}" "${XDG_CACHE_HOME}" "${PIP_CACHE_DIR}"

export HF_MODEL_PATH="${CONTRIEVER_PATH}"
export CUDA_VISIBLE_DEVICES="${GPUS}"
if [ ! -d "${HF_MODEL_PATH}" ]; then
    echo "ERROR: contriever not found at ${HF_MODEL_PATH}" | tee -a "${log_file}"
    exit 1
fi

if [ -d "${QDRANT_STORAGE}/collections" ]; then
    echo "Онтология уже собрана в ${QDRANT_STORAGE}." | tee -a "${log_file}"
    echo "Пересобрать: сначала rm -rf ${QDRANT_STORAGE}" | tee -a "${log_file}"
    exit 0
fi
mkdir -p "${QDRANT_STORAGE}"

# ---------- Qdrant ----------
QDRANT_PORT=$(find_free_port 16333)
QDRANT_GRPC_PORT=$(find_free_port $((QDRANT_PORT + 10000)))
echo "=== Starting Qdrant on port ${QDRANT_PORT} (storage ${QDRANT_STORAGE}) ===" | tee -a "${log_file}"
QDRANT__SERVICE__HTTP_PORT=${QDRANT_PORT} \
QDRANT__SERVICE__GRPC_PORT=${QDRANT_GRPC_PORT} \
QDRANT__SERVICE__HOST=127.0.0.1 \
QDRANT__STORAGE__STORAGE_PATH="${QDRANT_STORAGE}" \
QDRANT__TELEMETRY_DISABLED=true \
QDRANT__STORAGE__WAL__WAL_CAPACITY_MB=1 \
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

# ---------- Сборка онтологии ----------
# LLM не нужен: contriever эмбеддит алиасы из Wikidata-маппингов, лежащих в пакете.
cd "${project_root}" || exit 1
echo "=== Building Wikidata ontology DB ===" | tee -a "${log_file}"
python -m scripts.setup_wikontic_ontology \
    --backend qdrant \
    --qdrant-url "http://127.0.0.1:${QDRANT_PORT}" \
    --qdrant-timeout 300 >> "${log_file}" 2>&1
status=$?
echo "=== Ontology build finished (exit ${status}) ===" | tee -a "${log_file}"

if [ ${status} -ne 0 ]; then
    echo "Сборка не удалась — директория оставлена как есть для разбора." | tee -a "${log_file}"
fi

curl -s "http://127.0.0.1:${QDRANT_PORT}/collections" >> "${log_file}" 2>&1

echo "=== Job finished at $(date) ===" | tee -a "${log_file}"
exit ${status}
