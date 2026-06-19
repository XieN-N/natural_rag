from __future__ import annotations

import argparse
import asyncio
import pickle
import os
from pathlib import Path

from diskcache import Index
from ragu.models.llm import LLMOpenAI
from ragu.models.openai import CachedAsyncOpenAI

from natural_rag.baseline.tree import TreeKnowledgeBase
from natural_rag.baseline.build import build_base_from_docs
from natural_rag.dataset import RAGDataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run baseline on a dataset.")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/bl_medium")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/baseline")),
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
        "--openai-base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--openai-api-key",
        default=os.environ.get("OPENAI_API_KEY"),
    )
    parser.add_argument(
        "--openai-rate-min-delay",
        type=float,
        default=float(os.environ.get("OPENAI_RATE_MIN_DELAY", "2")),
    )
    parser.add_argument(
        "--openai-rate-max-simultaneous",
        type=int,
        default=int(os.environ.get("OPENAI_RATE_MAX_SIMULTANEOUS", "10")),
    )
    parser.add_argument(
        "--llm-cache",
        default=os.environ.get("LLM_CACHE", "tmp/llm_cache"),
    )
    parser.add_argument(
        "--llm-debug-cache",
        default=os.environ.get("LLM_DEBUG_CACHE", "tmp/llm_debug_cache"),
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=int(os.environ.get("MAX_COMPLETION_TOKENS", "100000")),
    )
    parser.add_argument(
        "--llm-model",
        default=os.environ.get("LLM_MODEL", "mistralai/mistral-medium-3"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    if not args.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")

    dataset = RAGDataset.load_auto(args.dataset_path)
    dataset_name = args.dataset_path.stem if args.dataset_path.is_file() else args.dataset_path.name
    
    index_dir = args.output_dir / dataset_name / "index"
    answers_dir = args.output_dir / dataset_name / "answers"
    dump_stages_dir = args.output_dir / dataset_name / "answers"
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    client = CachedAsyncOpenAI(
        base_url=args.openai_base_url,
        api_key=args.openai_api_key,
        rate_min_delay=args.openai_rate_min_delay,
        rate_max_simultaneous=args.openai_rate_max_simultaneous,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache=args.llm_cache,
        debug_errors_storage=args.llm_debug_cache,
        max_completion_tokens=args.max_completion_tokens,
    )

    base = TreeKnowledgeBase()
    llm = LLMOpenAI(client=client, model_name=args.llm_model)

    if args.build_index:
        asyncio.run(build_base_from_docs(
            llm, base, list(dataset.documents.values()), dump_stages_dir=dump_stages_dir,
        ))
        (index_dir / 'entries.pkl').write_bytes(pickle.dumps(base._entries))


if __name__ == "__main__":
    main()