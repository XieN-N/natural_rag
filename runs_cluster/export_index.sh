#!/bin/bash

# ============================================================
# Упаковать индекс Wikontic для вывоза с кластера.
#
# Кладёт в архив всё, что нужно для генерации ответов на другой машине, а не
# только storage Qdrant:
#
#   <RUN_ID>/manifest.json              что это за индекс и каким префиксом звать
#   <RUN_ID>/qdrant_storage/<RUN_ID>/   сам граф
#   <RUN_ID>/generated/<RUN_ID>/        index_summary.json, index_timing.jsonl
#   <RUN_ID>/datasets/<dataset>/        если датасета нет в git
#   <RUN_ID>/main.log.gz                улика для NO TRIPLETS STORED
#
# Датасет обязателен, потому что answers/<i>.txt нумеруются по позиции вопроса
# в датасете: другой порядок вопросов молча сдвинет все ответы. generated/ в
# .gitignore, поэтому цифры фронта 1 тоже надо везти руками.
#
# Прогоны заканчиваются в разное время, поэтому обычный режим — забрать один
# конкретный бенчмарк, не дожидаясь остальных:
#
#   ./runs_cluster/export_index.sh --list           # что готово к вывозу
#   ./runs_cluster/export_index.sh <RUN_ID>         # один бенчмарк
#   ./runs_cluster/export_index.sh <RUN_ID> <RUN_ID>
#   ./runs_cluster/export_index.sh --all            # все разом
#
# Запускать на login-ноде, когда job уже завершился: Qdrant не должен писать
# в директорию во время упаковки.
# ============================================================

set -uo pipefail

project_root="${PROJECT_ROOT:-/userspace/sse/natural_rag}"
QDRANT_STORAGE_ROOT="${QDRANT_STORAGE_ROOT:-/userspace/sse/qdrant_storage}"
EXPORT_DIR="${EXPORT_DIR:-/userspace/sse/index_export}"
WITH_DATASET="${WITH_DATASET:-auto}"   # auto | always | never

usage() {
    echo "Использование: $0 <RUN_ID> [RUN_ID ...]   # по одному бенчмарку"
    echo "               $0 --list                  # что готово к вывозу"
    echo "               $0 --all                   # все прогоны разом"
    echo
    echo "Флаги: --no-dataset | --with-dataset"
    echo
    echo "Доступные storage-директории:"
    ls -1 "${QDRANT_STORAGE_ROOT}" 2>/dev/null | grep -v '^_' | sed 's/^/  /'
    exit 1
}

# Прогоны заканчиваются в разное время: показываем статус каждого, чтобы было
# видно, что уже можно забирать, а что ещё считается.
list_runs() {
    # RUN_ID последним: он бывает под 70 символов, и если поставить его первым,
    # он разъезжает колонки с числами.
    printf "%-12s %8s %7s %8s  %s\n" "СТАТУС" "ДОКОВ" "ПУСТЫХ" "РАЗМЕР" "RUN_ID"
    for run_id in $(ls -1 "${QDRANT_STORAGE_ROOT}" 2>/dev/null | grep -v '^_'); do
        storage="${QDRANT_STORAGE_ROOT}/${run_id}"
        [ -d "${storage}" ] || continue

        status="?"
        if [ -f "${storage}/.owner" ]; then
            owner_job=$(cat "${storage}/.owner" 2>/dev/null)
            if [ -n "${owner_job}" ] && [ -n "$(squeue -h -j "${owner_job}" 2>/dev/null)" ]; then
                status="ИДЁТ ${owner_job}"
            fi
        fi

        summary=$(find "${project_root}/generated/${run_id}" -name index_summary.json 2>/dev/null | head -1)
        read -r s_status n_docs empty <<<"$(python - "${summary}" <<'PY'
import json, os, sys
path = sys.argv[1] if len(sys.argv) > 1 else ""
data = {}
if path and os.path.exists(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        pass
print(data.get("status") or "?", data.get("n_docs", "?"), data.get("empty_docs", 0) or 0)
PY
)"
        [ "${status}" = "?" ] && status="${s_status}"
        size=$(du -sh "${storage}" 2>/dev/null | cut -f1)
        printf "%-12s %8s %7s %8s  %s\n" "${status}" "${n_docs}" "${empty}" "${size}" "${run_id}"
    done
    echo
    echo "Забрать один:  $0 <RUN_ID>"
    echo "status=running и job не в очереди — индекс частичный, но рабочий;"
    echo "дособрать можно тем же sbatch (--resume включён)."
}

