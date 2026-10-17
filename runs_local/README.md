# Ответы и оценка на своей машине (Ubuntu)

Кластер строит графы, дальше он не нужен. Индексы вывозятся сюда, ответы
генерируются **gpt-4o-mini** через API vsellm, оценка тоже здесь.

Почему именно gpt-4o-mini: это протокол из нашей же статьи (раздел 3.1) — «all
systems use the same answer-generation LLM (gpt-4o-mini), isolating graph
construction quality». Ответчик один на все движки, различается только граф.
Судья при этом обязан быть **другим** (`gemini-3-flash-preview`), иначе модель
оценивает саму себя.

---

## 1. Разово: окружение

```bash
pip install -e ".[wikontic]"
```

### Эмбеддер

Разворачивать отдельно нечего: `facebook/contriever` — обычная torch-модель,
которую Wikontic грузит внутрь своего процесса. Ни порта, ни сервера, ни vLLM.
На машине с интернетом она скачается сама.

Но скачать явно всё-таки стоит, по трём причинам: `Aligner` строится в
конструкторе пайплайна, то есть **и при генерации ответов без индексации** —
без модели ничего не запустится; веса должны быть **те же, что на кластере**,
иначе эмбеддинги запроса лягут в другое пространство, чем проиндексированные
(ошибки не будет, просто тихо просядет качество); и на офлайновой машине
автозагрузка не сработает вовсе.

```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('facebook/contriever', local_dir='models/contriever')"
```

~440 МБ. GPU почти не занимает (110M параметров) — `WIKONTIC_DEVICE=cuda`.

### Эмбеддер для индексов RAGU (в т.ч. Windows)

RAGU ходит к эмбеддеру по HTTP (`EmbedderOpenAI`), на кластере это vLLM с
gte-multilingual-base. vLLM под Windows не работает, а для ответов по готовому
индексу нужны только эмбеддинги запросов, поэтому хватает маленького
OpenAI-совместимого сервера `runs_local/serve_embedder.py` на
sentence-transformers. Отдельное окружение:

```bash
python -m venv .venv_embed
.venv_embed/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv_embed/Scripts/python -m pip install "sentence-transformers>=3,<6" "transformers>=4.40,<5"
.venv_embed/Scripts/python runs_local/serve_embedder.py --port 8002
```

Для GPU RTX 50xx вместо `whl/cpu` нужен `whl/cu128`; для ~500 запросов хватает и
CPU. Первый запуск скачивает модель (~600 МБ) и её код (`trust_remote_code`).

Проверка, что сервер даёт те же векторы, что лежат в индексе (иначе поиск
тихо деградирует):

```bash
.venv_embed/Scripts/python runs_local/check_embedder.py --index-dir generated/ragu_musique/musique/gpt-oss-20b/index
```

Для `ragu_musique/gpt-oss-20b` (2026-10-16): косинус 1.00000 по чанкам,
сущностям и отношениям. Дальше в `runs/ragu_run.py`:
`--embed-base-url http://127.0.0.1:8002/v1 --embedding-model-name gte-multilingual-base --embedding-dim 768`.

### Qdrant

Тот же статический бинарь, что на кластере, root не нужен:

```bash
curl -L -O https://github.com/qdrant/qdrant/releases/download/v1.18.3/qdrant-x86_64-unknown-linux-musl.tar.gz
tar xzf qdrant-x86_64-unknown-linux-musl.tar.gz && chmod +x ./qdrant && ./qdrant --version
```

Запускать руками не надо: `answer_from_index.py` поднимает его сам на свободном
порту над нужным бандлом и гасит на выходе.

### Переменные

```bash
export HF_MODEL_PATH=models/contriever
export WIKONTIC_DEVICE=cuda
export OPENAI_BASE_URL=https://api.vsellm.ru/v1
export OPENAI_API_KEY=<ключ>
```

---

## 2. Вывоз индексов с кластера

