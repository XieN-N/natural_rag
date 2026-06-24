"""
One-time setup script for the Wikidata ontology used by Wikontic.

Usage:
    python -m scripts.setup_wikontic_ontology --backend qdrant --qdrant_url :memory:
    python -m scripts.setup_wikontic_ontology --backend mongo --mongo_uri "mongodb://localhost:27018/"

Creates:
    1. Wikidata ontology DB (entity_types, entity_type_aliases, properties, property_aliases)
    2. Triplets DB (entity_aliases, property_aliases, initial_triplets, triplets, filtered_triplets,
       ontology_filtered_triplets)

Requires: natural_rag[wikontic]
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Setup Wikontic Wikidata ontology databases")
    parser.add_argument("--backend", choices=["qdrant", "mongo"], default="qdrant",
                        help="Storage backend (default: qdrant)")
    parser.add_argument("--qdrant-url", default=":memory:",
                        help="Qdrant URL (default: :memory: )")
    parser.add_argument("--qdrant-api-key", default=None,
                        help="Qdrant API key (if using Qdrant Cloud)")
    parser.add_argument("--mongo-uri", default=None,
                        help="MongoDB URI (required if backend=mongo)")
    parser.add_argument("--ontology-db-name", default="wikidata_ontology",
                        help="Ontology database name (default: wikidata_ontology)")
    parser.add_argument("--triplets-db-name", default="triplets_db",
                        help="Triplets database name (default: triplets_db)")
    parser.add_argument("--language", choices=["en", "ru"], default="en",
                        help="Language for ontology mappings (default: en)")
    args = parser.parse_args()

    try:
        from wikontic import (
            create_wikidata_ontology_database,
            create_ontological_triplets_database,
        )
    except ImportError:
        print("Error: wikontic package is not installed.", file=sys.stderr)
        print("Install it with: pip install natural_rag[wikontic]", file=sys.stderr)
        sys.exit(1)

    if args.backend == "qdrant":
        backend_kwargs = {
            "backend": "qdrant",
            "qdrant_url": args.qdrant_url,
            "qdrant_api_key": args.qdrant_api_key,
        }
    else:
        if not args.mongo_uri:
            print("Error: --mongo-uri is required when backend=mongo", file=sys.stderr)
            sys.exit(1)
        backend_kwargs = {
            "backend": "mongodb",
            "mongo_uri": args.mongo_uri,
        }

    print(f"Creating Wikidata ontology database '{args.ontology_db_name}'...")
    create_wikidata_ontology_database(
        **backend_kwargs,
        database=args.ontology_db_name,
    )
    print("Done.")

    print(f"Creating ontological triplets database '{args.triplets_db_name}'...")
    create_ontological_triplets_database(
        **backend_kwargs,
        db_name=args.triplets_db_name,
    )
    print("Done.")

    print("\nWikontic ontology setup complete!")
    print(f"  Backend: {args.backend}")
    if args.backend == "qdrant":
        print(f"  Qdrant URL: {args.qdrant_url}")
    else:
        print(f"  MongoDB URI: {args.mongo_uri}")
    print(f"  Ontology DB: {args.ontology_db_name}")
    print(f"  Triplets DB: {args.triplets_db_name}")
    print(f"  Language: {args.language}")


if __name__ == "__main__":
    main()