RUN_IDS=()
ALL=0
LIST=0
while [ $# -gt 0 ]; do
    case "$1" in
        --all)          ALL=1 ;;
        --list|-l)      LIST=1 ;;
        --no-dataset)   WITH_DATASET="never" ;;
        --with-dataset) WITH_DATASET="always" ;;
        -h|--help)      usage ;;
        -*)             echo "Неизвестный флаг: $1"; usage ;;
        *)              RUN_IDS+=("$1") ;;
    esac
    shift
done

if [ ${LIST} -eq 1 ]; then
    list_runs
    exit 0
fi

if [ ${ALL} -eq 1 ]; then
    mapfile -t RUN_IDS < <(ls -1 "${QDRANT_STORAGE_ROOT}" 2>/dev/null | grep -v '^_')
fi
[ ${#RUN_IDS[@]} -eq 0 ] && usage

mkdir -p "${EXPORT_DIR}"

for RUN_ID in "${RUN_IDS[@]}"; do
    storage="${QDRANT_STORAGE_ROOT}/${RUN_ID}"
    if [ ! -d "${storage}" ]; then
        echo "ПРОПУСК: нет ${storage}"
        echo "  Что есть на самом деле — $0 --list"
        continue
    fi

    if [ -f "${storage}/.owner" ]; then
        owner_job=$(cat "${storage}/.owner" 2>/dev/null)
        if [ -n "${owner_job}" ] && [ -n "$(squeue -h -j "${owner_job}" 2>/dev/null)" ]; then
            echo "ПРОПУСК: ${RUN_ID} — идёт job ${owner_job}, архив был бы несогласованным"
            continue
        fi
    fi

    echo "=== ${RUN_ID} ==="
    echo -n "  размер индекса: "; du -sh "${storage}" | cut -f1

    stage="${EXPORT_DIR}/.stage_${RUN_ID}"
    rm -rf "${stage}"
    mkdir -p "${stage}/${RUN_ID}/qdrant_storage" "${stage}/${RUN_ID}/generated"

    # index_summary.json лежит в generated/<RUN_ID>/<датасет>/<модель>/
    summary=$(find "${project_root}/generated/${RUN_ID}" -name index_summary.json 2>/dev/null | head -1)

    manifest="${stage}/${RUN_ID}/manifest.json"
    dataset_name=$(python - "${RUN_ID}" "${storage}" "${summary}" "${manifest}" <<'PY'
import json, sys, os
run_id, storage, summary_path, out = sys.argv[1:5]
summary = {}
if summary_path and os.path.exists(summary_path):
    try:
        summary = json.load(open(summary_path, encoding="utf-8"))
    except Exception as exc:
        print(f"  предупреждение: не прочитался {summary_path}: {exc}", file=sys.stderr)

if not summary.get("collection_prefix"):
    # Без него пришлось бы угадывать префикс коллекций, а угадать нельзя:
    # он собирается как <датасет>__<модель>__<режим>__<scope>. Бандл с неверным
    # префиксом отвалится на preflight уже после scp — лучше сказать сейчас.
    print(f"  нет index_summary.json с collection_prefix "
          f"(искали в generated/{run_id}/). Это не прогон Wikontic либо "
          f"generated/ потерян — экспортировать нечего", file=sys.stderr)
    sys.exit(2)

prefix = summary["collection_prefix"]
mode = summary.get("mode")
# Имена коллекций захардкожены в wikontic; PrefixedBackend склеивает их через
# двойное подчёркивание (natural_rag/wikontic_prefix.py). Список нужен, чтобы
# preflight на ноутбуке мог проверить, что граф действительно на месте, до
# первого обращения к платному API.
#
# Обязательными считаем только те, без которых ответы заведомо пустые. Набор
# коллекций у structured и dynamic немного разный, и валить прогон из-за
# необязательной коллекции — хуже, чем не проверить её.
required = ["triplets", "initial_triplets"]
optional = ["entity_aliases", "property_aliases", "filtered_triplets"]

manifest = {
    "run_id": run_id,
    # Точно то, что нужно передать в --collection-prefix на другой машине.
    "collection_prefix": prefix,
    "required_collections": [f"{prefix}__{name}" for name in required],
    "optional_collections": [f"{prefix}__{name}" for name in optional],
    "dataset": summary.get("dataset"),
    "index_model": summary.get("model"),
    "mode": mode,
    "scope": summary.get("scope"),
    "status": summary.get("status"),
    "n_docs": summary.get("n_docs"),
    "total_units": summary.get("total_units"),
    "empty_docs": summary.get("empty_docs"),
    "failures": summary.get("failures"),
    "llm_calls": summary.get("llm_calls"),
    "wall_seconds": summary.get("wall_seconds"),
    "qdrant_storage_subdir": f"qdrant_storage/{os.path.basename(storage)}",
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
for key in ("dataset", "index_model", "mode", "scope", "status", "n_docs", "empty_docs"):
    print(f"  {key}: {manifest[key]}", file=sys.stderr)

# Прогоны заканчиваются в разное время, и забрать недосчитанный индекс легко.
# Статус пишется в index_summary.json при старте ("running") и переписывается на
# выходе, так что "running" у мёртвого job'а = job убили на середине.
if manifest["status"] != "done":
    print(f"  ВНИМАНИЕ: статус {manifest['status']!r}, индекс неполный. "
          f"Дособрать: тот же sbatch, --resume включён", file=sys.stderr)
total = manifest.get("total_units")
n_docs = manifest.get("n_docs")
if isinstance(total, int) and isinstance(n_docs, int) and n_docs < total:
    print(f"  ВНИМАНИЕ: проиндексировано {n_docs} из {total} документов", file=sys.stderr)
if manifest["empty_docs"]:
    print(f"  ВНИМАНИЕ: {manifest['empty_docs']} документов не попали в граф", file=sys.stderr)
# stdout — только имя датасета, его читает шелл
print(summary.get("dataset") or "")
PY
)
    manifest_status=$?
    # Без манифеста бандл бесполезен: answer_from_index.py на другой машине
    # откажется его брать. Лучше не отдать архив вовсе, чем отдать сломанный —
    # обнаружится это иначе уже после scp.
    if [ ${manifest_status} -ne 0 ] || [ ! -s "${manifest}" ]; then
        echo "  ПРОПУСК: не собрался manifest.json для ${RUN_ID}, архив не создаём"
        rm -rf "${stage}"
        continue
    fi

    # Хардлинки вместо копии: storage бывает в гигабайтах, а /userspace одна ФС.
    # Если хардлинки не поддерживаются — обычная копия.
    if ! cp -al "${storage}" "${stage}/${RUN_ID}/qdrant_storage/${RUN_ID}" 2>/dev/null; then
        echo "  (хардлинки недоступны, копируем)"
        cp -r "${storage}" "${stage}/${RUN_ID}/qdrant_storage/${RUN_ID}" || {
            echo "  ОШИБКА при подготовке ${RUN_ID}"; rm -rf "${stage}"; continue; }
    fi
    rm -f "${stage}/${RUN_ID}/qdrant_storage/${RUN_ID}/.owner"

    if [ -d "${project_root}/generated/${RUN_ID}" ]; then
        cp -r "${project_root}/generated/${RUN_ID}" "${stage}/${RUN_ID}/generated/${RUN_ID}"
    else
        echo "  предупреждение: нет generated/${RUN_ID} — цифры фронта 1 не поедут"
    fi

    # Датасет везём, если его нет в git: ровно случай graphrag_bench_*, который
    # собирается на login-ноде и в репозиторий не попадает.
    if [ -n "${dataset_name}" ] && [ "${WITH_DATASET}" != "never" ]; then
        dataset_dir="${project_root}/datasets/${dataset_name}"
        tracked=0
        if [ "${WITH_DATASET}" = "auto" ]; then
            git -C "${project_root}" ls-files --error-unmatch "datasets/${dataset_name}" >/dev/null 2>&1 && tracked=1
        fi
        if [ ! -d "${dataset_dir}" ]; then
            echo "  предупреждение: нет ${dataset_dir}"
        elif [ ${tracked} -eq 1 ]; then
            echo "  датасет ${dataset_name} есть в git — не пакуем"
        else
            echo "  пакуем датасет ${dataset_name}"
            mkdir -p "${stage}/${RUN_ID}/datasets"
            cp -r "${dataset_dir}" "${stage}/${RUN_ID}/datasets/${dataset_name}"
            rm -rf "${stage}/${RUN_ID}/datasets/${dataset_name}/.hf_cache"
        fi
    fi

    main_log="${project_root}/logs/${RUN_ID}/main.log"
    if [ -f "${main_log}" ]; then
        gzip -c "${main_log}" > "${stage}/${RUN_ID}/main.log.gz"
    fi

    archive="${EXPORT_DIR}/${RUN_ID}.tar.gz"
    echo "  пакуем -> ${archive}"
    tar czf "${archive}" -C "${stage}" "${RUN_ID}" || {
        echo "  ОШИБКА при упаковке"; rm -rf "${stage}"; continue; }
    rm -rf "${stage}"
    du -sh "${archive}" | sed 's/^/  /'
done

echo
echo "Готово. Забирать отсюда:"
echo "  scp 'sse@<кластер>:${EXPORT_DIR}/*.tar.gz' ~/wikontic_bundles/"
echo "Дальше — runs_local/README.md"
