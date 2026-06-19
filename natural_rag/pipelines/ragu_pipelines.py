import asyncio
import sys
from pathlib import Path
from typing import Any

from natural_rag.dataset import Document
from natural_rag.pipelines import RAGPipeline

from ragu import (
    SimpleChunker,
    SmartSemanticChunker,
    KnowledgeGraph,
    BuilderArguments,
    Settings,
    QueryPlanEngine,
    TwoStageArtifactsExtractorLLM,
)
from ragu.common.logger import logger as ragu_logger
from ragu.models.embedder import Embedder
from ragu.models.llm import LLM
from ragu.search_engine.local_search import LocalSearchEngine


class RAGUPipeline(RAGPipeline):
    def __init__(
        self,
        language: str,
        index_dir: str | Path,
        builder_llm: LLM,
        assistant_llm: LLM,
        embedder: Embedder,
        use_llm_summarization: bool = True,
        vectorize_chunks: bool = True,
        query_use_summary: bool = False,
        query_use_chunks: bool = False,
        chunker_name: str = "smart",
        simple_chunk_size: int = 2048,
        simple_chunk_overlap: int = 0,
        retrieval_top_k: int = 20,
        qa_top_k: int = 20,
        tokenizer_backend: str = "tiktoken",
        tokenizer_llm_name: str = "gpt-4o",
        tokenizer_embedder_name: str = "gpt-4o",
        query_engine: str = "local",
    ):
        ragu_logger.remove()
        ragu_logger.add(sys.stdout, level="DEBUG")

        self.language = language
        self.index_dir = index_dir
        self.builder_llm = builder_llm
        self.assistant_llm = assistant_llm
        self.embedder = embedder
        self.query_use_summary = query_use_summary
        self.query_use_chunks = query_use_chunks
        self.retrieval_top_k = retrieval_top_k
        self.qa_top_k = qa_top_k

        Settings.storage_folder = self.index_dir
        Settings.language = self.language

        if chunker_name == "simple":
            self.chunker = SimpleChunker(
                max_chunk_size=simple_chunk_size,
                overlap=simple_chunk_overlap,
            )
        elif chunker_name == "smart":
            self.chunker = SmartSemanticChunker()
        else:
            raise ValueError(f"Unsupported RAGU chunker: {chunker_name}")

        BIOASQ_ENTITY_TYPES = [
            "DiseaseOrDisorder",
            "SymptomOrFinding",
            "DrugOrChemical",
            "GeneOrProtein",
            "BiologicalProcess",
            "Anatomy",
            "CellOrOrganism",
            "MedicalProcedureOrTest",
            "TherapeuticIntervention",
            "MeasurementOrOutcome",
            "StudyOrEvidence",
            "Other",
        ]

        BIOASQ_RELATION_TYPES = [
            "treats",
            "prevents",
            "causes",
            "associated_with",
            "risk_factor_for",
            "symptom_of",
            "adverse_effect_of",
            "inhibits",
            "activates",
            "regulates",
            "expressed_in",
            "located_in",
            "part_of",
            "interacts_with",
            "biomarker_for",
            "diagnoses",
            "measures",
            "administered_by",
            "has_dose_or_route",
            "studied_in",
            "improves_outcome",
            "worsens_outcome",
            "compared_with",
            "other",
        ]

        self.artifact_extractor = TwoStageArtifactsExtractorLLM(
            llm=self.builder_llm,
            do_entity_validation=False,
            do_relation_validation=False,
            # entity_types=BIOASQ_ENTITY_TYPES,
            # relation_types=BIOASQ_RELATION_TYPES
        )

        self.builder_settings = BuilderArguments(
            use_llm_summarization=use_llm_summarization,
            vectorize_chunks=vectorize_chunks,
            make_community_summary=False,
        )

        self.knowledge_graph = KnowledgeGraph(
            llm=self.builder_llm,
            embedder=self.embedder,
            chunker=self.chunker,
            artifact_extractor=self.artifact_extractor,
            builder_settings=self.builder_settings,
            embedder_token_limit=8000,
            tokenizer_backend=tokenizer_backend,
            tokenizer_llm_name=tokenizer_llm_name,
            tokenizer_embedder_name=tokenizer_embedder_name,
        )

        local_search = LocalSearchEngine(
            self.assistant_llm,
            self.knowledge_graph,
            self.embedder,
            tokenizer_model="gpt-4o-mini",
            language=self.language,
        )
        self.search_engine = QueryPlanEngine(local_search) if query_engine == "query_plan" else local_search

    def build_index(self, documents: list[Document]):
        docs = [doc.text for doc in documents if doc.text]
        asyncio.run(self.knowledge_graph.build_from_docs(docs))

    async def _answer(self, question: str, max_retries: int = 3) -> tuple[str, Any]:
        for attempt in range(max_retries):
            context = await self.search_engine.a_search(question, top_k=self.retrieval_top_k)
            response = await self.search_engine.a_query(question, top_k=self.qa_top_k, use_chunks=True)
            if response.response and response.response.strip():
                return response.response, context
            ragu_logger.warning(f"Empty answer on attempt {attempt+1}/{max_retries}, retrying...")
        return "NO ANSWER OBTAINED", context

    def generate_answer(self, question: str) -> tuple[str, Any]:
        return asyncio.run(self._answer(question))