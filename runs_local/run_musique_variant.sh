#!/bin/bash
# Answer one variant of a short-answer benchmark over an existing RAGU index.
#
#   runs_local/run_musique_variant.sh <variant> <limit_questions> [extra ragu_run.py flags...]
#
# Answers go to generated/ragu_<dataset>__<variant>/<dataset>/<index-model>/answers
# (with <i>.context.json), all variants sharing the index at
# generated/ragu_<dataset>/<dataset>/<index-model>/index. Questions already
# answered are skipped, so re-running with a larger limit resumes.
#
# Examples (decision-model experiments, see runs_local/README.md):
#   runs_local/run_musique_variant.sh base 498
#   runs_local/run_musique_variant.sh dm_h2p30_na 498 --always-answer \
#       --selector pointwise --decision-model-name gpt-4o-mini \
#       --select-hops 2 --select-pool-chunks 30
#
# Environment (defaults in brackets):
#   OPENAI_API_KEY      key for the answering/decision endpoint (required)
#   OPENAI_BASE_URL     [https://api.vsellm.ru/v1]
#   EMBED_BASE_URL      [http://127.0.0.1:8002/v1]  (runs_local/serve_embedder.py)
#   DATASET             [musique]        INDEX_MODEL [gpt-oss-20b]
#   ANSWER_MODEL        [gpt-4o-mini]
#   EMBED_MODEL_NAME    [gte-multilingual-base]     EMBEDDING_DIM [768]
#   LLM_CACHE_ROOT      [tmp/llm_cache]  one cache per variant: <root>_<variant>,
#                       or <root>_<CACHE_TAG> to reuse another variant's cache.
#                       Separate caches keep timings honest.
#   PYTHON              [python]  an interpreter with dev RAGU installed
set -euo pipefail

VARIANT="${1:?variant name}"
LIMIT="${2:?number of questions}"
shift 2

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATASET="${DATASET:-musique}"
INDEX_MODEL="${INDEX_MODEL:-gpt-oss-20b}"
: "${OPENAI_API_KEY:?set OPENAI_API_KEY}"
CACHE_ROOT="${LLM_CACHE_ROOT:-tmp/llm_cache}"

cd "$ROOT"
PYTHONPATH="$ROOT" "${PYTHON:-python}" -u runs/ragu_run.py \
  --dataset-path "datasets/${DATASET}" \
  --output-dir "generated/ragu_${DATASET}__${VARIANT}" \
  --index-model "${INDEX_MODEL}" \
  --index-dir "generated/ragu_${DATASET}/${DATASET}/${INDEX_MODEL}/index" \
  --no-build-index --answer --save-context --short-answers \
  --limit-questions "${LIMIT}" \
  --query-engine local \
  --openai-base-url "${OPENAI_BASE_URL:-https://api.vsellm.ru/v1}" \
  --embed-base-url "${EMBED_BASE_URL:-http://127.0.0.1:8002/v1}" \
  --builder-model-name "${ANSWER_MODEL:-gpt-4o-mini}" \
  --assistant-model-name "${ANSWER_MODEL:-gpt-4o-mini}" \
  --embedding-model-name "${EMBED_MODEL_NAME:-gte-multilingual-base}" \
  --embedding-dim "${EMBEDDING_DIM:-768}" \
  --openai-rate-min-delay 0 --openai-rate-max-simultaneous 16 \
  --llm-cache "${CACHE_ROOT}_${CACHE_TAG:-$VARIANT}" \
  "$@"
