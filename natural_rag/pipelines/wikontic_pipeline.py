"""
WikonticPipeline — a standalone RAG pipeline based on Wikontic.

Uses Wikidata ontology to build knowledge graphs from text
and then answers questions based on extracted triplets.

Modes:
  - "dynamic": without ontology (embedding-only alignment)
  - "structured": with Wikidata ontology (entity types, properties, backbone validation)

Requires: pip install natural_rag[wikontic]
"""

import logging
import os
from typing import Any, Literal

from natural_rag.data import Document
from natural_rag.pipelines import RAGPipeline

logger = logging.getLogger(__name__)

try:
    import torch
    from wikontic import (
        create_triplets_database,
        create_ontological_triplets_database,
    )
    from wikontic.db.factory import create_backend
    from wikontic.utils.openai_utils import LLMTripletExtractor
    from wikontic.utils.inference_with_db import InferenceWithDB
    from wikontic.utils.structured_inference_with_db import StructuredInferenceWithDB
    from wikontic.utils.dynamic_aligner import Aligner as DynamicAligner
    from wikontic.utils.structured_aligner import Aligner as StructuredAligner

    _WIKONTIC_AVAILABLE = True
except ImportError:
    _WIKONTIC_AVAILABLE = False


class WikonticPipeline(RAGPipeline):
    """RAG pipeline based on Wikontic.

    Builds a knowledge graph from texts via LLM and Wikidata ontology,
    then answers questions with multi-hop graph traversal.
    """

    def __init__(
        self,
        language: str = "en",
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o",
        mode: Literal["dynamic", "structured"] = "structured",
        backend_type: Literal["qdrant", "mongo"] = "qdrant",
        qdrant_url: str = ":memory:",
        qdrant_api_key: str | None = None,
        mongo_uri: str | None = None,
        ontology_db_name: str = "wikidata_ontology",
        triplets_db_name: str = "triplets_db",
        device: str | None = None,
        proxy: str | None = None,
        hop_depth: int = 5,
        use_qualifiers: bool = False,
        use_filtered_triplets: bool = False,
        use_unidecode: bool | None = None,
    ):
        if not _WIKONTIC_AVAILABLE:
            raise ImportError(
                "Wikontic package is not installed. "
                "Install it with: pip install natural_rag[wikontic]"
            )

        self.language = language
        self.mode = mode
        self.hop_depth = hop_depth
        self.use_qualifiers = use_qualifiers
        self.use_filtered_triplets = use_filtered_triplets
        self.use_unidecode = use_unidecode if use_unidecode is not None else (language == "en")

        # Device (GPU by default if available)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("WikonticPipeline using device: %s", self.device)

        # ── Resolve API config ─────────────────────────────────────
        resolved_api_key = (
            api_key
            or os.getenv("WIKONTIC_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("KEY")
            or os.getenv("OPENROUTER_KEY")
        )
        if not resolved_api_key:
            raise ValueError(
                "API key is required. Pass api_key parameter or set "
                "WIKONTIC_API_KEY / OPENAI_API_KEY / KEY / OPENROUTER_KEY."
            )
        resolved_base_url = (
            base_url
            or os.getenv("WIKONTIC_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL", "https://api.openai.com/v1")
        )
        self.model = model or os.getenv("WIKONTIC_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o"
        resolved_proxy = proxy or os.getenv("WIKONTIC_PROXY_URL") or os.getenv("PROXY_URL")

        # ── Storage backends ───────────────────────────────────────
        logger.info("Creating storage backend: %s", backend_type)
        resolved_qdrant_url = qdrant_url or os.getenv("WIKONTIC_QDRANT_URL", ":memory:")
        resolved_qdrant_api_key = qdrant_api_key or os.getenv("WIKONTIC_QDRANT_API_KEY")
        resolved_triplets_db_name = triplets_db_name or os.getenv("WIKONTIC_TRIPLETS_DB_NAME", "triplets_db")
        resolved_ontology_db_name = ontology_db_name or os.getenv("WIKONTIC_ONTOLOGY_DB_NAME", "wikidata_ontology")

        # Create triplets storage backend
        if backend_type == "qdrant":
            self.triplets_db = create_backend(
                "qdrant",
                qdrant_url=resolved_qdrant_url,
                qdrant_api_key=resolved_qdrant_api_key,
            )
            if mode == "structured":
                self.ontology_db = create_backend(
                    "qdrant",
                    qdrant_url=resolved_qdrant_url,
                    qdrant_api_key=resolved_qdrant_api_key,
                )
        else:
            import pymongo
            resolved_mongo_uri = mongo_uri or os.getenv("WIKONTIC_MONGO_URI", "mongodb://localhost:27018/")
            mongo_client = pymongo.MongoClient(resolved_mongo_uri)
            self.triplets_db = create_backend(
                "mongodb", mongo_db=mongo_client[resolved_triplets_db_name]
            )
            if mode == "structured":
                self.ontology_db = create_backend(
                    "mongodb", mongo_db=mongo_client[resolved_ontology_db_name]
                )

        # Ensure triplets collections exist (pass pre-created backend via storage_backend=)
        logger.info("Ensuring triplets collections exist")
        if mode == "structured":
            create_ontological_triplets_database(
                storage_backend=self.triplets_db,
            )
        else:
            create_triplets_database(
                storage_backend=self.triplets_db,
            )

        # ── LLM Extractor ──────────────────────────────────────────
        logger.info("Initializing LLMTripletExtractor (model=%s)", self.model)
        self.extractor = LLMTripletExtractor(
            api_key=resolved_api_key,
            model=self.model,
            proxy=resolved_proxy,
            base_url=resolved_base_url,
        )

        # ── Aligner & Inference ────────────────────────────────────
        if mode == "structured":
            if not hasattr(self, "ontology_db") or self.ontology_db is None:
                raise ValueError(
                    "Structured mode requires a pre-built ontology database. "
                    "Run: python -m scripts.setup_wikontic_ontology"
                )
            logger.info("Initializing structured aligner")
            self.aligner = StructuredAligner(
                ontology_db=self.ontology_db,
                triplets_db=self.triplets_db,
                device=self.device,
            )
            self.inference = StructuredInferenceWithDB(
                extractor=self.extractor,
                aligner=self.aligner,
                triplets_db=self.triplets_db,
                language=language,
            )
        else:
            logger.info("Initializing dynamic aligner")
            self.aligner = DynamicAligner(
                triplets_db=self.triplets_db,
                device=self.device,
            )
            self.inference = InferenceWithDB(
                extractor=self.extractor,
                aligner=self.aligner,
                triplets_db=self.triplets_db,
                language=language,
            )

    # ── RAGPipeline interface ──────────────────────────────────────

    def build_index(self, documents: list[Document]):
        """Extracts triplets from documents and saves them to the KG."""
        total = len(documents)
        for i, doc in enumerate(documents):
            if not doc.text:
                logger.warning("Skipping empty document: %s", doc.id)
                continue
            logger.info("[%d/%d] Processing document: %s (len=%d)", i + 1, total, doc.id, len(doc.text))
            try:
                if self.mode == "structured":
                    self.inference.extract_triplets_with_ontology_filtering_and_add_to_db(
                        text=doc.text,
                        sample_id=doc.id,
                        source_text_id="full_text",
                        use_unidecode=self.use_unidecode,
                    )
                else:
                    self.inference.extract_triplets_and_add_to_db(
                        text=doc.text,
                        source_text_id="full_text",
                        sample_id=doc.id,
                    )
                logger.info("  \u2713 Done: %s", doc.id)
            except Exception as e:
                logger.error("  \u2717 Failed: %s \u2014 %s", doc.id, e)

    def generate_answer(self, question: str) -> tuple[str, Any]:
        """Answers a question using the built KG."""
        logger.info("Answering question: %s", question)
        try:
            linked = self.inference.identify_relevant_entities_from_question_with_llm(
                question=question, sample_id=None
            )
            result = self.inference.answer_question_with_llm(
                question=question,
                linked_entities=linked or [],
                sample_id=None,
                hop_depth=self.hop_depth,
                use_filtered_triplets=self.use_filtered_triplets,
                use_qualifiers=self.use_qualifiers,
            )
            if isinstance(result, tuple):
                _, answer_text = result
            else:
                answer_text = result
            logger.info("Answer: %s", str(answer_text)[:200] if answer_text else "None")
            return answer_text, None
        except Exception as e:
            logger.error("Failed to answer: %s", e)
            return "NO ANSWER OBTAINED", None

    def answer_with_collapsing(self, question: str, max_attempts: int = 5) -> tuple[str, Any]:
        """Answers with decomposition of complex questions (QA collapsing)."""
        logger.info("Answering (collapsing mode): %s", question)
        try:
            answer = self.inference.answer_with_qa_collapsing(
                question=question,
                sample_id=None,
                max_attempts=max_attempts,
                use_qualifiers=self.use_qualifiers,
                use_filtered_triplets=self.use_filtered_triplets,
            )
            return answer, None
        except Exception as e:
            logger.error("Failed to answer (collapsing): %s", e)
            return "NO ANSWER OBTAINED", None
