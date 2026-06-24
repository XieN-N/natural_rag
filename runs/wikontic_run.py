from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.wikontic_pipeline import WikonticPipeline


def parse_args() -> argparse.Namespace:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run Wikontic on a dataset.")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/bl_tiny")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/wikontic")),
        help="Output directory for index and answers.",
    )
    parser.add_argument(
        "--build-index",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--answer",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--mode",
        choices=["dynamic", "structured"],
        default=os.environ.get("WIKONTIC_MODE", "dynamic"),
        help="Pipeline mode: dynamic (no ontology) or structured (Wikidata).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("WIKONTIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("KEY")
        or os.environ.get("OPENROUTER_KEY"),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("WIKONTIC_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("WIKONTIC_MODEL")
        or os.environ.get("LLM_MODEL", "gpt-4o"),
    )
    parser.add_argument(
        "--language",
        default=os.environ.get("WIKONTIC_LANGUAGE", "en"),
    )
    parser.add_argument(
        "--backend-type",
        choices=["qdrant", "mongo"],
        default=os.environ.get("WIKONTIC_STORAGE_BACKEND", "qdrant"),
    )
    parser.add_argument(
        "--qdrant-url",
        default=os.environ.get("WIKONTIC_QDRANT_URL", ":memory:"),
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.environ.get("WIKONTIC_MONGO_URI"),
    )
    parser.add_argument(
        "--hop-depth",
        type=int,
        default=int(os.environ.get("WIKONTIC_HOP_DEPTH", "5")),
    )
    parser.add_argument(
        "--use-qualifiers",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--use-filtered-triplets",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.api_key:
        raise ValueError(
            "API key is required. Set WIKONTIC_API_KEY / OPENAI_API_KEY / "
            "KEY / OPENROUTER_KEY or pass --api-key."
        )

    dataset = RAGDataset.load_auto(args.dataset_path)
    dataset_name = (
        args.dataset_path.stem
        if args.dataset_path.is_file()
        else args.dataset_path.name
    )

    index_dir = args.output_dir / dataset_name / "index"
    answers_dir = args.output_dir / dataset_name / "answers"
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    pipeline = WikonticPipeline(
        language=args.language,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        mode=args.mode,
        backend_type=args.backend_type,
        qdrant_url=args.qdrant_url,
        mongo_uri=args.mongo_uri,
        hop_depth=args.hop_depth,
        use_qualifiers=args.use_qualifiers,
        use_filtered_triplets=args.use_filtered_triplets,
    )

    if args.build_index:
        pipeline.build_index(documents=list(dataset.documents.values()))

    if args.answer:
        for q_idx, question in enumerate(dataset.questions):
            answer_path = answers_dir / f"{q_idx}.txt"
            if not answer_path.exists() or args.force:
                answer, _ = pipeline.generate_answer(question.text)
                answer_path.write_text(answer)


if __name__ == "__main__":
    main()
