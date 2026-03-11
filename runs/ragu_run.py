from pathlib import Path
import os

from ragu.models.llm import CachedAsyncOpenAI, LLMOpenAI
from ragu.models.embedder import EmbedderOpenAI

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.ragu_pipelines import RAGUPipeline


dataset = RAGDataset.load_from_dir('datasets/bl_small')

index_dir = Path('generated/ragu/index')
answers_dir = Path('generated/ragu/answers')

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
)

pipeline = RAGUPipeline(
    language='english',
    index_dir=index_dir,
    builder_llm=LLMOpenAI(client, 'mistralai/mistral-medium-3'),
    assistant_llm=LLMOpenAI(client, 'mistralai/mistral-medium-3'),
    embedder=EmbedderOpenAI(client, 'emb-qwen/qwen3-embedding-8b', dim=4096),
)
pipeline.build_index(documents=list(dataset.documents.values()))

for q_idx, question in enumerate(dataset.questions):
    answer_path = answers_dir / f'{q_idx}.txt'
    if not answer_path.exists():
        answer = pipeline.generate_answer(question.text)
        answer_path.write_text(answer)