from __future__ import annotations

import argparse
import os
from pathlib import Path

import instructor
from fast_graphrag import GraphRAG
from fast_graphrag._llm import OpenAILLMService

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.fast_graphrag_pipelines import FastGraphRAGPipeline


class AiohttpEmbeddingService:
    def __init__(self, base_url: str, api_key: str, model: str, embedding_dim: int):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.embedding_dim = embedding_dim

    async def encode(self, texts: list[str]) -> list[list[float]]:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/embeddings",
                json={"input": texts, "model": self.model},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Embedding API error {resp.status}: {await resp.text()}")
                data = await resp.json()
                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FastGraphRAG on a dataset.")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/chegeka")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/fast_graphrag")),
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
        default=os.environ.get("LLM_MODEL", "Qwen2.5-14B-Instruct"),
    )
    parser.add_argument(
        "--embed-model",
        default=os.environ.get("EMBED_MODEL", "gte-multilingual-base"),
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=int(os.environ.get("EMBEDDING_DIM", "768")),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    if not args.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")
    if not args.embed_base_url:
        args.embed_base_url = args.openai_base_url

    dataset = RAGDataset.load_auto(args.dataset_path)
    dataset_name = args.dataset_path.stem if args.dataset_path.is_file() else args.dataset_path.name
    
    index_dir = args.output_dir / dataset_name / "index"
    answers_dir = args.output_dir / dataset_name / "answers"
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    llm_service = OpenAILLMService(
        model=args.llm_model,
        base_url=args.openai_base_url,
        api_key=args.openai_api_key,
        mode=instructor.Mode.JSON,
    )

    embedding_service = AiohttpEmbeddingService(
        base_url=args.embed_base_url,
        api_key=args.openai_api_key,
        model=args.embed_model,
        embedding_dim=args.embedding_dim,
    )

    cfg = GraphRAG.Config(
        llm_service=llm_service,
        embedding_service=embedding_service,
    )

    pipeline = FastGraphRAGPipeline(
        working_dir=index_dir,
        domain='General knowledge from the dataset documents.',
        example_queries=[
            'What is the main topic of the documents?',
            'What entities are mentioned in the dataset?',
        ],
        entity_types=['PERSON', 'ORGANIZATION', 'DATE', 'LOCATION', 'EVENT'],
        config=cfg,
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