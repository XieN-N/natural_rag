from __future__ import annotations
import asyncio
from pathlib import Path
import pickle
import sys
import os

from diskcache import Index # pyright: ignore[reportMissingTypeStubs]
from ragu.models.llm import LLMOpenAI
from ragu.models.openai import CachedAsyncOpenAI

from natural_rag.baseline.tree import TreeKnowledgeBase
from natural_rag.baseline.build import build_base_from_docs
from natural_rag.dataset import RAGDataset

dataset_name = 'bl_medium'

dataset = RAGDataset.load_from_dir(f'datasets/{dataset_name}')

index_dir = Path(f'generated/baseline_{dataset_name}/index')
answers_dir = Path(f'generated/baseline_{dataset_name}/answers')
dump_stages_dir = Path(f'generated/baseline_{dataset_name}/answers')

index_dir.mkdir(parents=True, exist_ok=True)
answers_dir.mkdir(parents=True, exist_ok=True)

client = CachedAsyncOpenAI(
    base_url=os.environ['OPENAI_BASE_URL'],
    api_key=os.environ['OPENAI_API_KEY'],
    rate_min_delay=2,
    rate_max_simultaneous=10,
    retry_times_sec=(2, 2, 2, 2, 2),
    cache='tmp/llm_cache',
    debug_errors_storage='tmp/llm_debug_cache',
    max_completion_tokens=100_000,
)

base = TreeKnowledgeBase()
llm = LLMOpenAI(client=client, model_name='mistralai/mistral-medium-3')

asyncio.run(build_base_from_docs(
    llm, base, list(dataset.documents.values()), dump_stages_dir=dump_stages_dir,
))

(index_dir / 'entries.pkl').write_bytes(pickle.dumps(base._entries)) # pyright: ignore[reportPrivateUsage]