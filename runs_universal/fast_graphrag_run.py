from pathlib import Path
import os
import sys
import numpy as np
import aiohttp

import instructor
from fast_graphrag import GraphRAG
from fast_graphrag._llm import OpenAILLMService

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.fast_graphrag_pipelines import FastGraphRAGPipeline

# Читаем настройки из переменных окружения
RAG_ENGINE = os.environ.get('RAG_ENGINE', 'fast_graphrag')
DATASET_NAME = os.environ.get('DATASET_NAME', 'chegeka')
INDEX_DIR = Path(os.environ.get('INDEX_DIR', f'generated/{RAG_ENGINE}_{DATASET_NAME}/index'))
ANSWERS_DIR = Path(os.environ.get('ANSWERS_DIR', f'generated/{RAG_ENGINE}_{DATASET_NAME}/answers'))

INDEX_DIR.mkdir(parents=True, exist_ok=True)
ANSWERS_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_BASE_URL = os.environ['OPENAI_BASE_URL']
EMBED_BASE_URL = os.environ['EMBED_BASE_URL']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

LLM_MODEL = os.environ.get('LLM_MODEL', 'Qwen2.5-14B-Instruct')
EMBED_MODEL = os.environ.get('EMBED_MODEL', 'gte-multilingual-base')
EMBEDDING_DIM = int(os.environ.get('EMBEDDING_DIM', '768'))

class AiohttpEmbeddingService:
    def __init__(self, base_url: str, api_key: str, model: str, embedding_dim: int):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.embedding_dim = embedding_dim

    async def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # vLLM rejects an empty string in a batch, taking the whole request
        # with it. A space embeds to something useless, which is what an empty
        # chunk deserves.
        safe_texts = [t if t and t.strip() else " " for t in texts]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/embeddings",
                json={"input": safe_texts, "model": self.model},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Embedding API error {resp.status}: {await resp.text()}")
                data = await resp.json()

        embeddings = []
        wrong_dim = 0
        for item in data["data"]:
            emb = item.get("embedding", [])
            if len(emb) != self.embedding_dim:
                # Padding keeps the run alive, but a zero vector is not an
                # embedding: it matches everything equally and quietly drags
                # retrieval down. Count it so the damage is visible.
                wrong_dim += 1
                emb = [0.0] * self.embedding_dim
            embeddings.append(emb)
        if wrong_dim:
            print(
                f"WARNING: {wrong_dim}/{len(embeddings)} embeddings came back with the "
                f"wrong dimension and were replaced by zero vectors. Check that "
                f"EMBEDDING_DIM={self.embedding_dim} matches the model served at "
                f"{self.base_url}.",
                file=sys.stderr,
            )
        return embeddings

dataset = RAGDataset.load_auto(f'datasets/{DATASET_NAME}')

llm_service = OpenAILLMService(
    model=LLM_MODEL,
    base_url=OPENAI_BASE_URL,
    api_key=OPENAI_API_KEY,
    mode=instructor.Mode.JSON,
)

embedding_service = AiohttpEmbeddingService(
    base_url=EMBED_BASE_URL,
    api_key=OPENAI_API_KEY,
    model=EMBED_MODEL,
    embedding_dim=EMBEDDING_DIM,
)

cfg = GraphRAG.Config(
    llm_service=llm_service,
    embedding_service=embedding_service,
)

pipeline = FastGraphRAGPipeline(
    working_dir=INDEX_DIR,
    domain='General knowledge from the dataset documents.',
    example_queries=[
        'What is the main topic of the documents?',
        'What entities are mentioned in the dataset?',
    ],
    entity_types=['PERSON', 'ORGANIZATION', 'DATE', 'LOCATION', 'EVENT'],
    config=cfg,
)

pipeline.build_index(documents=list(dataset.documents.values()))

for q_idx, question in enumerate(dataset.questions):
    answer_path = ANSWERS_DIR / f'{q_idx}.txt'
    if not answer_path.exists():
        answer, _ = pipeline.generate_answer(question.text)
        answer_path.write_text(answer)

pipeline.close()