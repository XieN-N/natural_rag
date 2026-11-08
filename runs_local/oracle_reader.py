"""Answer questions from an ideal context, to measure what the reader can do at best.

Uses the same no-abstain short-answer prompt as the ``*_na`` variants. The context
replaces retrieval with one of:

  docs   only the gold documents of the question;
  facts  only the graph entities and relations extracted from those documents;
  noisy  the context of a saved run (``--noise-variant``) with any missing gold
         documents appended to its chunks.

Comparing the three with a real run separates the losses: ``docs`` is the reader's
ceiling, ``docs - facts`` is what extraction loses, ``docs - noisy`` is what noise
costs, and ``docs`` minus the real run is what retrieval loses.

Output has the usual layout (``answers/<i>.txt``, ``<i>.context.json``), so
``eval_graphrag_bench.sh`` and ``compare_runs.py`` work on variants named
``<prefix>_docs`` and so on. Answered questions are skipped.

    python runs_local/oracle_reader.py docs facts noisy --ids 100-497 --prefix meno_oracle \
        --noise-variant meno_base_na --base-url http://127.0.0.1:8711/v1 --model meno-lite-0.1
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import networkx as nx
from jinja2 import Template
from openai import AsyncOpenAI, BadRequestError

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from natural_rag.pipelines.ragu_pipelines import (
    NO_ABSTAIN_SHORT_ANSWER_PROMPT,
    extract_final_answer,
    reason_first_prompt,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("kinds", nargs="+", choices=["docs", "facts", "noisy"])
    parser.add_argument("--dataset", default="musique")
    parser.add_argument("--index-model", default="gpt-oss-20b")
    parser.add_argument("--ids", default="100-497", help="Question index range, inclusive")
    parser.add_argument("--prefix", default="meno_oracle", help="Variants are <prefix>_<kind>")
    parser.add_argument("--noise-variant", default="meno_base_na", help="Saved run whose context is the noise")
    parser.add_argument("--missing-first", action="store_true", help="noisy: put missing gold documents before the context")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8711/v1"))
    parser.add_argument("--model", default=os.environ.get("ANSWER_MODEL", "meno-lite-0.1"))
    parser.add_argument("--max-completion-tokens", type=int, default=512)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--reason-first", action="store_true", help="Short reasoning before the answer, as --reason-first of ragu_run.py")
    parser.add_argument("--dry-run", action="store_true", help="Write contexts only, without calling the model")
    return parser.parse_args()


def facts_by_chunk(index_dir: Path) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Graph entities and relations per source chunk id."""
    graph = nx.read_gml(index_dir / "knowledge_graph.gml", label="label")
    entities: dict[str, list[dict]] = defaultdict(list)
    relations: dict[str, list[dict]] = defaultdict(list)
    for _, data in graph.nodes(data=True):
        for chunk in data.get("source_chunk_id", []) or []:
            entities[chunk].append(data)
    for _, _, data in graph.edges(data=True):
        for chunk in data.get("source_chunk_id", []) or []:
            relations[chunk].append(data)
    return entities, relations


def render_chunks(texts: list[str]) -> str:
    return "\n**Chunks**\n" + "\n".join(texts) + "\n"


def render_facts(entities: list[dict], relations: list[dict]) -> str:
    """Same section format as ``LocalSearchRetrieve.to_text``, without the rank column."""
    lines = ["", "**Entities**", "Entity, entity type, entity description"]
    lines += [f"{e['entity_name']}, {e['entity_type']}, {e['description']}" for e in entities]
    lines += ["", "**Relations**", "Subject, relation type, object, relation description"]
    lines += [f"{r['subject_name']}, {r['relation_type']}, {r['object_name']} - {r['description']}" for r in relations]
    return "\n".join(lines) + "\n"


def unique(items: list[dict]) -> list[dict]:
    seen, kept = set(), []
    for item in items:
        key = id(item)
        if key not in seen:
            seen.add(key)
            kept.append(item)
    return kept


