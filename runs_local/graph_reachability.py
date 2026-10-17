"""Offline ceiling of multi-hop traversal over a RAGU index (no LLM calls).

For each question the seed entities are found the way LocalSearch finds them
(``--top-k`` by query similarity), then the graph is walked breadth-first.
Per hop it reports the cumulative share of gold chunks reachable through the
entities' source chunks, how many candidates each hop adds, and how well plain
query cosine ranks the newly reachable gold chunks among a hop's chunks. This
tells whether more hops can help at all before paying for a decision model.

Needs only the embedder (``runs_local/serve_embedder.py``) and dev RAGU:

    python runs_local/graph_reachability.py --ids 0-99
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ragu.common.global_parameters import Settings
from ragu.common.logger import logger
from ragu.graph.graph_builder_pipeline import BuilderArguments
from ragu.graph.graph_retrieve_backend import GraphRetriever
from ragu.graph.knowledge_graph import KnowledgeGraph
from ragu.models.embedder import EmbedderOpenAI
from ragu.models.openai import CachedAsyncOpenAI
from ragu.utils.ragu_utils import compute_mdhash_id

from natural_rag.dataset import RAGDataset

POOL_KS = (10, 30, 100)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset-path", default="datasets/musique")
    parser.add_argument("--index-dir", default="generated/ragu_musique/musique/gpt-oss-20b/index")
    parser.add_argument("--embed-base-url", default="http://127.0.0.1:8002/v1")
    parser.add_argument("--embedding-model-name", default="gte-multilingual-base")
    parser.add_argument("--embedding-dim", type=int, default=768)
    parser.add_argument("--ids", default="0-99", help="Question index range, inclusive")
    parser.add_argument("--top-k", type=int, default=20, help="Seed entities, as LocalSearch top_k")
    parser.add_argument("--max-hops", type=int, default=3)
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    logger.remove()
    index_dir = (REPO_ROOT / args.index_dir).resolve()
    dataset_path = REPO_ROOT / args.dataset_path
    Settings.storage_folder = str(index_dir)
    client = CachedAsyncOpenAI(base_url=args.embed_base_url, api_key="local")
    embedder = EmbedderOpenAI(client, args.embedding_model_name, dim=args.embedding_dim)
    kg = KnowledgeGraph(llm=None, embedder=embedder, builder_settings=BuilderArguments(use_llm_summarization=False))
    retriever = GraphRetriever(knowledge_graph=kg, embedder=embedder)
    index = kg.index

    # gold documents -> chunk ids (RAGU stores doc_id = md5 of the document text)
    ds = RAGDataset.load_auto(str(dataset_path))
    corpus_doc = {key: compute_mdhash_id(doc.text) for key, doc in ds.documents.items() if doc.text}
    chunks = json.loads((index_dir / "kv_chunks.json").read_text(encoding="utf-8"))
    chunks_by_doc = defaultdict(set)
    for chunk_id, chunk in chunks.items():
        chunks_by_doc[chunk["doc_id"]].add(chunk_id)
    questions = [json.loads(line) for line in (dataset_path / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    start, end = (int(x) for x in args.ids.split("-"))

    rows = []
    for qi in range(start, min(end, len(questions) - 1) + 1):
        q = questions[qi]
        gold = set().union(*(chunks_by_doc[corpus_doc[g]] for g in q["gold_doc_ids"]))
        (seeds, _), = await retriever.query_entities([q["question"]], top_k=args.top_k)
        [qpoint] = await retriever.build_query_vectors([q["question"]])
        qvec = np.asarray(qpoint.dense_embedding, dtype=np.float32)
        qvec /= np.linalg.norm(qvec) or 1.0

        visited = {e.id for e in seeds}
        frontier = list(seeds)
        reached_chunks = set().union(*(set(e.source_chunk_id) for e in seeds))
        row = {"hops": q.get("hops"), "recall": [len(gold & reached_chunks) / len(gold)],
               "edges": [], "new_entities": [], "new_chunks": [len(reached_chunks)], "rank_recall": []}

        # gold among the default chunk pool: seed chunks, top-10 by cosine
        seed_chunk_ids = sorted(reached_chunks)
        points = await index.chunks_vector_db.get_points_by_ids(seed_chunk_ids)
        sims = sorted(((float(np.dot(np.asarray(p.dense_embedding, dtype=np.float32), qvec)) if p else -1.0, c)
                       for p, c in zip(points, seed_chunk_ids)), reverse=True)
        row["pool10_recall"] = len(gold & {c for _, c in sims[:10]}) / len(gold)

        for _ in range(args.max_hops):
            edge_lists = await index.graph_backend.get_all_edges_for_nodes([e.id for e in frontier])
            edges = [edge for edges in edge_lists for edge in edges if edge]
            neighbor_ids = sorted({x for edge in edges for x in (edge.subject_id, edge.object_id)} - visited)
            neighbors = [n for n in await index.get_nodes(neighbor_ids) if n is not None]
            visited.update(n.id for n in neighbors)
            new_chunks = set().union(*(set(n.source_chunk_id) for n in neighbors)) - reached_chunks if neighbors else set()
            new_gold = gold & new_chunks
            if new_chunks:
                ids = sorted(new_chunks)
                pts = await index.chunks_vector_db.get_points_by_ids(ids)
                order = [c for _, c in sorted(((float(np.dot(np.asarray(p.dense_embedding, dtype=np.float32), qvec)) if p else -1.0, c)
                                               for p, c in zip(pts, ids)), reverse=True)]
                row["rank_recall"].append({k: (len(new_gold & set(order[:k])) / len(new_gold)) if new_gold else None
                                           for k in POOL_KS})
            else:
                row["rank_recall"].append({k: None for k in POOL_KS})
            reached_chunks |= new_chunks
            row["recall"].append(len(gold & reached_chunks) / len(gold))
            row["edges"].append(len(edges))
            row["new_entities"].append(len(neighbors))
            row["new_chunks"].append(len(new_chunks))
            frontier = neighbors
        rows.append(row)

    def mean(values):
        values = [v for v in values if v is not None]
        return f"{100 * st.mean(values):5.1f}%" if values else "   - "

    hop_kinds = sorted({r["hops"] for r in rows if r["hops"] is not None})
    print(f"questions {start}-{start + len(rows) - 1}: n={len(rows)}")
    print(f"gold in the default chunk pool (top-10 of seed chunks): {mean([r['pool10_recall'] for r in rows])}")
    for hop in range(args.max_hops + 1):
        line = f"hop<= {hop}: gold recall {mean([r['recall'][hop] for r in rows])}"
        for h in hop_kinds:
            line += f"  {h}-hop {mean([r['recall'][hop] for r in rows if r['hops'] == h])}"
        line += f"  all-gold {sum(1 for r in rows if r['recall'][hop] == 1.0):3d}"
        if hop:
            line += (f" | edges med {st.median(r['edges'][hop - 1] for r in rows):6.0f}"
                     f" new ents med {st.median(r['new_entities'][hop - 1] for r in rows):6.0f}"
                     f" new chunks med {st.median(r['new_chunks'][hop] for r in rows):5.0f}")
            line += " | new-gold@k " + " ".join(
                f"{k}:{mean([r['rank_recall'][hop - 1][k] for r in rows])}" for k in POOL_KS)
        else:
            line += f" | seed chunks med {st.median(r['new_chunks'][0] for r in rows):.0f}"
        print(line)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
