#!/usr/bin/env bash
# Judge already answered variants with YandexGPT on the head node (compute nodes
# have no internet). Start it detached, so the laptop can go offline:
#
#   IDS=100-497 nohup bash runs_cluster/judge_variants.sh oracle_docs oracle_facts \
#       > ../logs/judge_variants.log 2>&1 < /dev/null &
#
# Environment (defaults in brackets): IDS [100-497], DONE_TAG [judge_variants]
set -uo pipefail

IDS="${IDS:-100-497}"
DONE_TAG="${DONE_TAG:-judge_variants}"
W=/userspace/sse/dm_engine
log() { echo "$(date '+%F %T') $*"; }

cd "$W/natural_rag"
FOLDER="$(cat "$W/secrets/yandex_folder_id")"
export LLM_API_KEY="$(cat "$W/secrets/yandex_api_key")"
export GRAPHRAG_BENCH_ROOT="$W/GraphRAG-Benchmark" EVAL_PYTHON="$W/env_eval/bin/python"
export PYTHON=/userspace/sse/.conda/envs/ragu_dev/bin/python PYTHONUTF8=1 HOME=/userspace/sse
export PYTHONPATH="$W/natural_rag:$W/RAGU"
export PASS="${PASS:-yandex}" JUDGE_WRAPPER=runs_local/judge_yandex.py JUDGE_CONCURRENCY=8
export JUDGE_BASE_URL=https://llm.api.cloud.yandex.net/v1
export JUDGE_MODEL="gpt://$FOLDER/yandexgpt-5.1/latest"
export JUDGE_EMBEDDING_MODEL="emb://$FOLDER/text-search-query/latest"
export DATASET="${DATASET:-musique}" INDEX_MODEL="${INDEX_MODEL:-gpt-oss-20b}"

for variant in "$@"; do
  log "judge $variant"
  bash runs_local/eval_graphrag_bench.sh "$variant" "${IDS%-*}" "${IDS#*-}" >> "$W/logs/judge_$variant.log" 2>&1
  log "judged $variant rc=$?"
done
touch "$W/logs/${DONE_TAG}.done"
log "all judged"