Бенчмарки заканчиваются в разное время, поэтому индексы забираются **по одному**,
не дожидаясь остальных. Сначала — что вообще готово:

```bash
./runs_cluster/export_index.sh --list
```

```
СТАТУС          ДОКОВ  ПУСТЫХ   РАЗМЕР  RUN_ID
done              233       1     3.4G  wikontic_graphrag_bench_medical_gpt-oss-20b_dynamic_corpus
done              157       8     2.9G  wikontic_graphrag_bench_medical_Qwen2.5-7B-Instruct_dynamic_corpus
done              214      48     2.1G  wikontic_graphrag_bench_medical_meno-lite-0.1_dynamic_corpus
```

`done` — прогон завершился, можно забирать. `ИДЁТ <job>` — Qdrant ещё пишет в
директорию, скрипт такую не тронет. `running` без номера job'а — job умер на
середине: индекс частичный, но рабочий, дособрать можно тем же sbatch
(`--resume` включён).

`ПУСТЫХ > 0` — столько документов отработали без ошибки, но в граф не попали.
Это ещё не поздно добрать повторным sbatch; после вывоза уже не починить, а
качество просядет по причине, не имеющей отношения к движку.

Дальше — по одному прогону:

```bash
./runs_cluster/export_index.sh wikontic_graphrag_bench_medical_gpt-oss-20b_dynamic_corpus
```

```bash
./runs_cluster/export_index.sh wikontic_graphrag_bench_medical_Qwen2.5-7B-Instruct_dynamic_corpus
```

```bash
./runs_cluster/export_index.sh wikontic_graphrag_bench_medical_meno-lite-0.1_dynamic_corpus
```

Можно перечислить несколько через пробел, а `--all` заберёт всё разом. Индексы
musique и bioasq ещё не пересобраны — их очередь после.

Скрипт печатает статус и предупреждает, если индекс неполный (`статус
'running'`, `проиндексировано N из M`) — то есть забрать недосчитанный musique
молча не получится.

Кладёт в `/userspace/sse/index_export/` по архиву на прогон. Внутри не только
storage Qdrant:

| Что | Зачем |
|---|---|
| `manifest.json` | режим, scope, `collection_prefix`, модель индексации — чтобы ничего не вводить руками |
| `qdrant_storage/<RUN_ID>/` | сам граф |
| `generated/<RUN_ID>/` | `index_summary.json`, `index_timing.jsonl` — цифры фронта 1, `generated/` в `.gitignore` |
| `datasets/<name>/` | только если датасета нет в git (это случай `graphrag_bench_medical`) |
| `main.log.gz` | улика для `NO TRIPLETS STORED` |

Датасет обязателен: `answers/<i>.txt` нумеруются **по позиции вопроса** в
датасете. Другой порядок вопросов молча сдвинет все ответы, и оценка получится
бессмысленной без единой ошибки в логе.

На своей машине — забирать тоже по одному, по мере готовности:

```bash
mkdir -p ~/wikontic_bundles && scp 'sse@<кластер>:/userspace/sse/index_export/*.tar.gz' ~/wikontic_bundles/
```

```bash
cd ~/wikontic_bundles && for f in *.tar.gz; do tar xzf "$f"; done && ls -d */
```

Проверить каждый распакованный бандл до того, как тратить API:

```bash
python runs_local/validate_index.py --bundle ~/wikontic_bundles/<RUN_ID>
```

Он сам поднимает Qdrant над бандлом, считает покрытие справочников и уходит в
ненулевой код, если индекс негоден. Бандлы
независимы: каждый несёт свой граф, манифест и датасет, и распаковываются они в
отдельные директории.

---

## 3. Глубина обхода — подобрать до ответов

