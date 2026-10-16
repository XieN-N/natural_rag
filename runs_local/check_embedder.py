"""Check that an embedding endpoint reproduces the vectors stored in a RAGU index.

A RAGU index is searched by cosine similarity between the query embedding and
the stored entity/relation/chunk embeddings. If the endpoint used for queries
is not the model (and pooling/normalization) that built the index, search
silently returns noise. This script re-embeds a sample of texts stored in the
NanoVDB files of the index and compares them with the stored vectors:

    python runs_local/check_embedder.py \\
        --index-dir generated/ragu_musique/musique/gpt-oss-20b/index \\
        --base-url http://127.0.0.1:8002/v1 --model gte-multilingual-base

The text RAGU embeds for each store (``ragu.graph.index``):
chunks -> ``content``, entities -> ``"{entity_name} - {description}"``,
relations -> ``description``. Very long texts may have been truncated by the
embedder token limit at indexing time, so the sample skips them by default.

Exit code is 0 when the minimum cosine over the sample is at least
``--min-cosine``, otherwise 1.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np

STORES = {
    "vdb_chunk.json": lambda item: item.get("content", ""),
    "vdb_entity.json": lambda item: f"{item.get('entity_name')} - {item.get('description')}",
    "vdb_relation.json": lambda item: f"{item.get('description')}",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("EMBED_BASE_URL", "http://127.0.0.1:8002/v1"),
        help="OpenAI-compatible endpoint (env EMBED_BASE_URL)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("EMBED_MODEL_NAME", "gte-multilingual-base"),
        help="Model name sent in requests (env EMBED_MODEL_NAME)",
    )
    parser.add_argument("--api-key", default=os.environ.get("EMBED_API_KEY", "local"))
    parser.add_argument("--n", type=int, default=24, help="Texts sampled per store")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=4000,
        help="Skip texts longer than this (they may have been truncated at indexing)",
    )
    parser.add_argument("--min-cosine", type=float, default=0.99)
    parser.add_argument(
        "--stores",
        nargs="+",
        default=list(STORES),
        choices=list(STORES),
    )
    return parser.parse_args()


def load_store(path: Path) -> tuple[list[dict], np.ndarray]:
    """Return (records, matrix) from a NanoVectorDB JSON file."""
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    dim = int(payload["embedding_dim"])
    matrix = np.frombuffer(base64.b64decode(payload["matrix"]), dtype=np.float32).reshape(-1, dim)
    records = payload["data"]
    if len(records) != len(matrix):
        raise ValueError(f"{path.name}: {len(records)} records but {len(matrix)} vectors")
    return records, matrix


def embed(base_url: str, model: str, api_key: str, texts: list[str]) -> np.ndarray:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/embeddings",
        data=json.dumps({"model": model, "input": texts, "encoding_format": "float"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        payload = json.load(response)
    rows = sorted(payload["data"], key=lambda row: row["index"])
    return np.asarray([row["embedding"] for row in rows], dtype=np.float32)


def unit(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def main() -> int:
    args = parse_args()
    overall_min = 1.0
    for store in args.stores:
        path = args.index_dir / store
        if not path.exists():
            print(f"{store}: not found, skipped")
            continue
        records, matrix = load_store(path)
        to_text = STORES[store]
        candidates = [
            i for i, item in enumerate(records)
            if 0 < len(to_text(item)) <= args.max_chars
        ]
        if not candidates:
            print(f"{store}: no texts within --max-chars, skipped")
            continue
        # evenly spaced, deterministic sample
        picks = [candidates[int(k)] for k in np.linspace(0, len(candidates) - 1, min(args.n, len(candidates)))]
        texts = [to_text(records[i]) for i in picks]

        fresh = embed(args.base_url, args.model, args.api_key, texts)
        if fresh.shape[1] != matrix.shape[1]:
            print(f"{store}: dimension mismatch, endpoint {fresh.shape[1]} vs index {matrix.shape[1]}")
            return 1
        cosines = np.sum(unit(fresh) * unit(matrix[picks]), axis=1)
        overall_min = min(overall_min, float(cosines.min()))
        worst = int(np.argmin(cosines))
        print(
            f"{store}: n={len(picks)} dim={matrix.shape[1]} cosine "
            f"min={cosines.min():.5f} median={np.median(cosines):.5f} mean={cosines.mean():.5f}"
        )
        if cosines.min() < args.min_cosine:
            print(f"  worst ({cosines[worst]:.4f}): {texts[worst][:160]!r}")

    verdict = "OK" if overall_min >= args.min_cosine else "MISMATCH"
    print(f"{verdict}: min cosine {overall_min:.5f} (threshold {args.min_cosine})")
    return 0 if verdict == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
