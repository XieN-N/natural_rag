"""Collect one benchmark's scores into a single Markdown table.

The numbers of a finished run end up spread over four files -- GraphRAG-Bench's
``generation_results.json`` and ``retrieval_results.json``, our own
``eval_results.json``, and the raw ``answers/`` directory -- in three different
shapes. Retyping them into a report is how a digit goes wrong silently, so this
reads them instead.

It also splits every metric by whether Wikontic actually answered. Wikontic's
``qa`` prompt tells the model to return ``None`` when the retrieved triplets do
not contain an answer, and those refusals score a flat zero on ROUGE and
coverage. Reporting only the pooled average hides whether a low number means
"answers badly" or "often declines to answer" -- a distinction that points at
different halves of the system.

    python runs_local/report_results.py \\
        --output-dir generated/<RUN_ID>__gpt-4o-mini \\
        --dataset-path <dataset> --index-model gpt-oss-20b
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from natural_rag.paths import resolve_run_dirs  # noqa: E402

# Order metrics the way GraphRAG-Bench's metric_config defines them per type,
# so the table reads like the benchmark's own reporting.
METRIC_ORDER = ["rouge_score", "answer_correctness", "coverage_score", "faithfulness"]
TYPE_ORDER = ["Fact Retrieval", "Complex Reasoning",
              "Contextual Summarize", "Creative Generation"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--dataset-path", type=Path, required=True)
    p.add_argument("--index-model", default=None)
    p.add_argument("--answer-model", default="gpt-4o-mini")
    p.add_argument("--judge-model", default="gemini-3-flash-preview")
    p.add_argument("--hop-depth", type=int, default=1)
    p.add_argument("--bundle", type=Path, default=None,
                   help="Bundle directory; its manifest.json supplies indexing "
                        "facts that belong next to the scores (empty_docs, mode).")
    p.add_argument("--note", action="append", default=[],
                   help="Caveat to list under 'Оговорки'. Repeatable.")
    p.add_argument("--out", type=Path, default=None,
                   help="Default: RESULTS_<dataset>.md in the repo root.")
    return p.parse_args()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def mean(values: list) -> float | None:
    clean = [v for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    return statistics.mean(clean) if clean else None


def fmt(value) -> str:
    return f"{value:.3f}" if isinstance(value, float) else "—"


def sort_types(names) -> list:
    return sorted(names, key=lambda t: (TYPE_ORDER.index(t) if t in TYPE_ORDER else 99, t))


def main() -> int:
    args = parse_args()
    _, answers_dir, base = resolve_run_dirs(
        args.output_dir, args.dataset_path, args.index_model
    )
    dataset_name = base.parent.name if args.index_model else base.name

    generation = load(base / "generation_results.json")
    retrieval = load(base / "retrieval_results.json")
    # judge_answers.py wraps its numbers in {"summary": ..., "rows": [...]}.
    free = load(base / "eval_results.json")
    if isinstance(free, dict) and "summary" in free:
        free = free["summary"]
    if generation is None:
        raise SystemExit(f"No generation_results.json in {base}")

    lines: list[str] = []
    add = lines.append
    add(f"# GraphRAG-Bench — {dataset_name}")
    add("")
    add(f"Индексация **{args.index_model}** · ответы **{args.answer_model}** · "
        f"судья **{args.judge_model}** · `hop_depth={args.hop_depth}`")
    add(f"Собрано {date.today().isoformat()} из `{base}`.")
    add("")

    # ── generation ────────────────────────────────────────────────
    add("## Генерация")
    add("")
    present = [m for m in METRIC_ORDER
               if any(m in (r.get("average_scores") or r) for r in generation.values())]
    add("| Тип вопроса | n | " + " | ".join(present) + " |")
    add("|---|---:|" + "---:|" * len(present))
    for qtype in sort_types(generation):
        result = generation[qtype]
        scores = result.get("average_scores") or result
        detailed = result.get("detailed") or []
        row = [qtype, str(len(detailed) or "?")]
        row += [fmt(scores.get(m)) for m in present]
        add("| " + " | ".join(row) + " |")
    add("")

    # ── retrieval ─────────────────────────────────────────────────
    if retrieval:
        add("## Retrieval")
        add("")
        add("| Тип вопроса | context_relevancy | evidence_recall |")
        add("|---|---:|---:|")
        for qtype in sort_types(retrieval):
            r = retrieval[qtype]
            add(f"| {qtype} | {fmt(r.get('context_relevancy'))} "
                f"| {fmt(r.get('evidence_recall'))} |")
        add("")
        add("Считаются по сохранённым триплетам, поэтому доступны только для "
            "Wikontic: `runs/ragu_run.py` контекст не пишет. Межсистемному "
            "сравнению эти две строки не подлежат.")
        add("")

    # ── answered vs refused ───────────────────────────────────────
    add("## Отказы")
    add("")
    add("Wikontic возвращает `None`, когда в извлечённых триплетах ответа нет. "
        "Такие случаи дают ноль по ROUGE и coverage, поэтому общее среднее "
        "смешивает «отвечает плохо» и «часто не отвечает».")
    add("")
    add("| Тип вопроса | метрика | все | ответившие | отказы | отказов |")
    add("|---|---|---:|---:|---:|---:|")
    for qtype in sort_types(generation):
        detailed = generation[qtype].get("detailed") or []
        if not detailed:
            continue
        answered = [x for x in detailed if str(x.get("generated_answer", "")).strip() != "None"]
        refused = [x for x in detailed if str(x.get("generated_answer", "")).strip() == "None"]
        for metric in present:
            if metric not in (detailed[0].get("metrics") or {}):
                continue
            pick = lambda rows: mean([r["metrics"].get(metric) for r in rows])
            add(f"| {qtype} | {metric} | {fmt(pick(detailed))} | "
                f"{fmt(pick(answered))} | {fmt(pick(refused))} | {len(refused)} |")
    add("")

    # ── free metrics ──────────────────────────────────────────────
    if free:
        add("## EM / token-F1 (без судьи)")
        add("")
        add("Не входят в протокол GraphRAG-Bench; приведены как дешёвая "
            "перекрёстная проверка. EM около нуля — артефакт формата: ответы "
            "развёрнутые, эталоны короткие, `--short-answers` намеренно не "
            "ставился.")
        add("")
        add("| Тип вопроса | n | EM | token-F1 |")
        add("|---|---:|---:|---:|")
        for qtype in sort_types(free.get("by_group", {})):
            g = free["by_group"][qtype]
            add(f"| {qtype} | {g.get('n')} | {fmt(g.get('em'))} | {fmt(g.get('f1'))} |")
        add(f"| **всего** | {free.get('n')} | {fmt(free.get('em'))} "
            f"| {fmt(free.get('f1'))} |")
        add("")

    # ── coverage of the numbers themselves ────────────────────────
    nan_notes = []
    for qtype in sort_types(generation):
        detailed = generation[qtype].get("detailed") or []
        for metric in present:
            bad = sum(1 for x in detailed
                      if metric in (x.get("metrics") or {})
                      and not isinstance(x["metrics"][metric], (int, float)))
            bad += sum(1 for x in detailed
                       if isinstance((x.get("metrics") or {}).get(metric), float)
                       and math.isnan(x["metrics"][metric]))
            if bad:
                nan_notes.append(f"- `{metric}` / {qtype}: {bad} из {len(detailed)} "
                                 f"не посчитано, среднее взято по остальным")
    add("## Полнота")
    add("")
    if nan_notes:
        add("Средние считаются через `nanmean`, то есть несосчитанные сэмплы "
            "выпадают молча. Здесь выпали:")
        add("")
        lines.extend(nan_notes)
    else:
        add("Все сэмплы посчитаны, пропусков нет.")
    add("")

    # ── caveats ───────────────────────────────────────────────────
    notes = list(args.note)
    manifest = load(args.bundle / "manifest.json") if args.bundle else None
    if manifest:
        if manifest.get("empty_docs"):
            notes.append(
                f"**{manifest['empty_docs']} документ(а) не попали в граф** при "
                f"индексации (`empty_docs` в манифесте). Вопросы, опирающиеся на "
                f"них, не могут быть отвечены никакой моделью."
            )
        notes.append(
            f"Граф: режим `{manifest.get('mode')}`, scope `{manifest.get('scope')}`, "
            f"{manifest.get('n_docs')} документов, {manifest.get('llm_calls')} вызовов "
            f"LLM, {manifest.get('wall_seconds', 0) / 3600:.1f} ч индексации."
        )
    if notes:
        add("## Оговорки")
        add("")
        for note in notes:
            add(f"- {note}")
        add("")

    out_path = args.out or (REPO_ROOT / f"RESULTS_{dataset_name}.md")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
