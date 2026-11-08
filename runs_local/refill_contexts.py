"""Rebuild the context of a logged best-first run with another budget or layout (no LLM calls).

A run made with ``--decision-log`` keeps every judged candidate with its ``P(Y)`` in
``metrics["decisions"]``. This script fills the context again the way
``DecisionSearchEngine._fill_context`` does, so the walk and the decisions stay exactly
those of the logged run and only the budget or the layout changes. The output holds
``<i>.context.json`` only; answer it with ``runs_local/oracle_reader.py saved``.

    python runs_local/refill_contexts.py a_log ctx_1500 --budget 1500 --ids 100-497
    python runs_local/refill_contexts.py a_log ctx_sections --layout sections --ids 100-497

``--check`` compares the rebuilt context with the one the run really used instead of
writing anything: with the run's own budget and layout they must be identical.

The ``sections`` layout groups the same lines under the section headers of
``LocalSearchRetrieve``. It reuses the format of the log, so relation lines have no
rank column; the comparison is about grouping and order.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import tiktoken

REPO_ROOT = Path(__file__).resolve().parent.parent
SECTIONS = ("entities", "relations", "chunks")
ENTITY = re.compile(r"^(?P<name>.*) \((?P<type>[^()]*)\): (?P<description>.*)$", re.DOTALL)
RELATION = re.compile(r"^(?P<subject>.*?) --\[(?P<type>.*?)\]--> (?P<object>.*?): (?P<description>.*)$", re.DOTALL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", help="Variant saved with --decision-log")
    parser.add_argument("target", nargs="?", help="Variant to write the contexts to")
    parser.add_argument("--dataset", default="musique")
    parser.add_argument("--index-model", default="gpt-oss-20b")
    parser.add_argument("--ids", default="100-497")
    parser.add_argument("--budget", type=int, default=3000)
    parser.add_argument("--layout", choices=["flat", "sections"], default="flat")
    parser.add_argument("--encoding-model", default="gpt-4o-mini", help="tiktoken model of the context budget")
    parser.add_argument("--check", action="store_true", help="Compare with the saved context, write nothing")
    return parser.parse_args()


def fill(decisions: list[list], budget: int, encoder: tiktoken.Encoding) -> list[tuple[str, str]]:
    """The items that fit into the budget, most probable first: (section, text)."""
    ordered = [row for section in SECTIONS for row in decisions if row[0] == section]
    ordered.sort(key=lambda row: -row[1])
    kept, tokens = [], 0
    for section, _, _, text in ordered:
        size = len(encoder.encode(text))
        if tokens + size > budget:
            continue
        tokens += size
        kept.append((section, text))
    # An item judged by two parallel branches keeps its last P(Y) for ordering, as in
    # DecisionSearchResult.probabilities; the context lists sections in this order.
    last = {row[3]: row[1] for row in decisions}
    grouped = [item for section in SECTIONS for item in kept if item[0] == section]
    grouped.sort(key=lambda item: -last[item[1]])
    return grouped


def render_flat(items: list[tuple[str, str]]) -> str:
    return "\n**Evidence, most useful first**\n" + "\n".join(text for _, text in items) + "\n"


def render_sections(items: list[tuple[str, str]]) -> str:
    """Section headers of ``LocalSearchRetrieve``, lines in the order of ``items``."""
    entities, relations, chunks = [], [], []
    for section, text in items:
        if section == "entities":
            match = ENTITY.match(text)
            entities.append(f"{match['name']}, {match['type']}, {match['description']}" if match else text)
        elif section == "relations":
            match = RELATION.match(text)
            relations.append(f"{match['subject']}, {match['type']}, {match['object']} - {match['description']}" if match else text)
        else:
            chunks.append(text)
    lines = ["**Entities**", "Entity, entity type, entity description", *entities, "",
             "**Relations**", "Subject, relation type, object, relation description", *relations]
    if chunks:
        lines += ["", "**Chunks**", *chunks]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    encoder = tiktoken.encoding_for_model(args.encoding_model)
    base = REPO_ROOT / "generated"
    source = base / f"ragu_{args.dataset}__{args.source}/{args.dataset}/{args.index_model}/answers"
    target = None
    if not args.check:
        if not args.target:
            raise SystemExit("target variant is required without --check")
        target = base / f"ragu_{args.dataset}__{args.target}/{args.dataset}/{args.index_model}/answers"
        target.mkdir(parents=True, exist_ok=True)
    render = render_flat if args.layout == "flat" else render_sections
    lo, hi = (int(x) for x in args.ids.split("-"))
    written = same = missing = 0
    for i in range(lo, hi + 1):
        path = source / f"{i}.context.json"
        if not path.exists():
            missing += 1
            continue
        saved = json.loads(path.read_text(encoding="utf-8"))
        decisions = (saved.get("metrics") or {}).get("decisions")
        if decisions is None:
            raise SystemExit(f"{path} has no decision log; run with --decision-log")
        text = render(fill(decisions, args.budget, encoder))
        if args.check:
            same += text.strip() == (saved["context"][0] if saved["context"] else "").strip()
            written += 1
            continue
        (target / f"{i}.context.json").write_text(
            json.dumps({"context": [text], "context_tokens": len(encoder.encode(text)),
                        "metrics": {"refilled_from": args.source, "budget": args.budget, "layout": args.layout}},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        written += 1
    if args.check:
        print(f"identical contexts: {same} of {written}; missing runs: {missing}")
    else:
        print(f"written {written} contexts to {target}; missing runs: {missing}")


if __name__ == "__main__":
    main()
