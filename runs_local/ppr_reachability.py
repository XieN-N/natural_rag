"""Offline: does Personalized PageRank over a RAGU graph surface the gold chunks?

Graph: entity-entity edges from the index (undirected, weight = number of
relations) plus entity-chunk edges (entity <-> each of its source chunks).
Personalized PageRank with ``--alpha`` (0.5 as in HippoRAG 2). Seeds:

  A: the ``--top-k`` entities LocalSearch retrieves, weighted by similarity;
  B: A plus every chunk weighted 0.05 * cosine(query, chunk) (HippoRAG 2 passage seeds).

Reports gold-chunk recall in the top-k chunks by PageRank score, by plain query
cosine, and for "seed-entity chunks + top-k new chunks" (what an augmenting
variant would hand to the reader). No LLM calls; needs the embedder only:

    python runs_local/ppr_reachability.py --ids 0-99
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

import networkx as nx
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

KS = (5, 10, 20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset-path", default="datasets/musique")
    parser.add_argument("--index-dir", default="generated/ragu_musique/musique/gpt-oss-20b/index")
    parser.add_argument("--embed-base-url", default="http://127.0.0.1:8002/v1")
    parser.add_argument("--embedding-model-name", default="gte-multilingual-base")
    parser.add_argument("--embedding-dim", type=int, default=768)
    parser.add_argument("--ids", default="0-99", help="Question index range, inclusive")
    parser.add_argument("--top-k", type=int, default=20, help="Seed entities, as LocalSearch top_k")
    parser.add_argument("--alpha", type=float, default=0.5, help="PageRank damping")
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

    started = time.time()
    graph = nx.Graph()
    for entity in await kg.index.graph_backend.get_all_nodes():
        graph.add_node(entity.id)
        for chunk_id in entity.source_chunk_id:
            graph.add_edge(entity.id, chunk_id, weight=1.0)
    for edge in await kg.index.graph_backend.get_all_edges():
        if graph.has_edge(edge.subject_id, edge.object_id):
            graph[edge.subject_id][edge.object_id]["weight"] += 1.0
        else:
            graph.add_edge(edge.subject_id, edge.object_id, weight=1.0)

    # chunk vectors straight from the NanoVDB file
    payload = json.loads((index_dir / "vdb_chunk.json").read_text(encoding="utf-8"))
    chunk_ids = [item["__id__"] for item in payload["data"]]
    chunk_matrix = np.frombuffer(base64.b64decode(payload["matrix"]), dtype=np.float32).reshape(-1, payload["embedding_dim"])
    chunk_matrix = chunk_matrix / np.linalg.norm(chunk_matrix, axis=1, keepdims=True)
    chunk_set = set(chunk_ids)
    chunk_nodes = [n for n in graph.nodes if n in chunk_set]
    print(f"graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges, {len(chunk_nodes)} chunks "
          f"({time.time() - started:.1f}s)")

    ds = RAGDataset.load_auto(str(dataset_path))
    corpus_doc = {key: compute_mdhash_id(doc.text) for key, doc in ds.documents.items() if doc.text}
    chunks = json.loads((index_dir / "kv_chunks.json").read_text(encoding="utf-8"))
    chunks_by_doc = defaultdict(set)
    for chunk_id, chunk in chunks.items():
        chunks_by_doc[chunk["doc_id"]].add(chunk_id)
    questions = [json.loads(line) for line in (dataset_path / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    start, end = (int(x) for x in args.ids.split("-"))

    rows, ppr_seconds = [], []
    for qi in range(start, min(end, len(questions) - 1) + 1):
        q = questions[qi]
        gold = set().union(*(chunks_by_doc[corpus_doc[g]] for g in q["gold_doc_ids"]))
        (seeds, hits), = await retriever.query_entities([q["question"]], top_k=args.top_k)
        [qpoint] = await retriever.build_query_vectors([q["question"]])
        qvec = np.asarray(qpoint.dense_embedding, dtype=np.float32)
        qvec /= np.linalg.norm(qvec) or 1.0
        base_chunks = set().union(*(set(e.source_chunk_id) for e in seeds))

        cos = chunk_matrix @ qvec
        by_cos = [chunk_ids[i] for i in np.argsort(-cos)]

        seed_a = {e.id: max(float(h.distance), 1e-6) for e, h in zip(seeds, hits) if e.id in graph}
        seed_b = dict(seed_a)
        for cid, score in zip(chunk_ids, cos):
            if cid in graph:
                seed_b[cid] = seed_b.get(cid, 0.0) + 0.05 * max(float(score), 0.0)

        row = {"hops": q.get("hops"), "base": len(gold & base_chunks) / len(gold)}
        for name, seed in (("A", seed_a), ("B", seed_b)):
            t0 = time.time()
            scores = nx.pagerank(graph, alpha=args.alpha, personalization=seed, weight="weight", tol=1e-6)
            ppr_seconds.append(time.time() - t0)
            ranked = sorted(chunk_nodes, key=lambda n: -scores.get(n, 0.0))
            ranked_new = [c for c in ranked if c not in base_chunks]
            for k in KS:
                row[f"{name}@{k}"] = len(gold & set(ranked[:k])) / len(gold)
                row[f"base+{name}@{k}"] = len(gold & (base_chunks | set(ranked_new[:k]))) / len(gold)
        cos_new = [c for c in by_cos if c not in base_chunks]
        for k in KS:
            row[f"cos@{k}"] = len(gold & set(by_cos[:k])) / len(gold)
            row[f"base+cos@{k}"] = len(gold & (base_chunks | set(cos_new[:k]))) / len(gold)
        rows.append(row)

    def mean(key, hops=None):
        values = [r[key] for r in rows if hops is None or r["hops"] == hops]
        return f"{100 * st.mean(values):5.1f}%" if values else "   - "

    hop_kinds = sorted({r["hops"] for r in rows if r["hops"] is not None})
    print(f"questions {start}-{start + len(rows) - 1}: n={len(rows)}; pagerank {st.median(ppr_seconds):.2f}s median per run")
    keys = ["base"] + [f"{p}@{k}" for p in ("cos", "A", "B") for k in KS] + \
           [f"base+{p}@{k}" for p in ("cos", "A", "B") for k in KS]
    for key in keys:
        print(f"{key:12s} {mean(key)}   " + "  ".join(f"{h}h {mean(key, h)}" for h in hop_kinds))


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
