"""Rebuild the entity-alias index of an exported bundle from its triplets.

Question answering enters the graph through ``entity_aliases`` only: the LLM
pulls entity mentions out of the question and
``Aligner.retrieve_similar_entity_names`` matches them against that collection
(``wikontic/utils/base_inference_with_db.py``). Entities absent from it are
unreachable no matter how deep the hop expansion goes.

In the ``graphrag_bench_medical`` bundle that collection held 463 entries for a
graph of 4717 distinct entities, because Wikontic's Qdrant adapter deleted and
rebuilt it whenever an alias document arrived without a vector -- see
``_VectorSafeCollection`` in ``natural_rag/wikontic_prefix.py`` for the full
chain. Three of those rebuilds exceeded Qdrant's request limit and left the
collection empty; the exception was swallowed and the indexing job still
reported ``failures: 0``.

This restores reachability without touching an LLM: every distinct subject and
object of ``__triplets`` that has no alias entry gets one, embedded with the
same contriever the index was built with (loaded via Wikontic's own ``Aligner``
so the weights and pooling cannot drift).

The entries it writes are identity aliases (``alias == label``). The original
surface-form-to-canonical mapping is gone and cannot be reconstructed; say so
wherever these numbers are reported.

    python runs_local/backfill_entity_aliases.py \\
        --bundle ~/wikontic_bundles/<RUN_ID> --dry-run
"""
from __future__ import annotations

import httpx

from natural_rag.url_guard import assert_http_url

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from answer_from_index import (  # noqa: E402
    free_port,
    load_manifest,
    resolve_storage,
    start_qdrant,
)

EMBEDDING_DIMENSIONS = 768


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true",
                   help="Report what is missing and exit without writing.")
    p.add_argument("--batch-size", type=int, default=256,
                   help="Documents per upsert. Each carries a 768-float vector, "
                        "so a large batch runs into Qdrant's request size limit.")
    p.add_argument("--device", default=None, help="cuda / cpu. Default: auto.")
    p.add_argument("--qdrant-bin", default=None)
    p.add_argument("--qdrant-url", default=None,
                   help="Use an already-running Qdrant over this bundle's storage.")
    return p.parse_args()


def scroll_payloads(url: str, collection: str) -> list[dict]:
    assert_http_url(url, what="Qdrant URL")
    payloads: list[dict] = []
    offset = None
    with httpx.Client(timeout=120) as client:
        while True:
            body: dict = {"limit": 1000, "with_payload": True, "with_vector": False}
            if offset is not None:
                body["offset"] = offset
            response = client.post(f"{url}/collections/{collection}/points/scroll", json=body)
            response.raise_for_status()
            result = response.json()["result"]
            payloads.extend(p["payload"] for p in result["points"] if p.get("payload"))
            offset = result.get("next_page_offset")
            if offset is None:
                return payloads


def main() -> int:
    args = parse_args()
    bundle = args.bundle.expanduser().resolve()
    manifest = load_manifest(bundle)
    prefix = manifest["collection_prefix"]

    process = None
    try:
        if args.qdrant_url:
            url = assert_http_url(args.qdrant_url.rstrip("/"), what="--qdrant-url")
        else:
            import os
            binary = args.qdrant_bin or os.environ.get("QDRANT_BIN", "./qdrant")
            process, url = start_qdrant(
                binary, resolve_storage(bundle, manifest), free_port(),
                bundle / "backfill_qdrant.log",
            )

        triplets = scroll_payloads(url, f"{prefix}__triplets")
        aliases = scroll_payloads(url, f"{prefix}__entity_aliases")

        # An entity is reachable if it appears as a *label*: that is what
        # retrieve_similar_entity_names returns and what the hop expansion then
        # matches against triplet subjects/objects.
        known = {a.get("label") for a in aliases if a.get("label")}
        wanted: dict[str, str] = {}
        for triplet in triplets:
            for field in ("subject", "object"):
                name = triplet.get(field)
                if isinstance(name, str) and name and name not in wanted:
                    wanted[name] = triplet.get("sample_id") or ""

        missing = {name: sid for name, sid in wanted.items() if name not in known}
        print(f"triplets          : {len(triplets)}")
        print(f"distinct entities : {len(wanted)}")
        print(f"alias entries     : {len(aliases)}  (labels: {len(known)})")
        print(f"missing           : {len(missing)}")
        if not missing:
            print("Nothing to do.")
            return 0
        if args.dry_run:
            for name in list(missing)[:15]:
                print(f"  would add {name!r}")
            print("--dry-run: nothing written.")
            return 0

        from wikontic.db.factory import create_backend
        from wikontic.utils.dynamic_aligner import Aligner

        from natural_rag.wikontic_prefix import PrefixedBackend

        backend = PrefixedBackend(
            create_backend(backend_type="qdrant", qdrant_url=url), prefix
        )
        # Registers (vector name, 768) so _upsert_documents does not decide the
        # collection has the wrong dimension and "repair" it by deleting it.
        # PrefixedBackend skips the rebuild because the vector is already there.
        backend.ensure_vector_index(
            collection_name="entity_aliases",
            index_name="entity_aliases",
            vector_field="alias_text_embedding",
            num_dimensions=EMBEDDING_DIMENSIONS,
            token_fields=["sample_id"],
        )

        aligner = Aligner(backend, device=args.device)

        batch: list[dict] = []
        written = 0
        skipped = 0
        for i, (name, sample_id) in enumerate(sorted(missing.items()), 1):
            embedding = aligner.get_embedding(name)
            if not isinstance(embedding, list) or len(embedding) != EMBEDDING_DIMENSIONS:
                skipped += 1
                continue
            batch.append({
                "label": name,
                "alias": name,
                "sample_id": sample_id,
                "alias_text_embedding": embedding,
            })
            if len(batch) >= args.batch_size:
                backend.upsert_many(
                    "entity_aliases", batch,
                    unique_fields=["label", "alias", "sample_id"],
                )
                written += len(batch)
                batch = []
                print(f"  {written}/{len(missing)} written")
        if batch:
            backend.upsert_many(
                "entity_aliases", batch,
                unique_fields=["label", "alias", "sample_id"],
            )
            written += len(batch)

        total = httpx.get(
            f"{url}/collections/{prefix}__entity_aliases", timeout=120
        ).json()["result"]["points_count"]
        print(f"\nwritten {written}, skipped {skipped} (no embedding)")
        print(f"entity_aliases now holds {total} points")
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
