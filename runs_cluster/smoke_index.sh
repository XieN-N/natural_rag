#!/usr/bin/env bash
# Проверить модель на десяти документах, прежде чем ставить в очередь на сутки.
#
# Полная индексация graphrag_bench_medical — около 22 часов и 25 тысяч вызовов
# LLM. Всё, что делает её бессмысленной, видно на первых документах: модель, чьи
# ответы не парсятся (граф выходит пустым), модель, сыплющая пустыми сущностями,
# неподнятый vLLM, неверный путь к contriever. Этот скрипт ловит такое за
# минуты.
#
# Индексирует во ВРЕМЕННЫЙ префикс `<RUN_ID>__smoke`, чтобы не смешивать пробу
# с боевым индексом, и заканчивает проверкой целостности.
#
# Смоучится тот же самый скрипт, который потом пойдёт в очередь — иначе проба
# проверяет не то, что запускается. Задаётся через SCRIPT:
#
#   SCRIPT=launch_wikontic_qwen.sh ./runs_cluster/smoke_index.sh
#
# Скрипт НЕ уходит в SLURM сам: он выполняет целевой файл через bash здесь же.
# На login-узле vLLM не поднимется, поэтому запускать через srun, на той же
# ноде, что зашита в целевом скрипте:
#
#   srun -p a100 -w ngpu06 bash -c \
#     'SCRIPT=launch_wikontic_qwen.sh ./runs_cluster/smoke_index.sh'
#
# Ненулевой код возврата означает: в очередь не ставить.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SCRIPT="${SCRIPT:-run_universal_wikontic.sh}"
target="${here}/${SCRIPT}"
if [ ! -f "${target}" ]; then
    echo "ERROR: нет ${target}"
    echo "Доступные:"
    ls -1 "${here}"/run_universal_wikontic*.sh | xargs -n1 basename | sed 's/^/  /'
    exit 1
fi

# Дефолты берём из целевого скрипта, а не из своих: смысл смоука в том, чтобы
# проверить ровно ту конфигурацию, которая пойдёт в очередь. Своё значение здесь
# молча разошлось бы с боевым — именно так и появляется зелёная проба на dynamic
# при боевом structured.
# read_default VAR — значение по умолчанию из строки вида VAR="${VAR:-значение}".
# Через awk и -v, а не sed: имя переменной попадает в паттерн как обычный текст,
# и не нужно экранировать $ и { через кавычки шелла — там ошибиться легче, чем
# заметить (пустое значение вместо разбора выглядит как «переменная не задана»).
read_default() {
    awk -v name="$1" '
        index($0, name "=\"${" name ":-") == 1 {
            line = $0
            sub(/^[^{]*\{[^:]*:-/, "", line)   # отрезать VAR="${VAR:-
            sub(/\}.*/, "", line)              # отрезать }" и комментарий
            print line
            exit
        }' "${target}"
}

SMOKE_DOCS="${SMOKE_DOCS:-10}"
DATASET_NAME="${DATASET_NAME:-$(read_default DATASET_NAME)}"
BIG_LLM_NAME="${BIG_LLM_NAME:-$(read_default BIG_LLM_NAME)}"
BIG_LLM_MODEL="${BIG_LLM_MODEL:-$(read_default BIG_LLM_MODEL)}"
WIKONTIC_MODE="${WIKONTIC_MODE:-$(read_default WIKONTIC_MODE)}"
WIKONTIC_SCOPE="${WIKONTIC_SCOPE:-$(read_default WIKONTIC_SCOPE)}"

for var in DATASET_NAME BIG_LLM_NAME BIG_LLM_MODEL WIKONTIC_MODE WIKONTIC_SCOPE; do
    if [ -z "${!var}" ]; then
        echo "ERROR: не удалось определить ${var} из ${SCRIPT} — задайте явно"
        exit 1
    fi
done

base_run_id="${RUN_ID:-wikontic_${DATASET_NAME}_${BIG_LLM_NAME}_${WIKONTIC_MODE}_${WIKONTIC_SCOPE}}"

echo "=== Смоук индексации: ${SMOKE_DOCS} документов ==="
echo "=== Скрипт:   ${SCRIPT}"
echo "=== Датасет:  ${DATASET_NAME}, режим ${WIKONTIC_MODE}/${WIKONTIC_SCOPE}"
echo "=== Модель:   ${BIG_LLM_NAME}  (${BIG_LLM_MODEL})"
echo "=== Префикс:  ${base_run_id}__smoke (временный)"

if [ ! -d "${BIG_LLM_MODEL}" ]; then
    echo "ERROR: нет каталога модели ${BIG_LLM_MODEL}"
    echo "Пути на Linux регистрозависимы — сверьте написание."
    exit 1
fi

# Отдельное хранилище Qdrant: проба не должна касаться боевых коллекций даже
# при совпадении имён.
RUN_ID="${base_run_id}__smoke" \
QDRANT_STORAGE_ID="${base_run_id}__smoke" \
LIMIT_DOCS="${SMOKE_DOCS}" \
DO_INDEX=1 \
DO_ANSWER=0 \
DATASET_NAME="${DATASET_NAME}" \
BIG_LLM_NAME="${BIG_LLM_NAME}" \
BIG_LLM_MODEL="${BIG_LLM_MODEL}" \
WIKONTIC_MODE="${WIKONTIC_MODE}" \
WIKONTIC_SCOPE="${WIKONTIC_SCOPE}" \
    bash "${target}"
status=$?

echo
if [ ${status} -eq 0 ]; then
    echo "=== СМОУК ПРОЙДЕН. Модель ${BIG_LLM_NAME} пригодна, можно ставить полный прогон. ==="
    echo "Временные коллекции ${base_run_id}__smoke можно удалить."
else
    echo "=== СМОУК ПРОВАЛЕН (код ${status}). В очередь не ставить. ==="
    echo "Смотрите строки 'Graph health' и 'ИНДЕКС НЕПРИГОДЕН' в логе прогона."
    echo "Пустой граф при живом vLLM почти всегда означает, что ответы модели"
    echo "не парсятся — ищите 'Failed to parse JSON' и 'NO TRIPLETS STORED'."
fi
exit ${status}
