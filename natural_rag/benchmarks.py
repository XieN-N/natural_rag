"""Registry of supported benchmarks.

Single source of truth for "which benchmarks exist, where their data lives,
and which flags they need". Used by:

* ``scripts/validate_repo.py`` — checks every registered benchmark loads;
* ``docs/benchmarks.md`` — the human-readable table (keep in sync via
  ``python -m natural_rag.benchmarks``);
* run scripts — dataset names map to ``datasets/<name>`` paths and answer
  file patterns.

Datasets flagged ``in_repo=False`` are NOT committed: see the install notes in
``docs/benchmarks.md`` (they used to live in the ``datasets/ragu_benchmarks``
submodule, which had no ``.gitmodules`` and did not survive a fresh clone).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Benchmark:
    name: str
    path: str                    # relative to the repo root
    fmt: str                     # yaml-dir | jsonl | single-json
    language: str                # ISO code, for prompts/notes
    docs: int                    # documents in the corpus
    questions: int               # questions with reference answers
    short_answers: bool          # --short-answers recommended (short gold answers)
    in_repo: bool                # data committed vs manual install
    source: str                  # provenance / paper / URL
    notes: str = ""
    answers_pattern: str = ""    # glob for the consolidated answers JSON


    def default_answers_pattern(self) -> str:
        return self.answers_pattern or f"{self.name}_*.json"


BENCHMARKS: dict[str, Benchmark] = {
    b.name: b
    for b in [
        Benchmark(
            name="bl_tiny",
            path="datasets/bl_tiny",
            fmt="yaml-dir",
            language="en",
            docs=9,
            questions=12,
            short_answers=False,
            in_repo=True,
            source="The Betweenlands mod wiki (custom corpus), tiny slice",
            notes="Smoke-тест по умолчанию: полный цикл индексация+ответы "
                  "занимает ~20 минут на одном GPU. Оценка — чек-листами "
                  "(runs/ragu_evaluate.py), не LLM-судьёй.",
        ),
        Benchmark(
            name="bl_medium",
            path="datasets/bl_medium",
            fmt="yaml-dir",
            language="en",
            docs=114,
            questions=38,
            short_answers=False,
            in_repo=True,
            source="The Betweenlands mod wiki (custom corpus), medium slice",
        ),
        Benchmark(
            name="bl",
            path="datasets/bl",
            fmt="yaml-dir",
            language="en",
            docs=752,
            questions=109,
            short_answers=False,
            in_repo=True,
            source="The Betweenlands mod wiki (custom corpus), full",
            notes="Загрузчик читает только questions.yaml (109 вопросов); "
                  "questions2.yaml — доп. набор для ручных прогонов. "
                  "Готовится ноутбуками из notebooks/.",
        ),
        Benchmark(
            name="bioasq",
            path="datasets/bioasq",
            fmt="jsonl",
            language="en",
            docs=5524,
            questions=500,
            short_answers=True,
            in_repo=True,
            source="BioASQ challenge (bioasq.org), biomedical QA",
        ),
        Benchmark(
            name="musique",
            path="datasets/musique",
            fmt="jsonl",
            language="en",
            docs=5966,
            questions=498,
            short_answers=True,
            in_repo=True,
            source="MuSiQue (Trivedi et al., 2022), multi-hop QA",
            notes="Полная индексация Wikontic ≈ 4.3 суток в один поток — "
                  "для смоука используйте LIMIT_DOCS.",
        ),
        Benchmark(
            name="2wikimultihopqa",
            path="datasets/2wikimultihopqa/2wikimultihopqa.json",
            fmt="single-json",
            language="en",
            docs=6120,
            questions=1000,
            short_answers=True,
            in_repo=True,
            source="2WikiMultihopQA (Ho et al., 2020)",
            notes="Один JSON: документы собираются из context/evidences "
                  "вопросов. Для смоука --limit-questions/--limit-docs.",
        ),
        Benchmark(
            name="hotpotqa",
            path="datasets/hotpotqa",
            fmt="jsonl",
            language="en",
            docs=5717,
            questions=500,
            short_answers=True,
            in_repo=True,
            source="HotpotQA (Yang et al., 2018)",
        ),
        Benchmark(
            name="hotpotqa_500",
            path="datasets/hotpotqa_500",
            fmt="jsonl",
            language="en",
            docs=4941,
            questions=500,
            short_answers=True,
            in_repo=True,
            source="HotpotQA (Yang et al., 2018), 500-question subset",
        ),
        Benchmark(
            name="financebench",
            path="datasets/financebench",
            fmt="jsonl",
            language="en",
            docs=915,
            questions=150,
            short_answers=True,
            in_repo=True,
            source="FinanceBench (Patronus AI), financial QA",
        ),
        # --- НЕ в репозитории: ставятся вручную, см. docs/benchmarks.md ---
        Benchmark(
            name="multiq",
            path="datasets/multiq",
            fmt="jsonl",
            language="ru",
            docs=0,
            questions=0,
            short_answers=True,
            in_repo=False,
            source="Mera / GraphRAG-Bench русскоязычный MultiQ",
            notes="Ставится вручную (бывший datasets/ragu_benchmarks). "
                  "Исторически файл ответов назывался multi_q_answers.json — "
                  "паттерн multi*_answers.json ловит оба варианта.",
            answers_pattern="multi*_answers.json",
        ),
        Benchmark(
            name="chegeka",
            path="datasets/chegeka",
            fmt="jsonl",
            language="ru",
            docs=0,
            questions=0,
            short_answers=True,
            in_repo=False,
            source="ЧГК («Что? Где? Когда?»), GraphRAG-Bench",
            notes="Ставится вручную (бывший datasets/ragu_benchmarks).",
        ),
        Benchmark(
            name="graphrag_bench_medical",
            path="datasets/graphrag_bench_medical",
            fmt="jsonl",
            language="en",
            docs=0,
            questions=0,
            short_answers=False,
            in_repo=False,
            source="GraphRAG-Bench, medical subset",
            notes="Ставится вручную. Оценивается внешним GraphRAG-Benchmark "
                  "(judge gemini-3-flash-preview), short-answers НЕ "
                  "рекомендуется — роняет ROUGE-L.",
        ),
    ]
}


def get_benchmark(name: str) -> Benchmark:
    try:
        return BENCHMARKS[name]
    except KeyError:
        known = ", ".join(sorted(BENCHMARKS))
        raise KeyError(f"Unknown benchmark {name!r}. Known: {known}") from None


def _main() -> None:
    """Print the registry as a markdown table (for docs/benchmarks.md)."""
    header = (
        "| Бенчмарк | Формат | Язык | Документов | Вопросов | "
        "short-answers | В репо | Источник |"
    )
    print(header)
    print("|---|---|---|---|---|---|---|---|")
    for b in BENCHMARKS.values():
        docs = str(b.docs) if b.in_repo else "—"
        questions = str(b.questions) if b.in_repo else "—"
        print(
            f"| `{b.name}` | {b.fmt} | {b.language} | {docs} | {questions} | "
            f"{'да' if b.short_answers else 'нет'} | "
            f"{'да' if b.in_repo else 'вручную'} | {b.source} |"
        )


if __name__ == "__main__":
    _main()
