from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np

from openai import AsyncOpenAI
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.lightrag_pipelines import LightRAGPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LightRAG on a dataset.")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/multiq")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/lightrag")),
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
        "--query-mode",
        default=os.environ.get("QUERY_MODE", "naive"),
    )
    parser.add_argument(
        "--max-parallel-insert",
        type=int,
        default=int(os.environ.get("MAX_PARALLEL_INSERT", "16")),
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
        "--embed-base-url",
        default=os.environ.get("EMBED_BASE_URL"),
    )
    parser.add_argument(
        "--llm-model",
        default=os.environ.get("LLM_MODEL", "openai/gpt-4o-mini"),
    )
    parser.add_argument(
        "--embed-model",
        default=os.environ.get("EMBED_MODEL", "emb-openai/text-embedding-3-small"),
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=int(os.environ.get("EMBEDDING_DIM", "1536")),
    )
    return parser.parse_args()


async def embedding_func(texts: list[str], args: argparse.Namespace) -> np.ndarray:
    client = AsyncOpenAI(
        base_url=args.embed_base_url or args.openai_base_url,
        api_key=args.openai_api_key,
    )
    response = await client.embeddings.create(
        input=texts,
        model=args.embed_model,
    )
    return np.array([item.embedding for item in response.data])


async def llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    **kwargs,
) -> str:
    return await openai_complete_if_cache(
        args.llm_model,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        api_key=args.openai_api_key,
        base_url=args.openai_base_url,
        **kwargs,
    )


def main() -> None:
    global args
    args = parse_args()
    
    if not args.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")

    dataset = RAGDataset.load_auto(args.dataset_path)
    dataset_name = args.dataset_path.stem if args.dataset_path.is_file() else args.dataset_path.name
    
    index_dir = args.output_dir / dataset_name / "index"
    answers_dir = args.output_dir / dataset_name / "answers"
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    pipeline = LightRAGPipeline(
        working_dir=index_dir,
        llm_model_func=lambda prompt, system_prompt=None, history_messages=None, **kwargs: llm_func(
            prompt, system_prompt, history_messages, **kwargs
        ),
        embedding_func=EmbeddingFunc(
            embedding_dim=args.embedding_dim,
            max_token_size=8192,
            func=lambda texts: embedding_func(texts, args),
        ),
        query_mode=args.query_mode,
        max_parallel_insert=args.max_parallel_insert,
    )

    if args.build_index:
        pipeline.build_index(documents=list(dataset.documents.values()))

    if args.answer:
        for q_idx, question in enumerate(dataset.questions):
            answer_path = answers_dir / f'{q_idx}.txt'
            if not answer_path.exists() or args.force:
                answer, _ = pipeline.generate_answer(question.text)
                answer_path.write_text(answer)

    pipeline.close()


if __name__ == "__main__":
    main()