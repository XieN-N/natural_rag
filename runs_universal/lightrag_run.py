from pathlib import Path
import os
import numpy as np
import aiohttp

from openai import AsyncOpenAI
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.lightrag_pipelines import LightRAGPipeline

# Читаем настройки из переменных окружения
RAG_ENGINE = os.environ.get('RAG_ENGINE', 'lightrag')
DATASET_NAME = os.environ.get('DATASET_NAME', 'multiq')
INDEX_DIR = Path(os.environ.get('INDEX_DIR', f'generated/{RAG_ENGINE}_{DATASET_NAME}/index'))
ANSWERS_DIR = Path(os.environ.get('ANSWERS_DIR', f'generated/{RAG_ENGINE}_{DATASET_NAME}/answers'))

INDEX_DIR.mkdir(parents=True, exist_ok=True)
ANSWERS_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_BASE_URL = os.environ['OPENAI_BASE_URL']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
EMBED_BASE_URL = os.environ['EMBED_BASE_URL']

LLM_MODEL = os.environ.get('LLM_MODEL', 'openai/gpt-4o-mini')
EMBED_MODEL = os.environ.get('EMBED_MODEL', 'emb-openai/text-embedding-3-small')
EMBEDDING_DIM = int(os.environ.get('EMBEDDING_DIM', '1536'))

dataset = RAGDataset.load_auto(f'datasets/{DATASET_NAME}')

async def embedding_func(texts: list[str]):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{EMBED_BASE_URL}/embeddings",
            json={
                "input": texts,
                "model": EMBED_MODEL,
            },
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Embedding API error {resp.status}: {await resp.text()}")
            data = await resp.json()
            embeddings = [item["embedding"] for item in data["data"]]
            return np.array(embeddings)

async def llm_func(prompt, system_prompt=None, history_messages=None, **kwargs):
    return await openai_complete_if_cache(
        LLM_MODEL,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        **kwargs,
    )

pipeline = LightRAGPipeline(
    working_dir=INDEX_DIR,
    llm_model_func=llm_func,
    embedding_func=EmbeddingFunc(
        embedding_dim=EMBEDDING_DIM,
        max_token_size=8192,
        func=embedding_func,
    ),
    query_mode='naive',
)

pipeline.build_index(documents=list(dataset.documents.values()))

for q_idx, question in enumerate(dataset.questions):
    answer_path = ANSWERS_DIR / f'{q_idx}.txt'
    if not answer_path.exists():
        answer, _ = pipeline.generate_answer(question.text)
        answer_path.write_text(answer)

pipeline.close()