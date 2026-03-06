import asyncio
from dataclasses import dataclass
from pathlib import Path
import sys
import os
import shutil

from ragu.common.logger import logger as ragu_logger
from ragu import (
    SimpleChunker,
    KnowledgeGraph,
    BuilderArguments,
    Settings,
    ArtifactsExtractorLLM,
)
from ragu.models.embedder import EmbedderOpenAI
from ragu.models.llm import LLMOpenAI
from ragu.models.openai import CachedAsyncOpenAI
from ragu.search_engine.local_search import LocalSearchEngine

from natural_rag.pipelines import RAGPipeline
from natural_rag.dataset import Document



class RAGUPipeline(RAGPipeline):
    def __init__(
        self,
        language: str,
        index_dir: Path,
    ):
        ragu_logger.remove()
        ragu_logger.add(sys.stdout, level="DEBUG")

        self.language = language
        self.index_dir = index_dir
        self.client = CachedAsyncOpenAI(
            base_url=os.environ['OPENAI_BASE_URL'],
            api_key=os.environ['OPENAI_API_KEY'],
            rate_min_delay=2,
            rate_max_simultaneous=10,
            retry_times_sec=(2, 2, 2, 2, 2),
            cache='./tmp/llm_cache',
            debug_errors_storage='./tmp/llm_debug',
        )
        self.llm = LLMOpenAI(self.client, "mistralai/mistral-medium-3")
        self.embedder = EmbedderOpenAI(self.client, "emb-qwen/qwen3-embedding-8b", dim=4096)

        Settings.storage_folder = self.index_dir
        Settings.language = self.language

        self.chunker = SimpleChunker(max_chunk_size=1000)

        self.artifact_extractor = ArtifactsExtractorLLM(
            llm=self.llm,
            do_validation=False
        )

        self.builder_settings = BuilderArguments(
            use_llm_summarization=True,
            vectorize_chunks=True,
        )

        self.knowledge_graph = KnowledgeGraph(
            llm=self.llm,
            embedder=self.embedder,
            chunker=self.chunker,
            artifact_extractor=self.artifact_extractor,
            builder_settings=self.builder_settings,
        )

        self.local_search = LocalSearchEngine(
            LLMOpenAI(self.client, "mistralai/mistral-medium-3"),
            self.knowledge_graph,
            self.embedder,
            tokenizer_model="gpt-4o-mini",
        )

    def build_index(self, documents: list[Document]):
        docs = [doc.text for doc in documents if doc.text]
        shutil.rmtree(Settings.storage_folder, ignore_errors=True)
        asyncio.run(self.knowledge_graph.build_from_docs(docs))

    def answer_question(self, question: str) -> list[str]:
        return asyncio.run(self.local_search.a_query(question)).response # type: ignore