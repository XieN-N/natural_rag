# Wikontic vs RAGU на кластере: полная инструкция

Сравнение Wikontic и RAGU на моделях Сбера: **скорость индексации** (фронт 1) и
**качество** на musique / bioasq / graphrag-bench (фронт 3).

Хранилище — **Qdrant, запущенный как обычный пользовательский процесс из статического
бинаря**. Docker и root не нужны. MongoDB не используется: Wikontic'у нужен Atlas
Vector Search (`createSearchIndex` / `$vectorSearch`), которого нет в MongoDB
Community, а `mongodb-atlas-local` — docker-образ.

Всё под `/userspace/sse`, ничего в `/home`.

---

## Состав папки

| Скрипт | Что делает |
|---|---|
| `run_universal.sh` | LightRAG / FastGraphRAG на любом датасете: vLLM + индексация + ответы + судья (заменил ~30 копий из бывшего `runs_universal/`) |
| `run_universal_wikontic.sh` | Wikontic на любом датасете (индексация + ответы) |
| `run_universal_ragu.sh` | RAGU на любом датасете |
| `launch_wikontic_gpt.sh` | пресет: graphrag_bench_medical × gpt-oss-20b × dynamic × ngpu07 |
| `launch_wikontic_meno.sh` | пресет: graphrag_bench_medical × meno-lite-0.1 × dynamic × ngpu05 |
| `launch_wikontic_qwen.sh` | пресет: graphrag_bench_medical × Qwen2.5-7B × dynamic × ngpu06 |
| `musique_wikontic_structured.sh` | musique, structured — индексация + ответы |
| `musique_wikontic_dynamic.sh` | musique, dynamic — индексация + ответы |
| `smoke_index.sh` | смоук-проверка индексации на 5 документах (не в очередь) |
| `build_ontology.sh` | разовая сборка Wikidata-онтологии (только для `structured`) |
| `eval_universal.sh` | судья: EM / F1 / accuracy + вход для GraphRAG-Benchmark |
| `show_progress.sh` | очередь + живая таблица скорости + результаты оценки |
| `export_index.sh` | упаковать индекс для вывоза (граф + манифест + цифры + датасет) |
| `retry_documents.py` | дозапуск отдельных документов после сбоя индексации |
| `time_phase.py` | замер длительности фаз прогона по логам |
| `graphbench_ragu.sh` / `graphbench_lightrag.sh` / `graphbench_hipporag.sh` | прогоны GraphRAG-Bench для соответствующих движков |

Ответы и оценка происходят не здесь, а на своей машине через API — см.
[`runs_local/README.md`](../runs_local/README.md).

`launch_*.sh` ставятся голым `sbatch` (весь прогон зашит внутри — так
случайный `export` в сессии не подменит датасет). Остальные универсальные
скрипты настраиваются блоком «НАСТРОЙКИ» в начале файла, и любую настройку
можно переопределить из окружения (SLURM пробрасывает его в job):

```bash
DATASET_NAME=bioasq WIKONTIC_MODE=dynamic sbatch runs_cluster/run_universal_wikontic.sh
```

```bash
sbatch --export=ALL,RAG_ENGINE=lightrag,DATASET_NAME=chegeka,BIG_LLM_MODEL=/userspace/kms/models/gpt-oss-20b,BIG_LLM_NAME=gpt-oss-20b runs_cluster/run_universal.sh
```

Бывшие копии `run_<датасет>_<модель>_<движок>.sh` заменены одним
`run_universal.sh`; эквивалентные запуски:

