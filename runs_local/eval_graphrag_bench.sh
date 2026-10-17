#!/bin/bash
# Judge a variant's answers with the GraphRAG-Benchmark protocol, only where needed.
#
#   runs_local/eval_graphrag_bench.sh <variant> [first_question] [last_question]
#
# Builds graphrag_bench_input.json for generated/ragu_<dataset>__<variant>, then
# judges only the questions in [first, last] that no eval_results*.json of the
# variant covers yet, writing eval_results_<timestamp>.json. Up to three rounds,
# so questions lost to connection errors are judged again instead of silently
# dropped. Re-running never re-judges (and never re-pays for) covered questions.
# runs_local/compare_runs.py averages all eval_results*.json of a variant.
#
# A second, independent judge pass: PASS=pass2 counts only eval_results_pass2*.json
# as done and writes eval_results_pass2_<timestamp>.json.
#
# Environment (defaults in brackets):
#   LLM_API_KEY          key for the judge endpoint (required; the name the eval scripts expect)
#   GRAPHRAG_BENCH_ROOT  checkout of bond005/GraphRAG-Benchmark (required)
#   EVAL_PYTHON          [python]  interpreter with the GraphRAG-Benchmark requirements
#   JUDGE_BASE_URL       [https://api.vsellm.ru/v1]
#   JUDGE_MODEL          [gemini-3-flash-preview]   JUDGE_EMBEDDING_MODEL [text-embedding-3-small]
#   DATASET              [musique]  INDEX_MODEL [gpt-oss-20b]
#   PYTHON               [python]   interpreter for natural_rag scripts
#   PASS                 []         judge pass tag, see above
set -euo pipefail

VARIANT="${1:?variant name}"
FROM="${2:-0}"
TO="${3:-1000000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATASET="${DATASET:-musique}"
INDEX_MODEL="${INDEX_MODEL:-gpt-oss-20b}"
: "${LLM_API_KEY:?set LLM_API_KEY}"
: "${GRAPHRAG_BENCH_ROOT:?set GRAPHRAG_BENCH_ROOT}"
PY="${PYTHON:-python}"
OUT="generated/ragu_${DATASET}__${VARIANT}"
RUN_DIR="${ROOT}/${OUT}/${DATASET}/${INDEX_MODEL}"
PREFIX="eval_results${PASS:+_${PASS}}"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

win_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else echo "$1"; fi; }

cd "$ROOT"
PYTHONPATH="$ROOT" "$PY" runs/build_graphrag_bench_input.py --dataset-path "datasets/${DATASET}" \
  --output-dir "$OUT" --index-model "$INDEX_MODEL" --skip-missing

for round in 1 2 3; do
  MISSING="${RUN_DIR}/graphrag_bench_input.missing.json"
  N=$("$PY" - "$RUN_DIR" "$MISSING" "$FROM" "$TO" "${ROOT}/datasets/${DATASET}/questions.jsonl" "$PREFIX" <<'PY'
import glob, json, os, sys
run, dst, lo, hi, questions, prefix = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
items = json.load(open(run + "/graphrag_bench_input.json", encoding="utf-8"))
done = set()
for path in glob.glob(run + "/" + prefix + "*.json"):
    for section in json.load(open(path, encoding="utf-8")).values():
        done.update(item["id"] for item in section.get("detailed", []))
if os.path.exists(questions):
    position = {json.loads(line)["id"]: i for i, line in enumerate(open(questions, encoding="utf-8"))}
else:  # without a jsonl, the input file's order (dataset order) stands in for the index
    position = {it["id"]: i for i, it in enumerate(items)}
todo = [it for it in items if lo <= position.get(it["id"], -1) <= hi and it["id"] not in done]
json.dump(todo, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(len(todo))
PY
)
  echo "round ${round}: ${N} questions to judge"
  [ "$N" = "0" ] && break
  OUT_FILE="${RUN_DIR}/${PREFIX}_$(date +%s).json"
  (cd "$GRAPHRAG_BENCH_ROOT" && "${EVAL_PYTHON:-python}" -m Evaluation.generation_eval --mode API \
    --model "${JUDGE_MODEL:-gemini-3-flash-preview}" --base_url "${JUDGE_BASE_URL:-https://api.vsellm.ru/v1}" \
    --embedding_model "${JUDGE_EMBEDDING_MODEL:-text-embedding-3-small}" \
    --embedding_base_url "${JUDGE_BASE_URL:-https://api.vsellm.ru/v1}" \
    --data_file "$(win_path "$MISSING")" --output_file "$(win_path "$OUT_FILE")" \
    --detailed_output --max_concurrent 6) || true
done
