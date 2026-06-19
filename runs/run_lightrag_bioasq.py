from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from openai import AsyncOpenAI

from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.lightrag_pipelines import LightRAGPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Smoke-test LightRAG indexing on BioASQ.'
    )
    parser.add_argument(
        '--n-docs',
        type=int,
        default=100,
        help='Number of documents to index. Use 0 to index the full corpus.',
    )
    parser.add_argument(
        '--dataset-dir',
        default='datasets/bioasq',
        help='Path to the BioASQ dataset directory.',
    )
    parser.add_argument(
        '--index-dir',
        default=None,
        help='Index output dir. Defaults to generated/lightrag_bioasq_smoke_<n>/index.',
    )
    parser.add_argument(
        '--query-mode',
        default='hybrid',
        help='LightRAG query mode to configure on the pipeline.',
    )
    parser.add_argument(
        '--max-parallel-insert',
        type=int,
        default=16,
        help='Number of documents LightRAG may index concurrently if supported.',
    )
    parser.add_argument(
        '--openai-base-url',
        default='http://localhost:8000/v1',
        help='OpenAI-compatible base URL for vLLM.',
    )
    parser.add_argument(
        '--embed-base-url',
        default='http://localhost:8000/v1',
        help='OpenAI-compatible base URL for vLLM.',
    )
    parser.add_argument(
        '--openai-api-key',
        default='token-abc123',
        help='API key passed to the OpenAI-compatible server.',
    )
    parser.add_argument(
        '--llm-model',
        required=True,
        help='LLM model name exposed by vLLM.',
    )
    parser.add_argument(
        '--embed-model',
        required=True,
        help='Embedding model name exposed by vLLM.',
    )
    parser.add_argument(
        '--embedding-dim',
        type=int,
        required=True,
        help='Embedding vector dimension.',
    )
    return parser.parse_args()


def resolve_entity_types_guidance(args: argparse.Namespace) -> str | None:
    if args.entity_types_guidance_file:
        return Path(args.entity_types_guidance_file).read_text(encoding='utf-8').strip()
    if args.entity_types_guidance:
        return args.entity_types_guidance.strip()
    if args.use_bioasq_entity_types:
        return BIOASQ_ENTITY_TYPES_GUIDANCE
    return None


def main() -> None:
    args = parse_args()

    dataset = RAGDataset.load_auto(args.dataset_dir)
    documents = list(dataset.documents.values())

    index_dir = Path(
        args.index_dir
        or f'generated/lightrag_bioasq_{len(documents)}/index'
    )
    index_dir.mkdir(parents=True, exist_ok=True)

    async def embedding_func(texts: list[str]):
        client = AsyncOpenAI(
            base_url=args.embed_base_url,
            api_key=args.openai_api_key,
        )
        response = await client.embeddings.create(
            input=texts,
            model=args.embed_model,
        )
        return np.array([item.embedding for item in response.data])

    async def llm_func(
        prompt,
        system_prompt=None,
        history_messages=None,
        **kwargs,
    ):
        return await openai_complete_if_cache(
            args.llm_model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=args.openai_api_key,
            base_url=args.openai_base_url,
            **kwargs,
        )

    pipeline = LightRAGPipeline(
        working_dir=index_dir,
        llm_model_func=llm_func,
        embedding_func=EmbeddingFunc(
            embedding_dim=args.embedding_dim,
            max_token_size=8192,
            func=embedding_func,
        ),
        query_mode=args.query_mode,
        max_parallel_insert=args.max_parallel_insert,
    )

    try:
        print(f'Indexing {len(documents)} docs from {args.dataset_dir}')
        print(f'Index dir: {index_dir}')
        pipeline.build_index(documents=documents)
    finally:
        pipeline.close()

    print('Done')


if __name__ == '__main__':
    main()
