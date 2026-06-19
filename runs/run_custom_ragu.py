from __future__ import annotations

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAGU_ROOT = PROJECT_ROOT.parent / "RAGU"
for path in (PROJECT_ROOT, RAGU_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from ragu.models.embedder import EmbedderOpenAI
from ragu.models.llm import LLMOpenAI
from ragu.models.openai import CachedAsyncOpenAI

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.ragu_pipelines import RAGUPipeline


load_dotenv()


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None else int(raw)


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return default if raw is None else float(raw)


def first_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def parse_args() -> argparse.Namespace:
    output_dir = Path(os.environ.get("OUTPUT_DIR", "generated/ragu_generated"))
    limit = os.environ.get("LIMIT")

    parser = argparse.ArgumentParser(
        description="Build and evaluate RAGU answers for custom dataset.",
    )
    parser.add_argument("--dataset-path", type=Path, default=Path(os.environ.get(
        "DATASET_PATH",
        "datasets/2wikimultihopqa/2wikimultihopqa.json",
    )))
    parser.add_argument("--output-dir", type=Path, default=output_dir)
    parser.add_argument("--index-dir", type=Path, default=Path(os.environ["INDEX_DIR"]) if "INDEX_DIR" in os.environ else None)
    parser.add_argument("--answers-dir", type=Path, default=Path(os.environ["ANSWERS_DIR"]) if "ANSWERS_DIR" in os.environ else None)
    parser.add_argument("--answers-json-file", default=os.environ.get("ANSWERS_JSON_FILE", "2wikimultihopqa_answers.json"))
    parser.add_argument("--limit", type=int, default=int(limit) if limit else None)

    parser.add_argument("--build-index", action=argparse.BooleanOptionalAction, default=env_bool("BUILD_INDEX", True))
    parser.add_argument("--answer", action=argparse.BooleanOptionalAction, default=env_bool("ANSWER", True))
    parser.add_argument("--force", action=argparse.BooleanOptionalAction, default=env_bool("FORCE", False))
    parser.add_argument("--use-chunks", action=argparse.BooleanOptionalAction, default=env_bool("USE_CHUNKS", True))
    parser.add_argument("--use-summary", action=argparse.BooleanOptionalAction, default=env_bool("USE_SUMMARY", False))

    parser.add_argument("--chunker", choices=["simple", "smart"], default=os.environ.get("CHUNKER", "simple"))
    parser.add_argument("--simple-chunk-size", type=int, default=env_int("SIMPLE_CHUNK_SIZE", 2048))
    parser.add_argument("--simple-chunk-overlap", type=int, default=env_int("SIMPLE_CHUNK_OVERLAP", 0))

    parser.add_argument("--openai-base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--openai-api-key", default=first_env("OPENAI_API_KEY", "OPENAI_KEY"))
    parser.add_argument("--openai-rate-min-delay", type=float, default=env_float("OPENAI_RATE_MIN_DELAY", 1.0))
    parser.add_argument("--openai-rate-max-simultaneous", type=int, default=env_int("OPENAI_RATE_MAX_SIMULTANEOUS", 10))
    parser.add_argument("--llm-cache", default=os.environ.get("LLM_CACHE", "tmp/ragu_2wiki_llm_cache"))
    parser.add_argument("--llm-debug-cache", default=os.environ.get("LLM_DEBUG_CACHE", "tmp/ragu_2wiki_llm_debug_cache"))
    parser.add_argument("--max-completion-tokens", type=int, default=env_int("MAX_COMPLETION_TOKENS", 16384))

    parser.add_argument("--embedding-base-url", default=os.environ.get("EMBEDDING_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--embedding-api-key",default=first_env("OPENAI_API_KEY", "OPENAI_KEY"))
    parser.add_argument("--embedding-rate-min-delay", type=float, default=env_float("EMBEDDING_RATE_MIN_DELAY", 0.5))
    parser.add_argument("--embedding-rate-max-simultaneous", type=int, default=env_int("EMBEDDING_RATE_MAX_SIMULTANEOUS", 10))
    parser.add_argument("--embedding-cache", default=os.environ.get("EMBEDDING_CACHE", "tmp/ragu_2wiki_embedding_cache"))
    parser.add_argument("--embedding-debug-cache", default=os.environ.get("EMBEDDING_DEBUG_CACHE", "tmp/ragu_2wiki_embedding_debug_cache"))

    parser.add_argument("--builder-model-name", default=os.environ.get("BUILDER_MODEL_NAME", "gpt-4o-mini"))
    parser.add_argument("--assistant-model-name", default=os.environ.get("ASSISTANT_MODEL_NAME"))
    parser.add_argument("--embedding-model-name", default=os.environ.get("EMBEDDING_MODEL_NAME", "gte"))
    parser.add_argument("--embedding-dim", type=int, default=env_int("EMBEDDING_DIM", 3072))
    parser.add_argument("--retrieval-top-k", type=int, default=env_int("RETRIEVAL_TOP_K", 20))
    parser.add_argument("--qa-top-k", type=int, default=env_int("QA_TOP_K", 20))
    parser.add_argument("--tokenizer-backend", default=os.environ.get("TOKENIZER_BACKEND", "tiktoken"))
    parser.add_argument("--tokenizer-llm-name", default=os.environ.get("TOKENIZER_LLM_NAME", "gpt-4o"))
    parser.add_argument("--tokenizer-embedder-name", default=os.environ.get("TOKENIZER_EMBEDDER_NAME", "gpt-4o"))

    args = parser.parse_args()
    args.index_dir = args.index_dir or args.output_dir / "index"
    args.answers_dir = args.answers_dir or args.output_dir / "answers"
    args.assistant_model_name = args.assistant_model_name or args.builder_model_name
    return args


def build_pipeline(args: argparse.Namespace) -> RAGUPipeline:
    chat_client = CachedAsyncOpenAI(
        base_url=args.openai_base_url,
        api_key=args.openai_api_key,
        rate_min_delay=args.openai_rate_min_delay,
        rate_max_simultaneous=args.openai_rate_max_simultaneous,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache=args.llm_cache,
        debug_errors_storage=args.llm_debug_cache,
        max_completion_tokens=args.max_completion_tokens,
    )

    embedding_client = CachedAsyncOpenAI(
        base_url=args.embedding_base_url,
        api_key=args.embedding_api_key,
        rate_min_delay=args.embedding_rate_min_delay,
        rate_max_simultaneous=args.embedding_rate_max_simultaneous,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache=args.embedding_cache,
        debug_errors_storage=args.embedding_debug_cache,
        max_completion_tokens=8192,
    )

    return RAGUPipeline(
        language="english",
        index_dir=args.index_dir,
        builder_llm=LLMOpenAI(chat_client, args.builder_model_name),
        assistant_llm=LLMOpenAI(chat_client, args.assistant_model_name),
        embedder=EmbedderOpenAI(embedding_client, args.embedding_model_name, dim=args.embedding_dim),
        query_use_chunks=args.use_chunks,
        query_use_summary=args.use_summary,
        chunker_name=args.chunker,
        simple_chunk_size=args.simple_chunk_size,
        simple_chunk_overlap=args.simple_chunk_overlap,
        retrieval_top_k=args.retrieval_top_k,
        qa_top_k=args.qa_top_k,
        tokenizer_backend=args.tokenizer_backend,
        tokenizer_llm_name=args.tokenizer_llm_name,
        tokenizer_embedder_name=args.tokenizer_embedder_name,
    )


def write_answers(
    dataset: RAGDataset,
    pipeline: RAGUPipeline,
    args: argparse.Namespace,
) -> None:
    args.answers_dir.mkdir(parents=True, exist_ok=True)
    answers_json: list[dict[str, str]] = []

    for q_idx, question in enumerate(dataset.questions):
        answer_path = args.answers_dir / f"{q_idx}.txt"
        if answer_path.exists() and not args.force:
            answer = answer_path.read_text(encoding="utf-8")
        else:
            answer, _ = pipeline.generate_answer(question.text)
            answer_path.write_text(str(answer), encoding="utf-8")

        answers_json.append({
            "question": question.text,
            "rag_answer": str(answer),
        })

    json_path = args.answers_dir / args.answers_json_file
    json_path.write_text(
        json.dumps(answers_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(answers_json)} answers to {json_path}")


def main() -> None:
    args = parse_args()
    dataset = RAGDataset.load_auto(args.dataset_path)
    args.index_dir.mkdir(parents=True, exist_ok=True)
    args.answers_dir.mkdir(parents=True, exist_ok=True)

    if not args.build_index and not args.answer:
        print(f"Loaded {len(dataset.documents)} documents and {len(dataset.questions)} questions")
        return

    pipeline = build_pipeline(args)

    if args.build_index:
        pipeline.build_index(documents=list(dataset.documents.values()))
    if args.answer:
        write_answers(dataset=dataset, pipeline=pipeline, args=args)


if __name__ == "__main__":
    main()