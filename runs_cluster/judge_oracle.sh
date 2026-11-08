#!/usr/bin/env bash
# Wait for an oracle_reader.sbatch job, then judge its variants with YandexGPT.
# Runs on the head node (compute nodes have no internet), so start it detached:
#
#   nohup bash runs_cluster/judge_oracle.sh <job id> > ../logs/judge_oracle.log 2>&1 < /dev/null &
#
# Environment (defaults in brackets):
#   IDS       [100-497]
#   KINDS     [docs facts noisy]
#   PREFIX    [meno_oracle]
set -uo pipefail

JOB="${1:?slurm job id}"
IDS="${IDS:-100-497}"
KINDS="${KINDS:-docs facts noisy}"
PREFIX="${PREFIX:-meno_oracle}"
W=/userspace/sse/dm_engine
log() { echo "$(date '+%F %T') $*"; }

while squeue -h -j "$JOB" 2>/dev/null | grep -q .; do sleep 120; done
if [ ! -f "$W/logs/oracle_${IDS}.done" ]; then
  log "job $JOB ended without oracle_${IDS}.done, see $W/logs/oracle_${JOB}.log"
  exit 1
fi
log "job $JOB finished"

cd "$W/natural_rag"
FOLDER="$(cat "$W/secrets/yandex_folder_id")"
export LLM_API_KEY="$(cat "$W/secrets/yandex_api_key")"
export GRAPHRAG_BENCH_ROOT="$W/GraphRAG-Benchmark" EVAL_PYTHON="$W/env_eval/bin/python"
export PYTHON=/userspace/sse/.conda/envs/ragu_dev/bin/python PYTHONUTF8=1 HOME=/userspace/sse
export PYTHONPATH="$W/natural_rag:$W/RAGU"
export PASS=yandex JUDGE_WRAPPER=runs_local/judge_yandex.py JUDGE_CONCURRENCY=8
export JUDGE_BASE_URL=https://llm.api.cloud.yandex.net/v1
export JUDGE_MODEL="gpt://$FOLDER/yandexgpt-5.1/latest"
export JUDGE_EMBEDDING_MODEL="emb://$FOLDER/text-search-query/latest"
export DATASET=musique INDEX_MODEL=gpt-oss-20b

for kind in $KINDS; do
  log "judge ${PREFIX}_$kind"
  bash runs_local/eval_graphrag_bench.sh "${PREFIX}_$kind" "${IDS%-*}" "${IDS#*-}" >> "$W/logs/judge_${PREFIX}_$kind.log" 2>&1
  log "judged ${PREFIX}_$kind rc=$?"
done
touch "$W/logs/judge_${PREFIX}_${IDS}.done"
log "all judged"
