#!/usr/bin/env bash
# Reader ceiling on an ideal context (runs_local/oracle_reader.py), Meno-Lite on vLLM.
#
#   sbatch runs_cluster/oracle_reader.sbatch [ids] [kinds...]
#
# Defaults: questions 100-497, kinds docs facts noisy. A smoke on the first ten
# questions runs first and stops the job if they are not answered. Answered
# questions are skipped, so resubmitting resumes. Judge afterwards, outside the
# compute nodes (they have no internet), with runs_local/eval_graphrag_bench.sh.
#
#SBATCH --job-name=dm_oracle
#SBATCH --partition=a100
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --time=04:00:00
#SBATCH --chdir=/userspace/sse/dm_engine/natural_rag
#SBATCH --output=/userspace/sse/dm_engine/logs/oracle_%j.log
#SBATCH --error=/userspace/sse/dm_engine/logs/oracle_%j.err
set -uo pipefail

IDS="${1:-100-497}"
shift || true
KINDS=("$@")
[ "${#KINDS[@]}" -gt 0 ] || KINDS=(docs facts noisy)

W=/userspace/sse/dm_engine
# torch must match the node driver (CUDA 12.6): env ragu has a CUDA 13.0 build and fails.
SERVE_ENV=/userspace/sse/.conda/envs/gb_ragu
RUN_ENV=/userspace/sse/.conda/envs/ragu_dev
MODEL=/userspace/kms/models/meno-lite-0.1
PORT=8711

export HOME=/userspace/sse
export HF_HOME="$W/cache/hf" XDG_CACHE_HOME="$W/cache/xdg" VLLM_CACHE_ROOT="$W/cache/vllm"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_USE_FLASHINFER_SAMPLER=0 PYTHONUTF8=1
export CUDA_VISIBLE_DEVICES=0
mkdir -p "$HF_HOME" "$XDG_CACHE_HOME" "$VLLM_CACHE_ROOT" "$W/logs"

hostname
nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv,noheader

"$SERVE_ENV/bin/vllm" serve "$MODEL" --served-model-name meno-lite-0.1 \
  --host 127.0.0.1 --port "$PORT" --max-model-len 32768 --gpu-memory-utilization 0.85 \
  --enable-prefix-caching --dtype bfloat16 --max-logprobs 20 \
  > "$W/logs/vllm_${SLURM_JOB_ID}.log" 2>&1 &
VLLM_PID=$!
trap 'kill "$VLLM_PID" 2>/dev/null' EXIT

up=0
for _ in $(seq 1 180); do
  if curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/v1/models" | grep -q 200; then up=1; break; fi
  kill -0 "$VLLM_PID" 2>/dev/null || break
  sleep 10
done
if [ "$up" != 1 ]; then
  echo "vLLM did not come up"; tail -30 "$W/logs/vllm_${SLURM_JOB_ID}.log"; exit 1
fi
echo "vLLM up: $(date '+%F %T')"

# The decision model reads first-token logprobs: stop now if the server does not return them.
PROBE=$(curl -s "http://127.0.0.1:${PORT}/v1/chat/completions" -H 'Content-Type: application/json' -d '{"model":"meno-lite-0.1","messages":[{"role":"user","content":"Answer Y or N: is 2+2=4?"}],"max_tokens":1,"logprobs":true,"top_logprobs":20}')
if ! echo "$PROBE" | grep -Eq '"top_logprobs": *\[ *\{'; then
  echo "logprobs probe failed: ${PROBE:0:400}"; exit 1
fi
echo "logprobs ok"

export PYTHONPATH="$W/natural_rag:$W/RAGU"
PY="$RUN_ENV/bin/python"
START="${IDS%-*}"
SMOKE="${START}-$((START + 9))"
"$PY" -u runs_local/oracle_reader.py docs --ids "$SMOKE" --base-url "http://127.0.0.1:${PORT}/v1" || exit 1
ANSWERED=$(ls generated/ragu_musique__meno_oracle_docs/musique/gpt-oss-20b/answers/*.txt 2>/dev/null | wc -l)
if [ "$ANSWERED" -lt 10 ]; then
  echo "smoke failed: $ANSWERED answers"; exit 1
fi
echo "smoke ok: $(date '+%F %T')"

"$PY" -u runs_local/oracle_reader.py "${KINDS[@]}" --ids "$IDS" --base-url "http://127.0.0.1:${PORT}/v1"
RC=$?
echo "done rc=$RC: $(date '+%F %T')"
[ "$RC" = 0 ] && touch "$W/logs/oracle_${IDS}.done"
exit "$RC"
