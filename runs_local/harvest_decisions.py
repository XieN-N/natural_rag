"""Collect pointwise decision-model requests from LLM caches, with gold labels.

Every request ``DecisionModel.a_score_pointwise`` sends goes through
``CachedAsyncOpenAI.option_probabilities`` and lands in the run's LLM cache with
the exact conversation and the returned option masses. This script reads those
caches, recovers which question and which candidate (chunk, relation or
entity) each prompt was about, and labels the candidate by the question's gold
documents: a chunk is positive when it comes from a gold document, a relation
or entity when any of its source chunks does. The output is one JSON line per
unique prompt, used to measure and to train the calibration of a decision model.

    python runs_local/harvest_decisions.py --dataset-path datasets/musique \
        --index-dir generated/ragu_musique/musique/gpt-oss-20b/index \
        --cache tmp/llm_cache_dm --cache tmp/llm_cache_dm_h2p30 --out decisions_musique.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import diskcache

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ragu.chunker.types import Chunk
from ragu.common.global_parameters import Settings
from ragu.common.logger import logger
from ragu.common.prompts.messages import render
from ragu.common.prompts.prompt_storage import DEFAULT_PROMPT_TEMPLATES
from ragu.graph.graph_builder_pipeline import BuilderArguments
from ragu.graph.knowledge_graph import KnowledgeGraph
from ragu.models.embedder import EmbedderOpenAI
from ragu.models.openai import CachedAsyncOpenAI
from ragu.search_engine.decision_search import _format_entity, _format_relation
from ragu.utils.ragu_utils import compute_mdhash_id

from natural_rag.dataset import RAGDataset

SENTINELS = {"query": "\x00Q\x00", "state": "\x00S\x00", "candidate": "\x00C\x00"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--cache", action="append", required=True, help="LLM cache directory; repeat for several")
    parser.add_argument("--out", required=True)
    parser.add_argument("--embedding-dim", type=int, default=768, help="Of the index vectors (gte-multilingual-base: 768)")
    return parser.parse_args()


def prompt_patterns() -> tuple[str, list[re.Pattern]]:
    """System text and user-message patterns of the pointwise prompt, with and without state."""
    instruction = DEFAULT_PROMPT_TEMPLATES["decision_pointwise"]
    system, patterns = None, []
    for state in (SENTINELS["state"], ""):
        conv = render(instruction.messages, query=SENTINELS["query"], state_context=state,
                      candidate=[SENTINELS["candidate"]])[0].to_openai()
        system = conv[0]["content"]
        pattern = re.escape(conv[-1]["content"])
        for name, sentinel in (("query", SENTINELS["query"]), ("state", SENTINELS["state"]),
                               ("candidate", SENTINELS["candidate"])):
            pattern = pattern.replace(re.escape(sentinel), f"(?P<{name}>.*?)")
        patterns.append(re.compile(f"^{pattern}$", re.DOTALL))
    return system, patterns


async def load_graph(index_dir: Path, dim: int):
    Settings.storage_folder = str(index_dir)
    # the embedder is never called: only stored nodes and edges are read
    embedder = EmbedderOpenAI(CachedAsyncOpenAI(base_url="http://127.0.0.1:9/v1", api_key="unused"), "unused", dim=dim)
    kg = KnowledgeGraph(llm=None, embedder=embedder, builder_settings=BuilderArguments(use_llm_summarization=False))
    return await kg.index.graph_backend.get_all_nodes(), await kg.index.graph_backend.get_all_edges()


def main() -> None:
    args = parse_args()
    logger.remove()
    index_dir = (REPO_ROOT / args.index_dir).resolve()
    ds = RAGDataset.load_auto(str(REPO_ROOT / args.dataset_path))
    dataset_name = Path(args.dataset_path).stem if Path(args.dataset_path).suffix else Path(args.dataset_path).name

    # candidate text -> objects, built with the same formatters DecisionSearch uses
    chunks = {cid: Chunk(**payload) for cid, payload in
              json.loads((index_dir / "kv_chunks.json").read_text(encoding="utf-8")).items()}
    nodes, edges = asyncio.run(load_graph(index_dir, args.embedding_dim))
    by_text: dict[str, dict[str, list]] = {"chunk": collections.defaultdict(list),
                                           "relation": collections.defaultdict(list),
                                           "entity": collections.defaultdict(list)}
    for cid, chunk in chunks.items():
        by_text["chunk"][chunk.content].append({cid})
    for edge in edges:
        by_text["relation"][_format_relation(edge)].append(set(edge.source_chunk_id or []))
    for node in nodes:
        by_text["entity"][_format_entity(node)].append(set(node.source_chunk_id or []))

    # question text -> index, and per question the chunks of its gold documents
    md5_to_chunks = collections.defaultdict(set)
    for cid, chunk in chunks.items():
        md5_to_chunks[chunk.doc_id].add(cid)
    question_index = collections.defaultdict(list)
    gold_chunks = []
    for i, q in enumerate(ds.questions):
        question_index[q.text].append(i)
        gold = set()
        for loc in q.relevant or []:
            doc = ds.documents.get(loc.doc_id)
            if doc is not None and doc.text:
                gold |= md5_to_chunks.get(compute_mdhash_id(doc.text), set())
        gold_chunks.append(gold)
    no_gold = sum(1 for g in gold_chunks if not g)

    system, patterns = prompt_patterns()
    stats = collections.Counter()
    seen = set()
    with open(args.out, "w", encoding="utf-8") as out:
        for cache_dir in args.cache:
            variant = Path(cache_dir).name
            cache = diskcache.Cache(cache_dir)
            for key in cache.iterkeys():
                if not isinstance(key, str) or '"option_probabilities"' not in key:
                    continue
                k = json.loads(key)
                if k.get("method") != "option_probabilities" or sorted(k.get("options", [])) != ["N", "Y"]:
                    continue
                conv = k["conversation"]
                if len(conv) != 2 or conv[0]["content"] != system:
                    stats["other prompt"] += 1
                    continue
                match = next((m for p in patterns if (m := p.match(conv[1]["content"]))), None)
                if match is None:
                    stats["unparsed"] += 1
                    continue
                digest = hashlib.md5(key.encode("utf-8")).hexdigest()
                if digest in seen:
                    stats["duplicate"] += 1
                    continue
                seen.add(digest)
                query, candidate = match.group("query"), match.group("candidate")
                state = match.groupdict().get("state") or ""
                qids = question_index.get(query)
                if not qids:
                    stats["unknown question"] += 1
                    continue
                kinds = [kind for kind in ("chunk", "relation", "entity") if candidate in by_text[kind]]
                if len(kinds) != 1:
                    stats["unmatched candidate" if not kinds else "ambiguous kind"] += 1
                    continue
                kind = kinds[0]
                gold = gold_chunks[qids[0]]
                label = int(any(sources & gold for sources in by_text[kind][candidate]))
                _args, masses = cache.get(key)
                m_y, m_n = float(masses.get("Y", 0.0)), float(masses.get("N", 0.0))
                row = {
                    "dataset": dataset_name, "question": qids[0], "hop": 2 if state else 1, "kind": kind,
                    "label": label, "mass_y": m_y, "mass_n": m_n,
                    "p_yes": m_y / (m_y + m_n) if m_y + m_n > 0 else None,
                    "model": k["model_name"], "variant": variant, "key": digest, "messages": conv,
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                stats[f"rows {kind} hop{row['hop']}"] += 1
                stats["positives"] += label
            cache.close()
    print(f"{dataset_name}: {len(ds.questions)} questions, {no_gold} without gold chunks in the index")
    for name, count in sorted(stats.items()):
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
