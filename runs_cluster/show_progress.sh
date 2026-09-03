#!/bin/bash
#
# Что сейчас происходит: очередь SLURM + живая таблица по скорости индексации.
# Работает на незавершённых прогонах — числа берутся из index_timing.jsonl.
#
#   ./runs_cluster/show_progress.sh          # один снимок
#   ./runs_cluster/show_progress.sh --watch  # обновлять каждые 60 секунд

set -uo pipefail
cd "$(dirname "$0")/.."

snapshot() {
    echo "=============== $(date '+%Y-%m-%d %H:%M:%S') ==============="
    echo
    echo "--- очередь ---"
    squeue -u "$(whoami)" -o "%.10i %.14j %.9P %.8T %.11M %.6D %R" 2>/dev/null || echo "squeue недоступен"
    echo
    echo "--- индексация ---"
    python runs/index_stats.py generated 2>/dev/null || echo "прогонов пока нет"
    echo
    echo "--- оценка ---"
    found=0
    for f in generated/*/*/*/eval_results.json generated/*/*/eval_results.json; do
        [ -f "$f" ] || continue
        found=1
        python -c "
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))['summary']
print('  {:<42} answers={:<5} em={:<6} f1={:<6} judge={}'.format(
    sys.argv[1].split('generated/')[-1][:42],
    d.get('n_answers'), d.get('em'), d.get('f1'), d.get('judge_accuracy')))
" "$f" 2>/dev/null
    done
    [ "$found" = "0" ] && echo "  результатов оценки пока нет"
}

if [ "${1:-}" = "--watch" ]; then
    while true; do
        clear
        snapshot
        echo
        echo "(обновление через 60 с, Ctrl-C для выхода)"
        sleep 60
    done
else
    snapshot
fi