Это самый дорогой шаг, если его пропустить. `answer_question_with_llm`
разворачивает `hop_depth` хопов от связанных сущностей и кладёт **всё**
достигнутое в один промпт: ни top-k, ни ранжирования (находка 16). Дефолт 5
безопасен только на per-sample подграфах. На корпусном он вываливает весь граф,
а шлюз отвечает непрозрачным `400 Request failed`, по которому причину не
опознать.

```bash
python runs_local/measure_hop_depth.py --bundle ~/wikontic_bundles/<RUN_ID>
```

В конце печатается готовая строка `БЕЗОПАСНЫЙ МИНИМУМ: --hop-depth N`.

**Мерить надо на каждом бандле отдельно.** Три графа отличаются связностью
принципиально: триплетов на одно отношение 27.9 у gpt-oss-20b против 5.7 у Qwen.
Компактный словарь предикатов означает более плотный граф, и один хоп от хаба
тянет существенно больше. Значение с одной модели на другую не переносится.

Смотреть надо на **строку ХАБ**, а не на перцентили. Случайные сиды занижают
риск: большинство сущностей периферийные, а реальные вопросы попадают в хабы.
На прошлом graphrag_bench ни один случайный сид не превышал лимит на хопе 2, а
хаб `cancer` в одиночку давал там 116 007 токенов — и прогон падал.

---

## 4. Ответы

Режим графа, scope, префикс коллекций и модель индексации скрипт берёт из
манифеста. Руками задаются только модель-ответчик и глубина из шага 3.

Сначала — проверка без единого обращения к API:

```bash
python runs_local/answer_from_index.py --bundle ~/wikontic_bundles/<RUN_ID> --preflight-only
```

Печатает число точек в каждой коллекции. Если префикс не тот или storage не от
этого прогона — выходит с ошибкой и показывает, что в Qdrant есть на самом деле.
Это главная причина, по которой скрипт существует: **неверный префикс не
падает**, Wikontic просто ничего не находит и отдаёт пустые ответы на всём
датасете. Узнать об этом постфактум стоит дня и всего бюджета на API.

Дальше по одному бандлу на модель. `<N>` подставьте из шага 3:

```bash
python runs_local/answer_from_index.py --bundle ~/wikontic_bundles/wikontic_graphrag_bench_medical_gpt-oss-20b_dynamic_corpus --model gpt-4o-mini --hop-depth <N>
```

```bash
python runs_local/answer_from_index.py --bundle ~/wikontic_bundles/wikontic_graphrag_bench_medical_Qwen2.5-7B-Instruct_dynamic_corpus --model gpt-4o-mini --hop-depth <N>
```

```bash
python runs_local/answer_from_index.py --bundle ~/wikontic_bundles/wikontic_graphrag_bench_medical_meno-lite-0.1_dynamic_corpus --model gpt-4o-mini --hop-depth <N>
```

**Без** `--short-answers`. Уровни Contextual Summarize и Creative Generation
оцениваются по Coverage — терсный промпт занизит их по построению, и это будет
артефакт формата, а не свойство графа.

Результат — `generated/<RUN_ID>__gpt-4o-mini/graphrag_bench_medical/<модель-индексации>/answers/`:
`<i>.txt` с ответом и `<i>.context.json` с триплетами, из которых он собран.
Имя модели-ответчика в пути обязательно, иначе прогоны разными моделями поверх
одного графа затрут друг друга.

Прервали — запустите ту же команду снова: готовые ответы пропускаются,
недостающие досчитываются. `--force` перегенерирует всё.

### musique и bioasq — когда дойдут руки

Их индексы ещё не пересобраны. Порядок тот же, но с `--short-answers`: у
musique/bioasq золотые ответы короткие, и многословный ответ роняет ROUGE-L с 49
до 12 безотносительно качества retrieval. В статье для них две панели, verbose и
terse; вторая делается тем же прогоном без флага и с другим `--output-dir`,
иначе он увидит готовые файлы и всё пропустит.

---

## 5. Оценка

### Быстрая проверка, без API

