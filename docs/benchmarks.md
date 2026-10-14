# Бенчмарки

Реестр (машиночитаемый): `natural_rag/benchmarks.py`. Обновить таблицу:
`python -m natural_rag.benchmarks`. Количества сверяются автоматически:
`python scripts/validate_repo.py`.

| Бенчмарк | Формат | Язык | Документов | Вопросов | short-answers | В репо | Источник |
|---|---|---|---|---|---|---|---|
| `bl_tiny` | yaml-dir | en | 9 | 12 | нет | да | The Betweenlands mod wiki (custom corpus), tiny slice |
| `bl_medium` | yaml-dir | en | 114 | 38 | нет | да | The Betweenlands mod wiki (custom corpus), medium slice |
| `bl` | yaml-dir | en | 752 | 109 | нет | да | The Betweenlands mod wiki (custom corpus), full |
| `bioasq` | jsonl | en | 5524 | 500 | да | да | BioASQ challenge (bioasq.org), biomedical QA |
| `musique` | jsonl | en | 5966 | 498 | да | да | MuSiQue (Trivedi et al., 2022), multi-hop QA |
| `2wikimultihopqa` | single-json | en | 6120 | 1000 | да | да | 2WikiMultihopQA (Ho et al., 2020) |
| `hotpotqa` | jsonl | en | 5717 | 500 | да | да | HotpotQA (Yang et al., 2018) |
| `hotpotqa_500` | jsonl | en | 4941 | 500 | да | да | HotpotQA (Yang et al., 2018), 500-question subset |
| `financebench` | jsonl | en | 915 | 150 | да | да | FinanceBench (Patronus AI), financial QA |
| `multiq` | jsonl | ru | — | — | да | вручную | Mera / GraphRAG-Bench русскоязычный MultiQ |
| `chegeka` | jsonl | ru | — | — | да | вручную | ЧГК («Что? Где? Когда?»), GraphRAG-Bench |
| `graphrag_bench_medical` | jsonl | en | — | — | нет | вручную | GraphRAG-Bench, medical subset |

## Форматы

- **yaml-dir**: `corpus_info.yaml` + `docs/*.md` + `questions.yaml` (BL-семейство).
- **jsonl**: `corpus.jsonl` (`doc_id`, `title`, `text`) + `questions.jsonl`
  (`question`, `answer`, `answer_aliases`, `gold_doc_ids`).
- **single-json**: один файл 2WikiMultihopQA; документы собираются из
  `context`/`evidences` вопросов (дедуп → 6120 доков).

Загрузка: `RAGDataset.load_auto(path)` — формат определяется по структуре
каталога/файла.

## Особенности по датасетам

- **bl_tiny** — smoke-тест по умолчанию: полный цикл индексация+ответы ~20
  минут на 1 GPU. Оценка чек-листами (`runs/ragu_evaluate.py`), не судьёй.
- **bl** — загрузчик читает `questions.yaml` (109 вопросов);
  `questions2.yaml` — дополнительный набор для ручных прогонов. Корпус
  готовится ноутбуками из `notebooks/`.
- **musique** — полная индексация Wikontic ≈ 4.3 суток в один поток; для
  смоука `LIMIT_DOCS` / `--limit-docs`.
- **graphrag_bench_medical** — оценивается внешним GraphRAG-Benchmark
  (судья gemini-3-flash-preview); `--short-answers` НЕ использовать —
  роняет ROUGE-L (49 → 12).

## Ручная установка внешних датасетов

`multiq`, `chegeka`, `graphrag_bench_medical` раньше жили в сабмодуле
`datasets/ragu_benchmarks`, у которого не было `.gitmodules` — после
свежего клона он не восстанавливался, поэтому gitlink удалён. Данные нужно
положить вручную:

```
datasets/multiq/               # corpus.jsonl + questions.jsonl
datasets/chegeka/              # corpus.jsonl + questions.jsonl
datasets/graphrag_bench_medical/
```

(источник — репозиторий ragu_benchmarks авторов RAGU / GraphRAG-Bench;
форматы те же jsonl). После установки проверьте, что загрузчик их видит:

```
python scripts/validate_repo.py
```

Они перечислены в реестре как `in_repo=False`: валидатор не падает, если их
нет, но загрузит и проверит, если папки появились.

## Повреждённые данные (исправлено)

В `datasets/hotpotqa/corpus.jsonl` и `datasets/financebench/corpus.jsonl`
последняя строка была обрезана (незакрытый JSON — файл оборвался при заливке)
и валила весь датасет при загрузке. Обрезанные хвосты удалены в ветке
`cleanup-reproducibility`; на вопросы они не ссылались.
