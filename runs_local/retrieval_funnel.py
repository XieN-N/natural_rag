"""Where gold documents and answers get lost on the way to the reader (no LLM calls).

For each question it follows the gold documents through the stages of a saved run:
indexed -> extracted into the graph -> source chunk of a seed entity -> reachable
in one hop -> in a decision pool -> passed the decision threshold -> in the answer
context. At question level it checks whether the reference answer string occurs in
the gold documents, in the graph facts extracted from them, in the context, and in
the generated answer.

Seeds come from the variant's saved ``metrics["entities"]``, decisions from the
jsonl written by ``runs_local/harvest_decisions.py``. The harvest deduplicates
prompts across variants, so its pools are a union over the harvested runs and the
second-hop numbers are an upper bound for any single run.

    python runs_local/retrieval_funnel.py meno_t01 --ids 100-497 \
        --decisions ../itmo_results/calib.tar.gz --decisions-member calib/meno_musique.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics as st
import string
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_RE = re.compile(r"Candidate:\n(.*?)\n\nIs this candidate", re.DOTALL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("variants", nargs="+")
    parser.add_argument("--dataset", default="musique")
    parser.add_argument("--index-model", default="gpt-oss-20b")
    parser.add_argument("--index-dir", default=None, help="Default: generated/ragu_<dataset>/<dataset>/<index-model>/index")
    parser.add_argument("--ids", default="100-497", help="Question index range, inclusive")
    parser.add_argument("--decisions", default=None, help="Harvested decisions: a .jsonl or a .tar.gz holding it")
    parser.add_argument("--decisions-member", default=None, help="Member name inside the tar archive")
    parser.add_argument("--threshold", type=float, default=0.1)
    parser.add_argument("--json-out", default=None, help="Write per-question rows here")
    return parser.parse_args()


def normalize(text: str) -> str:
    text = "".join(c for c in text.lower() if c not in string.punctuation)
    return " ".join(re.sub(r"\b(a|an|the)\b", " ", text).split())


def read_decisions(path: str, member: str | None) -> Iterator[dict[str, Any]]:
    if path.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path) as archive:
            handle = archive.extractfile(member)
            for line in handle:
                yield json.loads(line)
    else:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                yield json.loads(line)


def load_graph(index_dir: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    """Return entity -> source chunks, entity -> neighbours, chunk -> normalized fact texts."""
    graph = nx.read_gml(index_dir / "knowledge_graph.gml", label="label")
    entity_chunks: dict[str, set[str]] = {}
    neighbours: dict[str, set[str]] = defaultdict(set)
    chunk_facts: dict[str, set[str]] = defaultdict(set)
    for node, data in graph.nodes(data=True):
        chunks = {c for c in data.get("source_chunk_id", []) or [] if str(c).startswith("chunk-")}
        entity_chunks[node] = chunks
        text = normalize(f"{data.get('entity_name', '')} {data.get('description', '')}")
        for chunk in chunks:
            chunk_facts[chunk].add(text)
    for subject, obj, data in graph.edges(data=True):
        neighbours[subject].add(obj)
        neighbours[obj].add(subject)
        chunks = {c for c in data.get("source_chunk_id", []) or [] if str(c).startswith("chunk-")}
        text = normalize(f"{data.get('subject_name', '')} {data.get('object_name', '')} {data.get('description', '')}")
        for chunk in chunks:
            chunk_facts[chunk].add(text)
    return entity_chunks, neighbours, chunk_facts


def load_pools(path: str, member: str | None, content_to_chunk: dict[str, str], lo: int, hi: int, threshold: float):
    """Return (question, hop) -> chunk ids in the pool and chunk ids passing the threshold."""
    pooled: dict[tuple[int, int], set[str]] = defaultdict(set)
    passed: dict[tuple[int, int], set[str]] = defaultdict(set)
    unmatched = 0
    for row in read_decisions(path, member):
        question = int(row["question"])
        if row["kind"] != "chunk" or not lo <= question <= hi:
            continue
        match = CANDIDATE_RE.search(row["messages"][-1]["content"])
        chunk = content_to_chunk.get(match.group(1).strip()) if match else None
        if chunk is None:
            unmatched += 1
            continue
        key = (question, int(row["hop"]))
        pooled[key].add(chunk)
        if float(row["p_yes"]) >= threshold:
            passed[key].add(chunk)
    if unmatched:
        print(f"decisions: {unmatched} chunk prompts not matched to the index")
    return pooled, passed


def report(variant: str, rows: list[dict[str, Any]], has_pools: bool) -> None:
    gold_total = sum(r["gold"] for r in rows)
    stages = ["indexed", "extracted", "seed_chunk", "one_hop", "pool_h1", "passed_h1", "pool_h2", "passed_h2", "in_context"]
    print(f"\n=== {variant}: {len(rows)} questions, {gold_total} gold documents")
    for stage in stages:
        if stage.startswith(("pool", "passed")) and not has_pools:
            continue
        count = sum(r[stage] for r in rows)
        print(f"  {stage:12s} {count:5d}  {100 * count / gold_total:5.1f}%")

    def share(key: str, subset: list[dict[str, Any]]) -> str:
        return f"{100 * st.mean(r[key] for r in subset):5.1f}%" if subset else "    -"

    keys = ["answer_in_gold", "answer_in_gold_facts", "answer_in_seed_chunks", "answer_in_context", "correct"]
    print("  answer string, by question:")
    groups = [("all", rows)] + [(f"{h}-hop", [r for r in rows if r["hops"] == h]) for h in sorted({r["hops"] for r in rows})]
    print("    " + " " * 22 + "".join(f"{name:>8s}" for name, _ in groups))
    for key in keys:
        print(f"    {key:22s}" + "".join(f"{share(key, subset):>8s}" for _, subset in groups))


def main() -> None:
    args = parse_args()
    data_dir = REPO_ROOT / "datasets" / args.dataset
    index_dir = Path(args.index_dir) if args.index_dir else (
        REPO_ROOT / f"generated/ragu_{args.dataset}/{args.dataset}/{args.index_model}/index"
    )
    corpus = {}
    for line in (data_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        corpus[doc["doc_id"]] = doc["text"]
    questions = [json.loads(line) for line in (data_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lo, hi = (int(x) for x in args.ids.split("-"))

    chunks = json.loads((index_dir / "kv_chunks.json").read_text(encoding="utf-8"))
    chunks_by_doc: dict[str, set[str]] = defaultdict(set)
    content_to_chunk: dict[str, str] = {}
    for chunk_id, chunk in chunks.items():
        chunks_by_doc[chunk["doc_id"]].add(chunk_id)
        content_to_chunk[chunk["content"].strip()] = chunk_id
    entity_chunks, neighbours, chunk_facts = load_graph(index_dir)

    pooled: dict[tuple[int, int], set[str]] = {}
    passed: dict[tuple[int, int], set[str]] = {}
    if args.decisions:
        pooled, passed = load_pools(args.decisions, args.decisions_member, content_to_chunk, lo, hi, args.threshold)

    all_rows = {}
    for variant in args.variants:
        answers = REPO_ROOT / f"generated/ragu_{args.dataset}__{variant}/{args.dataset}/{args.index_model}/answers"
        rows = []
        for i in range(lo, min(hi, len(questions) - 1) + 1):
            path = answers / f"{i}.context.json"
            answer_path = answers / f"{i}.txt"
            if not path.exists() or not answer_path.exists():
                continue
            saved = json.loads(path.read_text(encoding="utf-8"))
            context = saved["context"][0] if saved["context"] else ""
            normalized_context = normalize(context)
            q = questions[i]
            references = [normalize(a) for a in [q["answer"], *q.get("answer_aliases", [])] if normalize(a)]
            seeds = [e["id"] for e in saved["metrics"].get("entities", [])]
            seed_chunks = set().union(*(entity_chunks.get(s, set()) for s in seeds)) if seeds else set()
            one_hop = set()
            for seed in seeds:
                for other in neighbours.get(seed, ()):
                    one_hop |= entity_chunks.get(other, set())
            one_hop |= seed_chunks

            row = {"i": i, "hops": q.get("hops"), "gold": len(q["gold_doc_ids"])}
            for stage in ("indexed", "extracted", "seed_chunk", "one_hop", "pool_h1", "passed_h1", "pool_h2", "passed_h2", "in_context"):
                row[stage] = 0
            gold_chunks, gold_text = set(), []
            for doc_id in q["gold_doc_ids"]:
                text = corpus[doc_id]
                gold_text.append(normalize(text))
                # Same value as ragu.utils.ragu_utils.compute_mdhash_id(text).
                doc_chunks = chunks_by_doc.get(hashlib.md5(("\0" + text).encode("utf-8")).hexdigest(), set())
                gold_chunks |= doc_chunks
                row["indexed"] += bool(doc_chunks)
                row["extracted"] += any(c in chunk_facts for c in doc_chunks)
                row["seed_chunk"] += bool(doc_chunks & seed_chunks)
                row["one_hop"] += bool(doc_chunks & one_hop)
                row["pool_h1"] += bool(doc_chunks & pooled.get((i, 1), set()))
                row["passed_h1"] += bool(doc_chunks & passed.get((i, 1), set()))
                row["pool_h2"] += bool(doc_chunks & pooled.get((i, 2), set()))
                row["passed_h2"] += bool(doc_chunks & passed.get((i, 2), set()))
                row["in_context"] += text.strip()[:200] in context

            def has_answer(texts: Any) -> bool:
                return any(ref in text for ref in references for text in texts)

            seed_text = [normalize(chunks[c]["content"]) for c in seed_chunks if c in chunks]
            generated = normalize(answer_path.read_text(encoding="utf-8"))
            row["answer_in_gold"] = has_answer(gold_text)
            row["answer_in_gold_facts"] = has_answer(t for c in gold_chunks for t in chunk_facts.get(c, ()))
            row["answer_in_seed_chunks"] = has_answer(seed_text)
            row["answer_in_context"] = has_answer([normalized_context])
            row["correct"] = has_answer([generated])
            rows.append(row)
        report(variant, rows, bool(pooled))
        all_rows[variant] = rows
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(all_rows), encoding="utf-8")


if __name__ == "__main__":
    main()
