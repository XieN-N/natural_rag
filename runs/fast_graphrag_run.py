from pathlib import Path
import os

import instructor
from fast_graphrag import GraphRAG
from fast_graphrag._llm import OpenAILLMService, OpenAIEmbeddingService

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.fast_graphrag_pipelines import FastGraphRAGPipeline


dataset_name = 'bl_medium'

dataset = RAGDataset.load_from_dir(f'datasets/{dataset_name}')

index_dir = Path(f'generated/fast_graphrag_{dataset_name}/index')
answers_dir = Path(f'generated/fast_graphrag_{dataset_name}/answers')

index_dir.mkdir(parents=True, exist_ok=True)
answers_dir.mkdir(parents=True, exist_ok=True)

OPENAI_BASE_URL = os.environ['OPENAI_BASE_URL']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

LLM_MODEL = os.environ.get('LLM_MODEL', 'openai/gpt-4o-mini')
EMBED_MODEL = os.environ.get('EMBED_MODEL', 'emb-openai/text-embedding-3-small')

cfg = GraphRAG.Config(
    llm_service=OpenAILLMService(
        model=LLM_MODEL,
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
        mode=instructor.Mode.JSON,
    ),
    embedding_service=OpenAIEmbeddingService(
        model=EMBED_MODEL,
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
    ),
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

pipeline.build_index(documents=list(dataset.documents.values()))

for q_idx, question in enumerate(dataset.questions):
    answer_path = answers_dir / f'{q_idx}.txt'
    if not answer_path.exists():
        answer, _ = pipeline.generate_answer(question.text)
        answer_path.write_text(answer)

pipeline.close()