| Бывший скрипт | Эквивалент |
|---|---|
| `run_universal_gpt_20b_lightrag_chegeka.sh` | `sbatch --export=ALL,RAG_ENGINE=lightrag,DATASET_NAME=chegeka,BIG_LLM_MODEL=/userspace/kms/models/gpt-oss-20b,BIG_LLM_NAME=gpt-oss-20b runs_cluster/run_universal.sh` |
| `run_universal_gigachat-3.1-lightning_lightrag_multiq.sh` | `sbatch --export=ALL,RAG_ENGINE=lightrag,DATASET_NAME=multiq runs_cluster/run_universal.sh` (gigachat — модель по умолчанию не тут: подставьте BIG_LLM_MODEL/BIG_LLM_NAME) |
| `run_bl_qwen_bl_lightrag.sh` | `sbatch --export=ALL,RAG_ENGINE=lightrag,DATASET_NAME=bl,BIG_LLM_MODEL=/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct,BIG_LLM_NAME=Qwen2.5-14B-Instruct runs_cluster/run_universal.sh` |
| `run_2wikimultihopqa_gpt_lightrag.sh` | `sbatch --export=ALL,RAG_ENGINE=lightrag,DATASET_NAME=2wikimultihopqa,BIG_LLM_MODEL=/userspace/kms/models/gpt-oss-20b,BIG_LLM_NAME=gpt-oss-20b runs_cluster/run_universal.sh` |
| `run_universal_wikontic_gpt.sh` | `sbatch runs_cluster/launch_wikontic_gpt.sh` (то же самое, одним файлом) |

---

## Шаг 1. Забрать код и создать каталог логов

```bash
export HOME=/userspace/sse
cd /userspace/sse/natural_rag
git fetch origin && git checkout wikontic-benchmark && git pull
chmod +x runs_cluster/*.sh
mkdir -p logs
ls -la runs_cluster/
```

`mkdir -p logs` обязателен. SLURM открывает файлы из `#SBATCH --output` / `--error`
**до** запуска скрипта и сам директорий не создаёт: если `logs/` нет, job падает
мгновенно и следов не остаётся нигде — скрипт не стартовал, а писать ошибку некуда.
`mkdir` внутри скрипта тут не спасает, до него дело не доходит. В git пустые
директории не хранятся, поэтому на свежем клоне `logs/` отсутствует.

---

## Шаг 2. Файл переменных окружения

Нужен в **каждой** новой сессии, иначе conda и pip полезут в `/home`.
Создать один раз:

```bash
cat > /userspace/sse/env.sh <<'EOF'
export HOME=/userspace/sse
export CONDA_ENVS_DIRS=/userspace/sse/.conda/envs
export CONDA_PKGS_DIRS=/userspace/sse/.conda/pkgs
export PIP_CACHE_DIR=/userspace/sse/cache/pip
export HF_HOME=/userspace/sse/cache/huggingface
source /userspace/sse/miniconda3/etc/profile.d/conda.sh
EOF
mkdir -p /userspace/sse/.conda/envs /userspace/sse/.conda/pkgs \
         /userspace/sse/cache/pip /userspace/sse/cache/huggingface
```

Дальше в начале каждой сессии — `source /userspace/sse/env.sh`.

---

## Шаг 3. Проверки окружения

### 3.1. Пути к моделям

```bash
ls /userspace/kms/models/ && echo "--- LLMs ---" && ls /userspace/kms/models/LLMs/
```

Нужны: **открытый GigaChat**, **эмбеддер** (только для RAGU) и **судья**.
По умолчанию в скриптах прописаны `/userspace/kms/models/gigachat-3.1-lightning`,
`/userspace/kms/models/gte-multilingual-base` и
`/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct` — если у вас иначе, поправьте
`BIG_LLM_MODEL` / `BIG_LLM_NAME` в блоке «НАСТРОЙКИ».

Если есть `Giga-Embeddings-instruct` — берите его для RAGU и уточните размерность
(пойдёт в `EMBEDDING_DIM`). На Wikontic выбор эмбеддера не влияет: у него зашит
`facebook/contriever`.

### 3.2. Диск, `noexec`, порт

```bash
df -hT /userspace/sse | tail -1
mount | grep -E "on /userspace"
python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print('bind ok:', s.getsockname())"
```

Нужно: **≥40 ГБ** свободных (два окружения с torch и vllm — ~25-30 ГБ, плюс индексы),
`/userspace` **без** `noexec`, `bind ok`. Тип ФС должен быть сетевым
(`nfs`/`lustre`/`gpfs`), иначе индекс, собранный на одной ноде, на другой не найдётся.

### 3.3. Что даёт SLURM

```bash
sinfo -o "%P %l %N %G %c %m"
sacct -u $(whoami) --format=JobID,JobName%20,NodeList,AllocTRES%40,Elapsed,State -S now-14days | head -20
```

`--gres` в скриптах нет и не нужен: на этом кластере ноды выделяются целиком
(так же работают скрипты `run_universal.sh` / `launch_*.sh`).

