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
from ragu.models.embedder import Embedder, EmbedderOpenAI
from ragu.models.llm import LLM
from ragu.models.openai import CachedAsyncOpenAI
from ragu.search_engine.local_search import LocalSearchEngine

from natural_rag.pipelines import RAGPipeline
from natural_rag.dataset import Document



class RAGUPipeline(RAGPipeline):
    def __init__(
        self,
        language: str,
        index_dir: str | Path,
        builder_llm: LLM,  # such as ragu.models.llm.LLMOpenAI(self.client, assistant_llm_name)
        assistant_llm: LLM,  # such as ragu.models.llm.LLMOpenAI(self.client, assistant_llm_name)
        embedder: Embedder,  # such as ragu.models.embedder.EmbedderOpenAI(self.client, embedder_name, dim=4096)
        use_llm_summarization: bool = True,
        vectorize_chunks: bool = True,
    ):
        ragu_logger.remove()
        ragu_logger.add(sys.stdout, level="DEBUG")

        self.language = language
        self.index_dir = index_dir
        self.builder_llm = builder_llm
        self.assistant_llm = assistant_llm
        self.embedder = embedder

        Settings.storage_folder = self.index_dir
        Settings.language = self.language

        self.chunker = SimpleChunker(max_chunk_size=1000)

        self.artifact_extractor = ArtifactsExtractorLLM(
            llm=self.builder_llm,
            do_validation=False
        )

        self.builder_settings = BuilderArguments(
            use_llm_summarization=use_llm_summarization,
            vectorize_chunks=vectorize_chunks,
        )

        self.knowledge_graph = KnowledgeGraph(
            llm=self.builder_llm,
            embedder=self.embedder,
            chunker=self.chunker,
            artifact_extractor=self.artifact_extractor,
            builder_settings=self.builder_settings,
        )

        self.local_search = LocalSearchEngine(
            self.assistant_llm,
            self.knowledge_graph,
            self.embedder,
            tokenizer_model="gpt-4o-mini",
        )

    def build_index(self, documents: list[Document]):
        docs = [doc.text for doc in documents if doc.text]
        asyncio.run(self.knowledge_graph.build_from_docs(docs))

    def generate_answer(self, question: str) -> str:
        return asyncio.run(self.local_search.a_query(question)).response # type: ignore