async def main() -> None:
    args = parse_args()
    data_dir = REPO_ROOT / "datasets" / args.dataset
    run_root = REPO_ROOT / "generated"
    index_dir = run_root / f"ragu_{args.dataset}/{args.dataset}/{args.index_model}/index"
    corpus = {}
    for line in (data_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        corpus[doc["doc_id"]] = doc["text"]
    questions = [json.loads(line) for line in (data_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lo, hi = (int(x) for x in args.ids.split("-"))
    hi = min(hi, len(questions) - 1)

    chunks_by_doc: dict[str, list[str]] = defaultdict(list)
    chunks = json.loads((index_dir / "kv_chunks.json").read_text(encoding="utf-8"))
    for chunk_id, chunk in chunks.items():
        chunks_by_doc[chunk["doc_id"]].append(chunk_id)
    entities, relations = facts_by_chunk(index_dir) if "facts" in args.kinds else ({}, {})
    noise_dir = run_root / f"ragu_{args.dataset}__{args.noise_variant}/{args.dataset}/{args.index_model}/answers"

    def build_context(kind: str, i: int) -> str:
        gold = questions[i]["gold_doc_ids"]
        if kind == "docs":
            return render_chunks([corpus[g].strip() for g in gold])
        if kind == "facts":
            ids = [c for g in gold for c in chunks_by_doc.get(hashlib.md5(("\0" + corpus[g]).encode("utf-8")).hexdigest(), [])]
            return render_facts(
                unique([e for c in ids for e in entities.get(c, [])]),
                unique([r for c in ids for r in relations.get(c, [])]),
            )
        saved = json.loads((noise_dir / f"{i}.context.json").read_text(encoding="utf-8"))["context"]
        text = saved[0] if saved else ""
        missing = [corpus[g].strip() for g in gold if corpus[g].strip()[:200] not in text]
        if not missing:
            return text.rstrip() + "\n"
        if args.missing_first:
            return render_chunks(missing) + text
        return text.rstrip() + "\n" + "\n".join(missing) + "\n"

    prompt_text = reason_first_prompt(NO_ABSTAIN_SHORT_ANSWER_PROMPT) if args.reason_first else NO_ABSTAIN_SHORT_ANSWER_PROMPT
    template = Template(prompt_text)
    client = AsyncOpenAI(base_url=args.base_url, api_key=os.environ.get("OPENAI_API_KEY", "local"), timeout=600, max_retries=8)
    semaphore = asyncio.Semaphore(args.concurrency)

    async def answer(kind: str, i: int, out_dir: Path) -> None:
        answer_path = out_dir / f"{i}.txt"
        if answer_path.exists():
            return
        context = build_context(kind, i)
        (out_dir / f"{i}.context.json").write_text(
            json.dumps({"context": [context], "context_tokens": None, "metrics": {"oracle": kind}}, ensure_ascii=False),
            encoding="utf-8",
        )
        if args.dry_run:
            return
        prompt = template.render(query=questions[i]["question"], context=context, language="english")
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.chat.completions.create(
                    model=args.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=args.max_completion_tokens,
                )
            except BadRequestError as exc:
                # Typically a context over the model limit: leave it unanswered and visible.
                print(f"{kind} {i}: request rejected: {str(exc)[:200]}", flush=True)
                return
        text = (response.choices[0].message.content or "").strip()
        raw = text
        if args.reason_first:
            text = extract_final_answer(text)
        answer_path.write_text(text, encoding="utf-8")
        saved = json.loads((out_dir / f"{i}.context.json").read_text(encoding="utf-8"))
        saved["answer_seconds"] = time.perf_counter() - started
        if args.reason_first:
            saved["raw_answer"] = raw
        (out_dir / f"{i}.context.json").write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")

    for kind in args.kinds:
        out_dir = run_root / f"ragu_{args.dataset}__{args.prefix}_{kind}/{args.dataset}/{args.index_model}/answers"
        out_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.gather(*(answer(kind, i, out_dir) for i in range(lo, hi + 1)))
        print(f"{kind}: {len(list(out_dir.glob('*.txt')))} answers in {out_dir}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