`#SBATCH --time` в скриптах намеренно нет: ограничений по времени выполнения на
кластере нет, и прогоны идут столько, сколько нужно.

---

## Шаг 4. Окружения conda

Порядок важен: **сначала vllm** (он пинит свою версию torch), потом наш пакет —
иначе pip дважды качает многогигабайтный torch.

```bash
source /userspace/sse/env.sh
conda create -y -p /userspace/sse/.conda/envs/wikontic python=3.12
conda activate /userspace/sse/.conda/envs/wikontic
pip install vllm
cd /userspace/sse/natural_rag && pip install -e ".[wikontic]"
```

```bash
conda deactivate
conda create -y -p /userspace/sse/.conda/envs/ragu python=3.12
conda activate /userspace/sse/.conda/envs/ragu
pip install vllm
cd /userspace/sse/natural_rag && pip install -e ".[ragu]"
```

Судья работает в уже существующем окружении `lightrag`, новое не нужно.

### Версии: обязательно выровнять по `lightrag`

Свежие `vllm` и `transformers` с этим GigaChat'ом не работают. Рабочий набор —
тот, что стоит в `lightrag`, где модель уже успешно серверится
скриптами `runs_cluster/run_universal.sh`:

```bash
pip install "vllm==0.11.0" "transformers==4.57.0" "tokenizers==0.22.2" "torch==2.8.0"
```

Выполнить в **обоих** новых окружениях. Что чинится:

* `transformers` 5.x + `huggingface_hub` 1.x валидируют `config.json` строгими
  датаклассами и падают на `routed_scaling_factor expected float, got int` —
  в конфиге модели лежит целое. В 4.x проверки нет; `transformers` 4.57 тянет
  `huggingface-hub<1.0`, так что отдельно его указывать не надо.
  В `pyproject.toml` теперь стоит `transformers>=4.40,<5`, чтобы это не вернулось.
* `flashinfer`, приехавший с новым vllm, собирает CUDA-ядра JIT'ом системным
  `nvcc`, а на нодах CUDA 11 — падает на `"CUDA versions below 12 are not supported"`.
  В job-скриптах выставлен `VLLM_USE_FLASHINFER_SAMPLER=0`, у vLLM есть родной
  torch-сэмплер. Можно и просто `pip uninstall -y flashinfer-python`.

Проверить, что модель поднимается, не занимая job:

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve /userspace/kms/models/gigachat-3.1-lightning \
  --served-model-name test --port 18000 --max-model-len 4096 --gpu-memory-utilization 0.3
```

Загрузка весов занимает ~16 минут (сетевая ФС), плюс ~1.5 минуты на `torch.compile` —
это нормально, но закладывайте ~20 минут на старт каждого job'а.

Проверка:

```bash
conda activate /userspace/sse/.conda/envs/wikontic
python -c "
import wikontic, torch, qdrant_client
from natural_rag.timing import IndexTimer
from natural_rag.wikontic_prefix import PrefixedBackend
from natural_rag.pipelines.wikontic_pipeline import WikonticPipeline
print('wikontic env OK, cuda:', torch.cuda.is_available())"
```

```bash
conda activate /userspace/sse/.conda/envs/ragu
python -c "import ragu; from natural_rag.timing import IndexTimer; print('ragu env OK')"
```

---

## Шаг 5. Скачать contriever

Wikontic использует `facebook/contriever` жёстко, а на вычислительных нодах стоит
`TRANSFORMERS_OFFLINE=1` — модель обязана лежать локально.

```bash
source /userspace/sse/env.sh
conda activate /userspace/sse/.conda/envs/wikontic
python -c "
from huggingface_hub import snapshot_download
snapshot_download('facebook/contriever', local_dir='/userspace/sse/models/contriever')"
ls -la /userspace/sse/models/contriever
```

Должны быть `config.json`, токенизатор и файл весов (`pytorch_model.bin` или
`model.safetensors`), суммарно ~440 МБ.

---

## Шаг 6. Скачать и проверить Qdrant

```bash
mkdir -p /userspace/sse/qdrant && cd /userspace/sse/qdrant
curl -L -O https://github.com/qdrant/qdrant/releases/download/v1.18.3/qdrant-x86_64-unknown-linux-musl.tar.gz
tar xzf qdrant-x86_64-unknown-linux-musl.tar.gz
chmod +x ./qdrant && ./qdrant --version
```

`musl`-сборка статическая, от glibc ноды не зависит, root не нужен. Конфиг рядом
класть не надо: дефолты вкомпилированы, всё задаётся переменными окружения — это
уже сделано в job-скриптах.

Проверка, что стартует и отвечает:

```bash
cd /tmp && QDRANT__SERVICE__HTTP_PORT=16999 QDRANT__STORAGE__STORAGE_PATH=/tmp/qtest \
  /userspace/sse/qdrant/qdrant > /tmp/qdrant_test.log 2>&1 &
