"""Un-mark documents as indexed so ``--resume`` processes them again.

A document counts as done when it has at least one triplet
(``WikonticPipeline.count_triplets``). That check cannot tell a real extraction
from a fragment, so a document written with a single salvaged triplet is
permanently stuck: it never shows up in ``empty_docs`` and ``--resume`` skips it
forever. Deleting its points from ``initial_triplets`` and ``triplets`` restores
the "not indexed" state and the next run redoes it properly.

Find the affected documents in the run log first (the log marks them with a
check mark, so match on the tail of the line instead)::

    grep -E "Done: .* \\(1 triplets\\)" logs/<RUN_ID>/main.log

Then, with Qdrant running over the run's storage directory::

    python runs_cluster/retry_documents.py \\
        --qdrant-url http://127.0.0.1:16400 \\
        --collection-prefix <RUN_ID> \\
        Medical__p0017 Medical__p0023

That prints what would be removed and changes nothing. Add ``--apply`` to
actually delete.
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from natural_rag.wikontic_prefix import sanitize_prefix  # noqa: E402

import httpx

from natural_rag.url_guard import assert_http_url

#: Only these decide whether count_triplets() considers a document done.
#: entity_aliases / property_aliases are a shared dictionary that re-populates
#: on reindex; filtered_triplets is never probed.
COLLECTIONS = ("initial_triplets", "triplets")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("documents", nargs="*",
                   help="sample_id of each document, as printed in the run log "
                        "(corpus scope: the document name, e.g. Medical__p0017).")
    p.add_argument("--qdrant-url", required=True,
                   help="Qdrant holding the index. Start it over the run's "
                        "storage directory first; the job's own Qdrant is gone "
                        "once the job ends.")
    p.add_argument("--collection-prefix", required=True,
                   help="RUN_ID or collection prefix. Sanitized the same way "
                        "PrefixedBackend does, so a dotted model name works.")
    p.add_argument("--apply", action="store_true",
                   help="Actually delete. Without it nothing is modified.")
    return p.parse_args()


def request(url: str, payload: dict | None = None) -> dict:
    assert_http_url(url, what="--qdrant-url")
    response = httpx.request(
        "POST" if payload is not None else "GET",
        url, json=payload, timeout=120,
    )
    response.raise_for_status()
    return response.json()


def doc_filter(sample_id: str) -> dict:
    """Match exactly what count_triplets() reads back."""
    return {"must": [{"key": "sample_id", "match": {"value": sample_id}}]}


def count_points(url: str, collection: str, sample_id: str) -> int | None:
    """Points belonging to ``sample_id``, or None when the collection is absent."""
    try:
        result = request(f"{url}/collections/{collection}/points/count",
                         {"filter": doc_filter(sample_id), "exact": True})
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return result.get("result", {}).get("count")


def delete_points(url: str, collection: str, sample_id: str) -> None:
    request(f"{url}/collections/{collection}/points/delete?wait=true",
            {"filter": doc_filter(sample_id)})


def main() -> int:
    args = parse_args()

    if not args.documents:
        # An empty filter deletes a whole collection in Qdrant. Making that
        # unreachable by accident is worth more than the convenience of
        # a "do everything" mode.
        raise SystemExit(
            "No documents given. Name each one explicitly — this tool deletes, "
            "and an empty document list must never turn into an empty filter."
        )

    prefix = sanitize_prefix(args.collection_prefix)
    url = assert_http_url(args.qdrant_url.rstrip("/"), what="--qdrant-url")
    if prefix != args.collection_prefix:
        print(f"prefix: {args.collection_prefix!r} -> {prefix!r} (sanitized)")

    total = 0
    missing: list[str] = []
    for sample_id in args.documents:
        counts: dict[str, int] = {}
        for name in COLLECTIONS:
            collection = f"{prefix}__{name}"
            points = count_points(url, collection, sample_id)
            if points is None:
                print(f"  MISSING COLLECTION {collection}")
                continue
            counts[collection] = points
        found = sum(counts.values())
        total += found
        status = "ok" if found else "нечего удалять"
        print(f"{sample_id}: {found} point(s)  [{status}]")
        for collection, points in counts.items():
            print(f"    {points:6d}  {collection}")
        if not found:
            missing.append(sample_id)

    if missing:
        print(f"\nБез точек: {', '.join(missing)} — проверьте sample_id "
              f"(в corpus-scope это имя документа из лога) и префикс.")

    if not args.apply:
        print(f"\nDry-run: ничего не изменено. Удалить эти {total} точек — "
              f"повторите команду с --apply.")
        return 0

    if not total:
        print("\nНечего удалять, выходим.")
        return 0

    print()
    for sample_id in args.documents:
        for name in COLLECTIONS:
            collection = f"{prefix}__{name}"
            if count_points(url, collection, sample_id):
                delete_points(url, collection, sample_id)
                left = count_points(url, collection, sample_id)
                print(f"удалено: {sample_id} из {collection} (осталось {left})")

    print("\nГотово. Документы больше не считаются проиндексированными — "
          "следующий sbatch с --resume их переберёт.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
