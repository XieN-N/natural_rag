from __future__ import annotations

import argparse
import os
from pathlib import Path

from ragu import QueryPlanEngine
from ragu.models.llm import CachedAsyncOpenAI, LLMOpenAI
from ragu.models.embedder import EmbedderOpenAI

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.ragu_pipelines import RAGUPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGU on a dataset.")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/bioasq")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/ragu")),
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
        "--chunker",
        choices=["simple", "smart"],
        default=os.environ.get("CHUNKER", "simple"),
    )
    parser.add_argument(
        "--use-chunks",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--use-summary",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--simple-chunk-size",
        type=int,
        default=int(os.environ.get("SIMPLE_CHUNK_SIZE", "2048")),
    )
    parser.add_argument(
        "--simple-chunk-overlap",
        type=int,
        default=int(os.environ.get("SIMPLE_CHUNK_OVERLAP", "0")),
    )
    parser.add_argument(
        "--openai-base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--embed-base-url",
        default=os.environ.get("EMBED_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")),
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
        "--builder-model-name",
        default=os.environ.get("BUILDER_MODEL_NAME") or os.environ.get("LLM_MODEL") or "mistralai/mistral-medium-3",
    )
    parser.add_argument(
        "--assistant-model-name",
        default=os.environ.get("ASSISTANT_MODEL_NAME") or os.environ.get("LLM_MODEL"),
    )
    parser.add_argument(
        "--embedding-model-name",
        default=os.environ.get("EMBEDDING_MODEL_NAME") or os.environ.get("EMBED_MODEL") or "emb-qwen/qwen3-embedding-8b",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=int(os.environ.get("EMBEDDING_DIM", "4096")),
    )
    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=int(os.environ.get("EMBED_BATCH_SIZE", "32")),
        help="Maximum texts per single embedding API call.",
    )
    parser.add_argument(
        "--retrieval-top-k",
        type=int,
        default=int(os.environ.get("RETRIEVAL_TOP_K", "20")),
    )
    parser.add_argument(
        "--qa-top-k",
        type=int,
        default=int(os.environ.get("QA_TOP_K", "20")),
    )
    parser.add_argument(
        "--query-engine",
        choices=["local", "query_plan"],
        default=os.environ.get("QUERY_ENGINE", "local"),
        help="Search engine for answering: local (default) or query_plan (decomposes complex queries).",
    )
    parser.add_argument(
        "--tokenizer-backend",
        default=os.environ.get("TOKENIZER_BACKEND", "tiktoken"),
    )
    parser.add_argument(
        "--tokenizer-llm-name",
        default=os.environ.get("TOKENIZER_LLM_NAME", "gpt-4o"),
    )
    parser.add_argument(
        "--tokenizer-embedder-name",
        default=os.environ.get("TOKENIZER_EMBEDDER_NAME", "gpt-4o"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    if not args.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")
    if not args.assistant_model_name:
        args.assistant_model_name = args.builder_model_name

    dataset = RAGDataset.load_auto(args.dataset_path)
    dataset_name = args.dataset_path.stem if args.dataset_path.is_file() else args.dataset_path.name
    
    index_dir = args.output_dir / dataset_name / "index"
    answers_dir = args.output_dir / dataset_name / "answers"
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    llm_client = CachedAsyncOpenAI(
        base_url=args.openai_base_url,
        api_key=args.openai_api_key,
        rate_min_delay=args.openai_rate_min_delay,
        rate_max_simultaneous=args.openai_rate_max_simultaneous,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache=args.llm_cache,
        debug_errors_storage=args.llm_debug_cache,
        max_completion_tokens=args.max_completion_tokens,
    )

    embed_client = CachedAsyncOpenAI(
        base_url=args.embed_base_url,
        api_key=args.openai_api_key,
        rate_min_delay=args.openai_rate_min_delay,
        rate_max_simultaneous=args.openai_rate_max_simultaneous,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache=args.llm_cache,
        debug_errors_storage=args.llm_debug_cache,
        max_completion_tokens=args.max_completion_tokens,
    )

    pipeline = RAGUPipeline(
        language='english',
        index_dir=index_dir,
        builder_llm=LLMOpenAI(llm_client, args.builder_model_name),
        assistant_llm=LLMOpenAI(llm_client, args.assistant_model_name),
        embedder=EmbedderOpenAI(embed_client, args.embedding_model_name, dim=args.embedding_dim, batch_size=args.embed_batch_size),
        chunker_name=args.chunker,
        query_use_chunks=args.use_chunks,
        query_use_summary=args.use_summary,
        simple_chunk_size=args.simple_chunk_size,
        simple_chunk_overlap=args.simple_chunk_overlap,
        retrieval_top_k=args.retrieval_top_k,
        qa_top_k=args.qa_top_k,
        tokenizer_backend=args.tokenizer_backend,
        tokenizer_llm_name=args.tokenizer_llm_name,
        tokenizer_embedder_name=args.tokenizer_embedder_name,
        query_engine=args.query_engine,
    )

    if args.build_index:
        pipeline.build_index(documents=list(dataset.documents.values()))

    if args.answer:
        for q_idx, question in enumerate(dataset.questions):
            answer_path = answers_dir / f'{q_idx}.txt'
            if not answer_path.exists() or args.force:
                answer, _ = pipeline.generate_answer(question.text)
                answer_path.write_text(answer)


if __name__ == "__main__":
    main()