sleep 8 && curl -sf http://127.0.0.1:16999/healthz && echo " <- QDRANT OK"
pkill -f "qdrant/qdrant"
```

---

## Шаг 7. Проверка без GPU и без LLM

Проверяет две самые хрупкие вещи: подхватится ли contriever офлайн и создаются ли
коллекции с префиксом. Можно прямо на login-ноде.

```bash
source /userspace/sse/env.sh
conda activate /userspace/sse/.conda/envs/wikontic
cd /userspace/sse/natural_rag
HF_MODEL_PATH=/userspace/sse/models/contriever TRANSFORMERS_OFFLINE=1 python -c "
from natural_rag.pipelines.wikontic_pipeline import WikonticPipeline
p = WikonticPipeline(api_key='dummy', base_url='http://127.0.0.1:1/v1', model='x',
    mode='dynamic', backend_type='qdrant', qdrant_url=':memory:',
    collection_prefix='probe__test', device='cpu',
    hf_model_path='/userspace/sse/models/contriever')
print('logical: ', sorted(p.triplets_db.list_collection_names()))
print('physical:', sorted(p.triplets_db._backend.list_collection_names()))
"
```

Ожидается:

```
logical:  ['entity_aliases', 'filtered_triplets', 'initial_triplets', 'property_aliases', 'triplets']
physical: ['probe__test__entity_aliases', 'probe__test__filtered_triplets', ...]
```

---

## Шаг 8. Смоук на bl_tiny

Пять документов, dynamic, один воркер — проверяем, что job проходит целиком.

```bash
cd /userspace/sse/natural_rag
DATASET_NAME=bl_tiny WIKONTIC_MODE=dynamic LIMIT_DOCS=5 WIKONTIC_WORKERS=1 \
  sbatch runs_cluster/run_universal_wikontic.sh
