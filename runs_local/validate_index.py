"""Refuse to trust a Wikontic index that is only partly there.

Exits non-zero when the graph is unusable, so a job script can stop before
spending a day answering questions against it, and ``export_index.sh`` can
refuse to ship it.

The check exists because "the run finished" says nothing about the index.
Wikontic swallows exceptions raised while a triplet is processed and files the
triplet under ``filtered_triplets`` with an ``exception_text``; a destroyed
entity index is therefore reported as ``failures: 0, status: done``. See
``natural_rag/graph_health.py`` for what is measured and why.

    # after indexing, against the live server
    python runs_local/validate_index.py \\
        --qdrant-url http://127.0.0.1:6333 --collection-prefix <RUN_ID>

    # after export, against an unpacked bundle
    python runs_local/validate_index.py --bundle ~/wikontic_bundles/<RUN_ID>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from natural_rag.graph_health import collect  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--bundle", type=Path,
                        help="Unpacked bundle; Qdrant is started over its storage.")
    source.add_argument("--qdrant-url",
                        help="Already-running Qdrant holding the index.")
    p.add_argument("--collection-prefix",
                   help="Required with --qdrant-url; taken from the manifest "
                        "with --bundle.")
    p.add_argument("--min-coverage", type=float, default=0.95,
                   help="Alias coverage below which the index is rejected.")
    p.add_argument("--json", action="store_true", help="Machine-readable output.")
    p.add_argument("--qdrant-bin", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    process = None
    try:
        if args.bundle:
            from answer_from_index import (
                free_port, load_manifest, resolve_storage, start_qdrant,
            )
            bundle = args.bundle.expanduser().resolve()
            manifest = load_manifest(bundle)
            prefix = args.collection_prefix or manifest["collection_prefix"]
            binary = args.qdrant_bin or os.environ.get("QDRANT_BIN", "./qdrant")
            process, url = start_qdrant(
                binary, resolve_storage(bundle, manifest), free_port(),
                bundle / "validate_qdrant.log",
            )
        else:
            if not args.collection_prefix:
                raise SystemExit("--collection-prefix is required with --qdrant-url")
            url, prefix = args.qdrant_url.rstrip("/"), args.collection_prefix

        health = collect(url, prefix)
        problems = health.problems(args.min_coverage)
        warnings = health.warnings()

        if args.json:
            print(json.dumps(
                {**health.as_summary(), "problems": problems, "warnings": warnings},
                ensure_ascii=False, indent=2,
            ))
        else:
            print(f"prefix: {prefix}")
            print(f"  триплетов           {health.triplets} "
                  f"(initial: {health.initial_triplets})")
            print(f"  сущностей           {health.distinct_entities}")
            print(f"  с алиасом           {health.entity_alias_labels} "
                  f"({health.entity_coverage:.1%})")
            print(f"  отношений           {health.distinct_relations}")
            print(f"  с алиасом           {health.property_alias_labels} "
                  f"({health.property_coverage:.1%})")
            print(f"  filtered_triplets   {health.filtered_triplets}")
            print(f"  из них с ошибкой    {health.swallowed_exceptions}"
                  + (f"  (в т.ч. 'larger than allowed': "
                     f"{health.wiped_collection_evidence})"
                     if health.wiped_collection_evidence else ""))

        for warning in warnings:
            print(f"\nВНИМАНИЕ: {warning}.")

        if problems:
            print("\nИНДЕКС НЕПРИГОДЕН:")
            for problem in problems:
                print(f"  - {problem}")
            print("\nСправочник сущностей чинится локально: "
                  "runs_local/backfill_entity_aliases.py --bundle <...>")
            return 1

        print("\nИндекс пригоден.")
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
