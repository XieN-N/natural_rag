#!/bin/bash
# Пресет: переиндексация graphrag_bench_medical на meno-lite-0.1 (dynamic, без
# ответов — ответы считаются локально, см. runs_local/README.md).
#
# Запускать голым sbatch, ничего не экспортируя:
#   sbatch runs_cluster/launch_wikontic_meno.sh
#
# Всё, что определяет прогон — датасет, режим, модель, нода — зашито ниже
# (почему это важно — см. комментарий в launch_wikontic_gpt.sh).
#
# Модель: meno-lite-0.1, нода: ngpu05. Ноды разведены из-за фиксированного
# BIG_LLM_PORT и fan-out pkill в базовом скрипте.
#
# Полный набор настроек — в runs_cluster/run_universal_wikontic.sh.

#SBATCH --job-name=wikontic_meno
#SBATCH --partition=a100
#SBATCH --nodelist=ngpu05
#SBATCH --error="logs/%x-%j.err"
#SBATCH --output="logs/%x-%j.log"

export DATASET_NAME=graphrag_bench_medical
export BIG_LLM_MODEL="/userspace/kms/models/meno-lite-0.1"
export BIG_LLM_NAME="meno-lite-0.1"
export WIKONTIC_MODE=dynamic
export DO_ANSWER=0

source "$(dirname "$0")/run_universal_wikontic.sh"
