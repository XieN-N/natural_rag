#!/bin/bash
# Пресет: переиндексация graphrag_bench_medical на gpt-oss-20b (dynamic, без
# ответов — ответы считаются локально, см. runs_local/README.md).
#
# Запускать голым sbatch, ничего не экспортируя:
#   sbatch runs_cluster/launch_wikontic_gpt.sh
#
# Всё, что определяет прогон — датасет, режим, модель, нода — зашито ниже.
# Забытый export в сессии раньше означал musique/structured вместо нужного —
# молча, без единой ошибки (выяснялось через сутки по содержимому generated/).
#
# Модель: gpt-oss-20b, нода: ngpu07. Три модели разведены по нодам не для
# скорости, а потому что BIG_LLM_PORT фиксирован и pkill -f vllm в базовом
# скрипте бьёт по всем своим процессам на ноде: два таких job'а на одной ноде
# убили бы vLLM друг друга.
#
# Полный набор настроек — в runs_cluster/run_universal_wikontic.sh.

#SBATCH --job-name=wikontic_gpt
#SBATCH --partition=a100
#SBATCH --nodelist=ngpu07
#SBATCH --error="logs/%x-%j.err"
#SBATCH --output="logs/%x-%j.log"

export DATASET_NAME=graphrag_bench_medical
export BIG_LLM_MODEL="/userspace/kms/models/gpt-oss-20b"
export BIG_LLM_NAME="gpt-oss-20b"
export WIKONTIC_MODE=dynamic
export DO_ANSWER=0

source "$(dirname "$0")/run_universal_wikontic.sh"