EM, token-F1 и разбивка по типам вопросов — сразу, бесплатно:

```bash
python runs/judge_answers.py --dataset-path datasets/graphrag_bench_medical --output-dir generated/wikontic_graphrag_bench_medical_gpt-oss-20b_dynamic_corpus__gpt-4o-mini --index-model gpt-oss-20b --no-judge
```

Разбивка по `question_type` включается сама, когда поле есть в датасете
(`--group-by ''` выключает). Для GraphRAG-Bench получится четыре строки — Fact
Retrieval, Complex Reasoning, Contextual Summarize, Creative Generation.

Это **не замена** официальной оценке: метрики другие. Это способ за минуту
увидеть, что ответы вообще осмысленные, прежде чем запускать судью на всём
датасете.

### Официальная оценка GraphRAG-Bench

Как в статье. Сборка входного файла:

```bash
python runs/build_graphrag_bench_input.py --dataset-path datasets/graphrag_bench_medical --output-dir generated/wikontic_graphrag_bench_medical_gpt-oss-20b_dynamic_corpus__gpt-4o-mini --index-model gpt-oss-20b
```

Смотрите на строку `with retrieved context: N/M` — она должна быть непустой,
иначе `faithfulness` и весь `retrieval_eval.py` посчитаются в ноль.

