#!/bin/bash
# Пресет: переиндексация graphrag_bench_medical на Qwen2.5-7B-Instruct
# (dynamic, без ответов — ответы считаются локально, см. runs_local/README.md).
#
# Запускать голым sbatch, ничего не экспортируя:
#   sbatch runs_cluster/launch_wikontic_qwen.sh
#
# Всё, что определяет прогон — датасет, режим, модель, нода — зашито ниже
# (почему это важно — см. комментарий в launch_wikontic_gpt.sh).
#
# Модель: Qwen2.5-7B-Instruct, нода: ngpu06. Ноды разведены из-за
# фиксированного BIG_LLM_PORT и fan-out pkill в базовом скрипте.
#
# Полный набор настроек — в runs_cluster/run_universal_wikontic.sh.

#SBATCH --job-name=wikontic_qwen
#SBATCH --partition=a100
#SBATCH --nodelist=ngpu06
#SBATCH --error="logs/%x-%j.err"
#SBATCH --output="logs/%x-%j.log"

export DATASET_NAME=graphrag_bench_medical
export BIG_LLM_MODEL="/userspace/kms/models/Qwen2.5-7B-Instruct"
export BIG_LLM_NAME="Qwen2.5-7B-Instruct"
export WIKONTIC_MODE=dynamic
export DO_ANSWER=0

source "$(dirname "$0")/run_universal_wikontic.sh"