squeue -u $(whoami)
```

```bash
tail -f logs/wikontic_bl_tiny_gigachat-3.1-lightning_dynamic_corpus/main.log
```

В логе по порядку: `Starting Qdrant on port ...` → `Qdrant ready` →
`Starting vLLM ...` → `vLLM started` → `Starting Wikontic pipeline` →
`[1/5] Processing document` → `finished (exit 0)` → таблица `index_stats`.

```bash
cat generated/wikontic_bl_tiny_gigachat-3.1-lightning_dynamic_corpus/bl_tiny/gigachat-3.1-lightning/index_summary.json
```

| Поле | Ожидание | Если не так |
|---|---|---|
| `status` | `done` | `running` — job убит, смотрите лог |
| `n_docs` | 5 | меньше — ищите `✗ Failed` в логе |
| `llm_calls` | заметно больше 5 | 0 — счётчик не прицепился |
| `failures` | 0 | >0 — traceback в логе |

---

## Шаг 9. Сборка онтологии (только для structured)

```bash
sbatch runs_cluster/build_ontology.sh
tail -f logs/build_ontology/main.log
```

LLM не поднимается: contriever эмбеддит алиасы из Wikidata-маппингов внутри пакета.
Готовность:

```bash
ls /userspace/sse/qdrant_storage/_ontology_base/collections
```

Дальше каждый structured-прогон копирует эту директорию себе, так что запускается
один раз. Повторный запуск сам выйдет с сообщением «уже собрана».

---

## Основной сценарий: индексация на кластере, ответы на ноутбуке

Кластер держит GPU и строит графы; ответы генерируются отдельно другой моделью
через API, там же оценка. Разделение полезно ещё и тем, что отвечает на открытый
вопрос про пустые ответы: если сильная модель на том же графе отвечает — дело было
в модели, если нет — в графе и связывании сущностей.

### A. Четыре индексационных прогона

`DO_ANSWER=0` — только построение графа.

```bash
DATASET_NAME=musique WIKONTIC_MODE=structured DO_ANSWER=0 sbatch runs_cluster/run_universal_wikontic.sh
```

```bash
DATASET_NAME=musique WIKONTIC_MODE=dynamic DO_ANSWER=0 sbatch runs_cluster/run_universal_wikontic.sh
```

```bash
DATASET_NAME=bioasq WIKONTIC_MODE=dynamic DO_ANSWER=0 sbatch runs_cluster/run_universal_wikontic.sh
```

```bash
DATASET_NAME=graphrag_bench_medical WIKONTIC_MODE=dynamic DO_ANSWER=0 sbatch runs_cluster/run_universal_wikontic.sh
```

Для structured сначала нужна онтология (шаг 9). Для graphrag-bench — подготовка
датасета (шаг 12). `use_qualifiers` здесь роли не играет: он используется только
в `generate_answer` / `answer_with_qa_collapsing`, то есть на этапе ответов.

**Обязательно проверьте в конце каждого прогона:**

```bash
grep -c "NO TRIPLETS STORED" logs/<RUN_ID>/main.log
python -c "import json,glob; [print(f, json.load(open(f))['empty_docs']) for f in glob.glob('generated/<RUN_ID>/**/index_summary.json', recursive=True)]"
```

`empty_docs > 0` означает, что столько-то документов отработали без ошибки, но
ничего не записали в граф — Wikontic проглатывает сбой разбора своего же ответа
(модель уходит в цикл до лимита токенов). Повторный запуск того же sbatch с
`--resume` их переберёт: они не помечены как готовые.

### B. Экспорт индексов

Бенчмарки заканчиваются в разное время — забирать по одному, не дожидаясь
остальных. Что готово:

```bash
./runs_cluster/export_index.sh --list
```

Колонки: статус (`done` / `ИДЁТ <job>` / `running` у умершего job'а), число
документов, сколько из них не попало в граф, размер, RUN_ID. `ПУСТЫХ > 0` ещё не
поздно добрать повторным sbatch с `--resume` — после вывоза уже не починить.

Затем нужный прогон:

```bash
./runs_cluster/export_index.sh wikontic_graphrag_bench_medical_gigachat-3.1-lightning_dynamic_corpus
```

Несколько — через пробел; `--all` заберёт все разом. Директорию, которую держит
живой job, скрипт не тронет, а про неполный индекс предупредит.

Кладёт в `/userspace/sse/index_export/` по архиву на прогон. Внутри не только
storage Qdrant, но и `manifest.json` (режим, scope, `collection_prefix`, модель
индексации), `generated/<RUN_ID>/` с цифрами фронта 1, `main.log.gz` и — если
датасета нет в git, то есть для `graphrag_bench_medical` — сам датасет.

Датасет обязателен: `answers/<i>.txt` нумеруются по позиции вопроса, другой
порядок вопросов молча сдвинет все ответы.

```bash
mkdir -p ~/wikontic_bundles && scp 'sse@<кластер>:/userspace/sse/index_export/<RUN_ID>.tar.gz' ~/wikontic_bundles/
```

### C. Дальше — на своей машине

Подготовка окружения, генерация ответов через API и оценка по каждому бенчмарку
описаны в **[`runs_local/README.md`](../runs_local/README.md)**. Коротко:

```bash
cd ~/wikontic_bundles && for f in *.tar.gz; do tar xzf "$f"; done
```

```bash
python runs_local/answer_from_index.py --bundle ~/wikontic_bundles/<RUN_ID> --preflight-only
```

```bash
python runs_local/answer_from_index.py --bundle ~/wikontic_bundles/<RUN_ID> --model gpt-4o-mini --short-answers
```

Режим графа, scope, `collection_prefix` и модель индексации читаются из
манифеста — вводить их руками не нужно и не следует: ошибка в префиксе не падает,
а тихо даёт пустые ответы на всём датасете. Preflight ловит это до первого
обращения к платному API.

---

## Шаг 10. Два прогона musique

Дождитесь онтологии, затем:

```bash
cd /userspace/sse/natural_rag
sbatch runs_cluster/musique_wikontic_structured.sh
sbatch runs_cluster/musique_wikontic_dynamic.sh
squeue -u $(whoami)
```

Оба самодостаточны и не мешают друг другу: разные порты vLLM (8000 / 8010), разные
storage-директории Qdrant, разные префиксы коллекций, разные каталоги результатов.
Если очередь узкая — ставьте по одному: сравнение по `s/doc` от времени старта не
зависит.

| | structured | dynamic |
|---|---|---|
| лог | `logs/wikontic_musique_structured/main.log` | `logs/wikontic_musique_dynamic/main.log` |
| результаты | `generated/wikontic_musique_structured/musique/gigachat-3.1-lightning/` | `generated/wikontic_musique_dynamic/...` |
| Qdrant | `qdrant_storage/wikontic_musique_structured` | `qdrant_storage/wikontic_musique_dynamic` |

---

## Шаг 11. Наблюдение и решение

```bash
./runs_cluster/show_progress.sh
```

Ждать конца не нужно: `index_summary.json` пишется сразу со статусом `running`, а
`runs/index_stats.py` пересчитывает живые числа по `index_timing.jsonl`. Через
час-два таблица покажет `s/doc`, `docs/min` и прогноз `eta_h` для обоих режимов —
по ним и решаете, тянуть ли structured дальше.

Точечно:

```bash
wc -l generated/wikontic_musique_structured/musique/gigachat-3.1-lightning/index_timing.jsonl
```

Если job упал по таймауту — просто поставьте тот же sbatch снова: `--resume` включён
и пропустит уже проиндексированные документы (проверка по `(sample_id,
source_text_id)`, как в их собственном `dataset_inference.py`).

**Про `WIKONTIC_WORKERS=1`.** Это осознанный выбор: апстримный Wikontic индексирует
строго последовательно, поэтому единственный поток даёт честное «сколько это стоит
как есть». Наш `ThreadPoolExecutor` — внешняя добавка, и включать её в основной
замер нечестно. Обратная сторона: полный musique (5 966 документов) в один поток
оценочно 50+ часов. Лимита времени на кластере нет, так что job доработает до
конца; если он всё же оборвётся (сбой ноды, ошибка), достаточно поставить тот же
sbatch снова — `--resume` продолжит с места остановки, а суммарное время тогда
считается по `index_timing.jsonl`, а не по одному job'у.

Если после основного замера захотите отдельно показать, сколько удалось выжать
распараллеливанием снаружи — прогон с `WIKONTIC_WORKERS=4` в **отдельную**
storage-директорию (смените `RUN_ID` в скрипте) и сравнение числа триплетов с
однопоточным: `Aligner` и `InferenceWithDB` не заявлены потокобезопасными.

---

## Шаг 12. Остальные бенчмарки

По итогам шага 11, обычно на `dynamic`:

```bash
DATASET_NAME=bioasq WIKONTIC_MODE=dynamic SHORT_ANSWERS=1 sbatch runs_cluster/run_universal_wikontic.sh
```

```bash
DATASET_NAME=bioasq SHORT_ANSWERS=1 sbatch runs_cluster/run_universal_ragu.sh
```

```bash
DATASET_NAME=musique SHORT_ANSWERS=1 sbatch runs_cluster/run_universal_ragu.sh
```

Прогоны независимы: у каждого Wikontic-прогона своя storage-директория, RAGU Qdrant
вообще не использует (у него файловый индекс).

GraphRAG-Bench сначала готовится на login-ноде (нужен интернет):

```bash
source /userspace/sse/env.sh && conda activate /userspace/sse/.conda/envs/ragu
cd /userspace/sse/natural_rag && python runs/prepare_graphrag_bench.py --domain medical
```

Каждая запись их корпуса — учебник целиком, а у Wikontic нет чанкера, поэтому скрипт
режет корпус на куски по 4000 символов по границам абзацев (`--max-doc-chars N`).

---

## Шаг 13. Оценка

В `runs_cluster/eval_universal.sh` — блок настроек под каждый прогон свой:

```bash
RAG_ENGINE="wikontic"
DATASET_NAME="musique"
INDEX_MODEL="gigachat-3.1-lightning"
OUTPUT_DIR_NAME="wikontic_musique_structured"   # или wikontic_musique_dynamic
JUDGE_MODEL="/userspace/kms/models/LLMs/Qwen2.5-14B-Instruct"
JUDGE_MODEL_NAME="Qwen2.5-14B-Instruct"
```

```bash
sbatch runs_cluster/eval_universal.sh
```

`OUTPUT_DIR_NAME` — это имя каталога в `generated/`, оно же `RUN_ID` прогона.
Посмотреть точное имя проще всего так:

```bash
ls generated/
```

Для выделенных скриптов это `wikontic_musique_structured` / `wikontic_musique_dynamic`,
для `run_universal_wikontic.sh` — `wikontic_<датасет>_<модель>_<режим>_<scope>`,
для `run_universal_ragu.sh` — `ragu_<датасет>` (совпадает с дефолтом, можно оставить пустым).

EM и F1 считаются вообще без GPU и судьи, прямо на login-ноде:

```bash
python runs/judge_answers.py --dataset-path datasets/musique \
  --output-dir generated/wikontic_musique_structured \
  --index-model gigachat-3.1-lightning --no-judge
