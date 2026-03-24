from pathlib import Path
import os
import numpy as np

from openai import AsyncOpenAI
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.lightrag_pipelines import LightRAGPipeline


dataset_name = 'bl_medium'

dataset = RAGDataset.load_from_dir(f'datasets/{dataset_name}')

index_dir = Path(f'generated/lightrag_{dataset_name}/index')
answers_dir = Path(f'generated/lightrag_{dataset_name}/answers')

index_dir.mkdir(parents=True, exist_ok=True)
answers_dir.mkdir(parents=True, exist_ok=True)

OPENAI_BASE_URL = os.environ['OPENAI_BASE_URL']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

LLM_MODEL = os.environ.get('LLM_MODEL', 'openai/gpt-4o-mini')
EMBED_MODEL = os.environ.get('EMBED_MODEL', 'emb-openai/text-embedding-3-small')
EMBEDDING_DIM = int(os.environ.get('EMBEDDING_DIM', '1536'))


async def embedding_func(texts: list[str]):
    client = AsyncOpenAI(
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
    )
    response = await client.embeddings.create(
        input=texts,
        model=EMBED_MODEL,
    )
    return np.array([item.embedding for item in response.data])


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
    working_dir=index_dir,
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
    answer_path = answers_dir / f'{q_idx}.txt'
    if not answer_path.exists():
        answer, _ = pipeline.generate_answer(question.text)
        answer_path.write_text(answer)

pipeline.close()