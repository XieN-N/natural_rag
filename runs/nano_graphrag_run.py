from pathlib import Path
import os
import numpy as np

from openai import AsyncOpenAI

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.nano_graphrag_pipelines import NanoGraphRAGPipeline


dataset_name = 'bl_medium'

dataset = RAGDataset.load_from_dir(f'datasets/{dataset_name}')

index_dir = Path(f'generated/nano_graphrag_{dataset_name}/index')
answers_dir = Path(f'generated/nano_graphrag_{dataset_name}/answers')

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


async def llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    **kwargs,
) -> str:
    client = AsyncOpenAI(
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content or ""


pipeline = NanoGraphRAGPipeline(
    working_dir=index_dir,
    best_model_func=llm_func,
    cheap_model_func=llm_func,
    embedding_func=embedding_func,
    embedding_dim=EMBEDDING_DIM,
    query_mode='naive',
)

pipeline.build_index(documents=list(dataset.documents.values()))

for q_idx, question in enumerate(dataset.questions):
    answer_path = answers_dir / f'{q_idx}.txt'
    if not answer_path.exists():
        answer, _ = pipeline.generate_answer(question.text)
        answer_path.write_text(answer)