```

---

## Шаг 14. Итоговые таблицы

```bash
python runs/index_stats.py generated
python runs/index_stats.py generated --format csv --out index_stats.csv
```

`index_summary.json` пишется одним и тем же `natural_rag/timing.py` для обоих
движков, поэтому wall-time, docs/min, LLM-вызовы и токены сравнимы напрямую.
У RAGU индексация корпуса — один вызов, поэтому в `index_timing.jsonl` у него одна
строка на весь корпус, у Wikontic — по строке на документ.

---

## Хранилище и изоляция

Индексы лежат **на диске** и переживают завершение job'а. Qdrant журналирует каждую
операцию в WAL, поэтому убийство job'а по таймауту данные не теряет.

Изоляция двухуровневая:

1. **Имена коллекций.** Wikontic хардкодит их в `Aligner`, поэтому два индекса в
   одном хранилище затирали бы друг друга. `--collection-prefix` (= `RUN_ID`)
   навешивает префикс на все коллекции триплетов — `natural_rag/wikontic_prefix.py`.
2. **Storage-директория.** Своя у каждого прогона. Два процесса Qdrant поверх одной
   директории на сетевой ФС — это не «второй не стартует», а порча данных:
   блокировки на NFS ненадёжны.

Предохранители: файл `.owner` со `SLURM_JOB_ID` (job откажется стартовать, если
указанный там job ещё жив по `squeue`; протухший перехватывается автоматически),
порт Qdrant подбирается свободным, `cleanup` даёт Qdrant до 30 секунд на корректное
завершение, а `pkill` бьёт только по своему порту vLLM — иначе параллельный прогон
на той же ноде остался бы без сервера.

---

## Два режима охвата графа

`WIKONTIC_SCOPE`:

* `corpus` (по умолчанию) — один граф на весь корпус, `sample_id=None`. Реальный
  RAG-режим, в котором работает RAGU. У Wikontic он в статье не измерялся.
* `per_sample` — как в их опубликованной оценке (`inference_and_eval/qa_eval_musique.py`):
  у каждого вопроса свой маленький граф, поиск фильтруется по `sample_id`. Наш корпус
  musique дедуплицирован, поэтому исходные 20 абзацев на вопрос не восстановить;
  берутся золотые документы плюс детерминированно досэмплированные дистракторы до
  `WIKONTIC_PER_SAMPLE_DOCS` — иначе Wikontic получил бы корпус только из золотых
  документов и идеальный retrieval.

В `per_sample` единиц индексации больше, чем документов в корпусе (498 × 20 = 9 960
против 5 966): абзацы повторяются в разных сэмплах. Скорость между режимами напрямую
сравнивать нельзя, только качество.

---

## Что делать, если

| Симптом | Причина и что делать |
|---|---|
| Job падает мгновенно, логов нет вообще | нет каталога `logs/` — SLURM не смог создать файлы из `#SBATCH --output`/`--error`. `mkdir -p /userspace/sse/natural_rag/logs`. Проверить: `sacct -j <JOBID> --format=JobID,State,ExitCode,Reason%40,Elapsed` |
| Job висит в PENDING | причина в колонке `R`: `squeue -u $(whoami) -o "%.10i %.12j %.9P %.8T %.10M %.20R"`. Частое — несовместимые `--partition` и `--nodelist`, либо нет свободных нод |
| `routed_scaling_factor expected float, got int` | `transformers` 5.x. Откатить до 4.57.0, см. «Версии» в шаге 4 |
| `"CUDA versions below 12 are not supported"`, `Ninja build failed` | flashinfer собирает ядра системным `nvcc` (CUDA 11). В скриптах уже стоит `VLLM_USE_FLASHINFER_SAMPLER=0`; если всё равно лезет — `pip uninstall -y flashinfer-python` |
| `ResponseHandlingException: timed out` при `create_payload_index` | сетевая ФС медленнее дефолтного таймаута `qdrant-client`. В скриптах стоит `--qdrant-timeout 120`; если мало — поднимите. Проверьте в `qdrant.log` длительность запроса |
| `NO TRIPLETS STORED` в логе, `empty_docs > 0` | документ отработал без ошибки, но ничего не записал: модель ушла в цикл, JSON не распарсился, Wikontic это проглотил. Перезапустите тот же sbatch — `--resume` их переберёт, они не помечены готовыми |
| В логе `Answer: None` вместо `Empty answer: ...` | исполняется не тот файл. `python -c "import natural_rag.pipelines.wikontic_pipeline as m; print(m.__file__)"` — если путь ведёт в site-packages, пакет установлен не editable и затеняет репозиторий: `pip install -e .` из корня проекта |
| `Qdrant died on startup` | `logs/<RUN_ID>/qdrant.log`; чаще всего директория занята другим живым job'ом |
| `занят живым job'ом NNN` | прогон уже идёт. `squeue -j NNN`; если job мёртв — удалите `.owner` в его storage-директории |
| Висит на `Waiting for vLLM` | `logs/<RUN_ID>/vllm_llm.log` — обычно не хватает памяти GPU: снижайте `LLM_MEM_UTIL` или поднимайте `NUM_GPUS` |
| `contriever not found` | `HF_MODEL_PATH` не указывает на скачанную папку (шаг 5) |
| `llm_calls: 0` в summary | счётчик не прицепился к клиенту Wikontic |
| Много `✗ Failed` при индексации | превышение контекста: документ уходит в LLM целиком. Режьте датасет или поднимайте `--max-model-len` |
| Ответов меньше вопросов | перезапустите с `DO_INDEX=0` — существующие ответы пропустятся, недостающие догенерируются |
| Начать прогон с нуля | `rm -rf /userspace/sse/qdrant_storage/<RUN_ID>` — пересоздастся из `_ontology_base` |