Дальше из репозитория [GraphRAG-Benchmark](https://github.com/bond005/GraphRAG-Benchmark),
в его окружении. **Ключ там называется иначе** — `LLM_API_KEY`, а не
`OPENAI_API_KEY`; без него оба скрипта падают с `ValueError` ещё до первого
запроса:

```bash
export LLM_API_KEY="<ключ vsellm>"
```

```bash
python -m Evaluation.generation_eval --mode API --model gemini-3-flash-preview --base_url https://api.vsellm.ru/v1 --embedding_model text-embedding-3-small --embedding_base_url https://api.vsellm.ru/v1 --data_file <path>/graphrag_bench_input.json --output_file <path>/generation_results.json --detailed_output
```

```bash
python -m Evaluation.retrieval_eval --mode API --model gemini-3-flash-preview --base_url https://api.vsellm.ru/v1 --data_file <path>/graphrag_bench_input.json --output_file <path>/retrieval_results.json
```

`generation_eval` сам группирует по `question_type` и на каждый тип считает свой
набор:

| Тип вопроса | Метрики |
|---|---|
| Fact Retrieval | `rouge_score`, `answer_correctness` |
| Complex Reasoning | `rouge_score`, `answer_correctness` |
| Contextual Summarize | `answer_correctness`, `coverage_score` |
| Creative Generation | `answer_correctness`, `coverage_score`, `faithfulness` |

`retrieval_eval` даёт `context_relevancy` и `evidence_recall`. Обе читают поле
`context` — то самое, что берётся из `<i>.context.json`.

Судья `gemini-3-flash-preview` — не тот, что генерировал ответы. В статье это
оговорено отдельно: «ensuring no evaluator–generator overlap».

### Итоговая таблица

Числа прогона расползаются по четырём файлам в трёх разных форматах. Перепечатывать
их руками — способ незаметно ошибиться цифрой, поэтому есть сборщик:

```bash
python runs_local/report_results.py --output-dir generated/wikontic_graphrag_bench_medical_gpt-oss-20b_dynamic_corpus__gpt-4o-mini --dataset-path datasets/graphrag_bench_medical --index-model gpt-oss-20b --hop-depth <N>
```

Он отдельно разделяет «отвечает плохо» и «часто не отвечает». Промпт Wikontic
предписывает вернуть `None`, если ответа в триплетах нет, поэтому отказ выглядит
как обычный ответ и даёт ровно ноль по ROUGE и coverage. Общее среднее эти два
случая смешивает, а они указывают на разные половины системы.

Повторить для каждой из трёх моделей и свести строки вместе — это и есть
таблица для статьи.

### musique и bioasq

Вашим обычным путём, он не менялся (скрипты переехали из `runs_universal/`
в `runs/` и получили CLI-флаги поверх env):

```bash
ANSWERS_DIR=generated/<RUN_ID>__gpt-4o-mini/musique/gigachat-3.1-lightning/answers DATASET_NAME=musique python runs/convert_answers.py
```

```bash
DATASET_NAME=musique ANSWERS_DIR=generated/<RUN_ID>__gpt-4o-mini/musique/gigachat-3.1-lightning/answers JUDGE_MODEL_NAME=gemini-3-flash-preview python runs/jsonl_llm_judge_evaluate.py
```

---

## 6. Эксперименты с decision model

Замеры decision model в RAGU (отбор контекста LocalSearch одним токеном и обход
графа на несколько шагов) делались на MuSiQue по готовому индексу
`generated/ragu_musique/musique/gpt-oss-20b/index`. Ответы и решения даёт
gpt-4o-mini через vsellm, оценивает gemini-3-flash-preview по протоколу
GraphRAG-Benchmark. Нужны RAGU из ветки `feature/decision-model` форка (команда
установки в [runs/README.md](../runs/README.md#installing-ragu)), сервер эмбеддера
из раздела 1 и чекаут [GraphRAG-Benchmark](https://github.com/bond005/GraphRAG-Benchmark)
со своим окружением.

Все варианты отвечают по одному общему индексу, каждый в свою папку
`generated/ragu_musique__<вариант>/` и со своим кэшем LLM, чтобы время ответа было
честным. Варианты лучше гонять по очереди, а не параллельно, иначе время одного
зависит от нагрузки другого.

```bash
export OPENAI_API_KEY=<ключ vsellm> PYTHON=<python с RAGU из ветки форка>
```

```bash
runs_local/run_musique_variant.sh base 498
```

```bash
runs_local/run_musique_variant.sh dm_h2p30_na 498 --always-answer --selector pointwise --decision-model-name gpt-4o-mini --select-hops 2 --select-pool-chunks 30
```

Остальные варианты из замеров отличаются только флагами:

| Вариант | Флаги |
|---|---|
| `base` | — (исходный LocalSearch) |
| `base_na` | `--always-answer` |
| `base800` | `--context-budget 800` |
| `cosine` | `--selector cosine` |
| `dm` | `--selector pointwise --decision-model-name gpt-4o-mini` |
| `dm_h2p30` | `dm` + `--select-hops 2 --select-pool-chunks 30` |
| `dm_h2p30_na` | `dm_h2p30` + `--always-answer` |
| `aug_h2` | `dm_h2p30` + `--select-keep-seed-context` |
| `ppr_dm`, `ppr_nodm` | `--ppr-chunks 5`, с decision model и без |

Повторный запуск с тем же именем пропускает готовые ответы, так что прерванный
прогон просто запускается ещё раз.

Оценка судьёй. Скрипт сам собирает `graphrag_bench_input.json` и оценивает только
те вопросы диапазона, которых ещё нет ни в одном `eval_results*.json` варианта;
вопросы, отвалившиеся по сети, добираются в следующем раунде. Судья стоит около
0.15 рубля за вопрос, поэтому разработка шла на вопросах 0–99, а 100–497 отложены
для проверки выбранной конфигурации.

```bash
LLM_API_KEY=<ключ vsellm> GRAPHRAG_BENCH_ROOT=<путь к GraphRAG-Benchmark> EVAL_PYTHON=<его python> runs_local/eval_graphrag_bench.sh dm_h2p30_na 100 497
```

Второй независимый проход судьи запускается с `PASS=pass2`: тогда готовыми
считаются только файлы `eval_results_pass2*.json`, и судья заново оценивает весь
диапазон. `compare_runs.py` усредняет все проходы варианта; на 398 вопросах два
прохода расходятся в среднем не больше чем на 0.2 пункта.

Сравнение, всё офлайн и бесплатно:

```bash
python runs_local/compare_runs.py base base_na dm cosine base800 dm_h2p30 dm_h2p30_na --ids 100-497
```

```bash
python runs_local/gold_recall.py base dm_h2p30_na --ids 0-99
```

`compare_runs.py` сравнивает каждый вариант с первым на общих вопросах: средняя
разница AC, 95% парный бутстреп-интервал, p с поправкой Холма, число вопросов,
ставших лучше и хуже, а также время по этапам и цену генерации на вопрос.
`gold_recall.py` считает, какая доля gold-документов MuSiQue попала в контекст
ответа.

Диагностика графа без вызовов LLM, нужен только эмбеддер. `graph_reachability.py`
показывает потолок обхода: сколько gold-чанков достижимо за 0–3 шага от стартовых
сущностей и сколько кандидатов добавляет каждый шаг. `ppr_reachability.py`
проверяет, поднимает ли Personalized PageRank по графу gold-чанки выше косинуса.

```bash
python runs_local/graph_reachability.py --ids 0-99
```

```bash
python runs_local/ppr_reachability.py --ids 0-99
```

Результат на отложенных вопросах (395 из 100–497, AC, разница с `base` и 95%
интервал):

| Вариант | AC | Разница | Контекст, токенов |
|---|---|---|---|
| `base` | 38.3 | | 6253 |
| `base_na` | 42.4 | +4.1 [+2.3; +5.9] | 6253 |
| `dm` | 37.5 | −0.7 [−2.9; +1.4] | 753 |
| `cosine` | 30.7 | −7.6 [−10.3; −4.9] | 741 |
| `base800` | 32.1 | −6.1 [−8.3; −4.0] | 800 |
| `dm_h2p30` | 41.8 | +3.6 [+1.0; +6.2] | 964 |
| `dm_h2p30_na` | 46.0 | +7.8 [+5.0; +10.5] | 964 |
| HippoRAG 2 | 49.0 | +10.7 [+6.6; +14.8] | — |

`dm_h2p30_na` лучше `base_na` на 3.8 пункта [+1.3; +6.4], то есть обход decision
model даёт прирост и сверх промпта без отказа. Цена: ответ на вопрос 7.9 с против
2.2 с, 96 запросов к decision model и около 0.41 рубля на генерацию против 0.087.

---

## Что придётся оговорить в отчёте

**Графы построены на разной доле корпуса.** Это первое, что надо назвать при
любом сравнении качества:

  gpt-oss-20b           263/264   99.6%
  Qwen2.5-7B-Instruct   256/264   97.0%
  meno-lite-0.1         216/264   81.8%

Часть отставания meno объясняется отсутствующими 18% документов, а не качеством
графа. Вопросы, чей источник не попал в индекс, обречены независимо от
модели-ответчика. Довести покрытие до равного нельзя: проход добора у meno и
Qwen вернул ноль документов (журнал находок, раздел 2.7).


- **Эмбеддер разный.** У Wikontic захардкожен `facebook/contriever` (768), свой
  подставить нельзя без форка. Контролируемая переменная — LLM.
- **Контекст сохраняется только у Wikontic.** `runs/ragu_run.py` пишет один
  `<i>.txt`, поэтому `evidence_recall` и `context_relevancy` пока считаются для
  одного движка из двух. Сравнивать по ним нельзя, пока не будет симметричной
  правки в RAGU.
- **В режиме `--qa-collapsing` контекста нет вообще**: Wikontic не возвращает
  опорные триплеты с этого пути. Скрипт пишет об этом в лог; retrieval-метрики
  для такого прогона не считаются.
- **Наши костыли.** Параллельная индексация, адаптеры формы ответов, префиксы
  коллекций, resume — наши добавки, в апстриме их нет. Любая цифра, полученная с
  ними, должна это оговаривать.
