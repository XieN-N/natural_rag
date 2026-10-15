# AGENTS.md — инструкция для агентов, работающих с natural_rag

Рабочий язык проекта — русский. Это исследовательский фреймворк для
сравнения GraphRAG-движков (RAGU, LightRAG, NanoGraphRAG, FastGraphRAG,
HippoRAG, Wikontic + безграфовый baseline) на QA-бенчмарках.

Личный исследовательский журнал (контекст сравнения RAGU vs Wikontic,
найденные баги, история решений) — `docs/research_journal.md`. Историю
«почему так» ищите там; этот файл описывает «как устроено сейчас».

## Карта репозитория

| Путь | Назначение |
|---|---|
| `natural_rag/` | Пакет: загрузка датасетов (`dataset.py`), реестр бенчмарков (`benchmarks.py`), пути вывода (`paths.py`), тайминг (`timing.py`), обёртки движков (`pipelines/`), чек-лист-оценка, дашборд |
| `runs/` | **Канонические раннеры и оценка** — по одному python-скрипту на движок + скрипты оценки/утилиты (см. `runs/README.md`) |
| `runs_cluster/` | SLURM-обёртки для кластера НГУ: sbatch-скрипты, smoke, экспорт индексов, прогресс (см. `runs_cluster/README.md`) |
| `runs_local/` | Локальные утилиты: ответы по готовому индексу через API, валидация/экспорт индексов, отчёты (см. `runs_local/README.md`) |
| `scripts/` | Утилиты установки (`setup_wikontic_ontology.py`) и самопроверка репо (`validate_repo.py`) |
| `datasets/` | Бенчмарки; 9 датасетов в репо + 3 внешних ставятся вручную (`docs/benchmarks.md`) |
| `notebooks/` | Ноутбуки подготовки BL-корпуса (bl, bl_medium, bl_tiny) |
| `legacy/` | `bl_orig_questions.yaml` — исходные вопросы BL до чистки |
| `generated/` | Выводы прогонов (gitignored): `generated/<engine>_<dataset>/<dataset>/[<index-model>/]{index,answers}` |

## Канонические раннеры (правило «один движок — один скрипт»)

| Движок/задача | Скрипт | Примечание |
|---|---|---|
| RAGU | `runs/ragu_run.py` | query engines: local / query_plan / naive; `--index-model`, `--short-answers`, `--limit-docs/questions` |
| LightRAG | `runs/lightrag_run.py` | |
| FastGraphRAG | `runs/fast_graphrag_run.py` | |
| NanoGraphRAG | `runs/nano_graphrag_run.py` | |
| HippoRAG | `runs/run_hippo.py` | |
| Baseline (без графа) | `runs/baseline_run.py` | |
| Wikontic | `runs/wikontic_run.py` | режимы dynamic/structured, scope corpus/per_sample |
| .txt → JSON ответов | `runs/convert_answers.py` | |
| LLM-судья | `runs/jsonl_llm_judge_evaluate.py` | не зависит от движка (чистый OpenAI-клиент) |
| Чек-лист-оценка BL | `runs/ragu_evaluate.py` | |
| Судья + EM/F1 по индексу | `runs/judge_answers.py` | зовётся из `runs_cluster/eval_universal.sh` |

Все раннеры конфигурируются argparse-флагами с env-fallback (DATASET_PATH,
OUTPUT_DIR, OPENAI_BASE_URL, LLM_MODEL, EMBED_MODEL, EMBEDDING_DIM, …).
Кластерные обёртки НЕ дублируют логику — только поднимают vLLM/Qdrant и
вызывают канонические раннеры с env. **Не создавайте копий раннеров под
конкретный датасет/модель — параметризуйте существующие.** (Исторически
появились ~30 копий в runs_universal/ — удалены в cleanup-reproducibility.)

Для смоука любого бенчмарка: `--limit-docs N --limit-questions N`.

## Бенчмарки

Реестр — `natural_rag/benchmarks.py` (имя → путь, формат, язык, кол-ва,
флаги). Таблица для людей — `docs/benchmarks.md` (обновляется
`python -m natural_rag.benchmarks`). Загрузка любого датасета:
`RAGDataset.load_auto(path)` — формат определяется автоматически
(yaml-dir / jsonl / single-json).

## Установка

Python ≥3.12, uv или pip. База: `uv pip install -e .`. Движки — extras:
`.[ragu]` (рекомендуется), `.[lightrag]`, `.[nano-graphrag]`,
`.[fast-graphrag]`, `.[hipporag]`, `.[wikontic]`, `.[baseline]`, `.[all]`.

**Релиз и dev-сборка RAGU взаимоисключающие** — оба ставят пакет `ragu`
(dev-ветка принимает EngineParams в a_search/a_query; обёртка понимает оба,
но ставить что-то одно). Релиз — extra `.[ragu]`; dev-ветка — ручная команда
из runs/README.md (git-URL-extra ломал бы uv lock: два URL на один пакет).

## Нормы работы (из журнала, проверенные практикой)

- **Кластер**: только через sbatch; партиции a100/a800; Docker запрещён;
  на вычислительных узлах нет интернета (модели/кэши локальные); сетевая ФС
  медленная (`--qdrant-timeout 120`).
- **Рабочая копия на кластере** `/userspace/sse/natural_rag` — НЕ трогать и
  ничего в ней не удалять: там живые прогоны и индексы. Проверки — в
  отдельной новой папке.
- **Перед длинным прогоном**: назвать цену в GPU-часах и риск; смоук на
  bl_tiny (~20 мин, 1 GPU) обязателен. `runs_cluster/smoke_index.sh`.
- **CRLF**: `.gitattributes` держит LF для `*.sh` — не отменять; sbatch
  отвергает DOS line breaks.
- **Ответственный LLM-ответчик один на все движки** (gpt-4o-mini),
  судья — другой (gemini-3-flash-preview): так изолируется качество
  построения графа. Короткие ответы (`--short-answers`) для бенчмарков с
  короткими эталонами, но НЕ для GraphRAG-Bench.
- **Проверки кода без счёта**: `python scripts/validate_repo.py` — все
  бенчмарки грузятся, весь python/bash парсится; `runs/test_all.py --dry-run`
  печатает команды всех пайплайнов.

## Типичные ошибки (подробнее — журнал)

- **openai ≥3 ломает любой RAGU** (0.0.3 и dev): у RAGU в logger.py хак
  `openai._utils._logs.httpx_logger`, удалённый в openai 3. В базовых
  зависимостях пин `openai>=2.21.0,<3` — не поднимать. Проверено
  2026-10-14: 0.0.3 + openai 2.21–2.54 работают, 3.x — нет.
- vLLM/transformers пины: transformers ≥5 ломает конфиг GigaChat
  (пин `>=4.40,<5` в extra wikontic); `VLLM_USE_FLASHINFER_SAMPLER=0` при
  CUDA 11.
- Точка в имени модели → имя qdrant-коллекции: см. `sanitize_prefix`
  (`natural_rag/wikontic_prefix.py`).
- Молчаливая потеря документов: следить за `NO TRIPLETS STORED`/`empty_docs`
  (`natural_rag/graph_health.py`).
- Забытый `export` в сессии до sbatch когда-то молча подменил датасет —
  поэтому пресеты `runs_cluster/launch_*.sh` зашивают конфиг и запускаются
  голым `sbatch`.