---

## Известные ограничения сравнения

Фиксировать в отчёте:

1. **Эмбеддер разный.** У Wikontic захардкожен `facebook/contriever` (768), он не
   использует OpenAI-совместимый эндпоинт вовсе. Эмбеддер Сбера применим только к
   RAGU. Контролируемая переменная — LLM (GigaChat для обоих).
2. **Короткие ответы.** У RAGU `--short-answers` подменяет шаблон промпта; у
   Wikontic промпты внутри пакета, поэтому инструкция дописывается к тексту вопроса.
3. **QA-путь.** По умолчанию `answer_question_with_llm`; их опубликованная оценка
   идёт через `answer_with_qa_collapsing` (`WIKONTIC_QA_COLLAPSING=1`).
4. **Индексация меряется в один поток** (`WIKONTIC_WORKERS=1`) — именно так работает
   апстримный Wikontic. Параллелизм в нашей обвязке есть, но в основной замер не
   включён. RAGU при этом асинхронный по своей природе
   (`OPENAI_RATE_MAX_SIMULTANEOUS`, по умолчанию 10) — сравниваются движки как есть,
   а не искусственно уравненные конфигурации; это стоит проговорить в отчёте прямо.
5. **Что измерено в статье.** EACL 2026, `aclanthology.org/2026.eacl-long.388`:
   QA мерилось на графах из ~20 абзацев одного сэмпла с фильтрацией по `sample_id`,
   датасет `musique_200_test.json` — 200 сэмплов. Корпусный режим не измерялся.
