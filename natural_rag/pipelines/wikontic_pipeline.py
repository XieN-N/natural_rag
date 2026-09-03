"""
WikonticPipeline — a standalone RAG pipeline based on Wikontic.

Uses Wikidata ontology to build knowledge graphs from text
and then answers questions based on extracted triplets.

Modes:
  - "dynamic": without ontology (embedding-only alignment)
  - "structured": with Wikidata ontology (entity types, properties, backbone validation)

Requires: pip install natural_rag[wikontic]
"""

import ast
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Literal

from natural_rag.data import Document
from natural_rag.pipelines import RAGPipeline
from natural_rag.timing import IndexTimer, LLMCallCounter, count_openai_calls
from natural_rag.wikontic_prefix import PrefixedBackend

logger = logging.getLogger(__name__)

#: Returned when answering raised. Callers use it to tell "the pipeline failed"
#: apart from a genuine "I don't know", and skip persisting it so a rerun retries.
FAILED_ANSWER = "NO ANSWER OBTAINED"

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


@dataclass(frozen=True)
class IndexUnit:
    """One unit of indexing work.

    Wikontic stores provenance as ``(sample_id, source_text_id)``. In corpus
    scope one document is one sample (``source_text_id="full_text"``, matching
    the previous behaviour of this pipeline). In per-sample scope — the setup
    used in Wikontic's own ``inference_and_eval/dataset_inference.py`` — one
    sample groups several paragraphs and ``source_text_id`` is the paragraph
    index within it.
    """

    sample_id: str
    source_text_id: str
    text: str
    doc_id: str


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
        qdrant_local_path: str | None = None,
        qdrant_timeout: int | None = 120,
        mongo_uri: str | None = None,
        ontology_db_name: str | None = None,
        triplets_db_name: str | None = None,
        collection_prefix: str | None = None,
        device: str | None = None,
        proxy: str | None = None,
        hop_depth: int = 5,
        use_qualifiers: bool = False,
        use_filtered_triplets: bool = False,
        use_unidecode: bool | None = None,
        hf_model_path: str | None = None,
        debug_llm: bool = False,
        normalize_llm_replies: bool = True,
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

        # Wikontic's embedder is hardcoded to facebook/contriever; the only
        # supported override is HF_MODEL_PATH, which resolve_contriever_path()
        # consults first. Must be set before the aligner is constructed.
        if hf_model_path:
            os.environ["HF_MODEL_PATH"] = str(hf_model_path)

        # Device (GPU by default if available)
        self.device = (
            device
            or os.getenv("WIKONTIC_DEVICE")
            or ("cuda" if torch.cuda.is_available() else "cpu")
        )
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
        # Defaults stay None here so the argument -> env -> literal chain works;
        # a non-empty default would shadow the environment variables.
        resolved_triplets_db_name = (
            triplets_db_name or os.getenv("WIKONTIC_TRIPLETS_DB_NAME") or "triplets_db"
        )
        resolved_ontology_db_name = (
            ontology_db_name or os.getenv("WIKONTIC_ONTOLOGY_DB_NAME") or "wikidata_ontology"
        )

        # Create triplets storage backend
        if backend_type == "qdrant":
            self.triplets_db = self._make_qdrant_backend(
                qdrant_url=resolved_qdrant_url,
                qdrant_api_key=resolved_qdrant_api_key,
                local_path=qdrant_local_path,
                timeout=qdrant_timeout,
            )
            if mode == "structured":
                self.ontology_db = self._make_qdrant_backend(
                    qdrant_url=resolved_qdrant_url,
                    qdrant_api_key=resolved_qdrant_api_key,
                    local_path=qdrant_local_path,
                    timeout=qdrant_timeout,
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

        # Namespace the triplet collections so several indexes can live in one
        # database / one Qdrant instance without cross-contamination. The
        # ontology DB is deliberately *not* prefixed: it is built once and
        # shared by every structured run.
        # Sanitized, not as given: PrefixedBackend rewrites everything outside
        # [A-Za-z0-9_-] to "_", so a model name with a dot (meno-lite-0.1,
        # Qwen2.5-7B-Instruct) makes the stored collections differ from the
        # string the caller handed us. Everything downstream — index_summary.json,
        # the export manifest, the preflight on the laptop — has to see the name
        # the collections actually carry, or a healthy index reads as missing.
        if collection_prefix:
            self.triplets_db = PrefixedBackend(self.triplets_db, collection_prefix)
            self.collection_prefix = self.triplets_db.prefix
            if self.collection_prefix != collection_prefix:
                logger.info(
                    "Collection prefix sanitized: %r -> %r",
                    collection_prefix, self.collection_prefix,
                )
            logger.info("Triplet collections namespaced under %r", self.collection_prefix)
        else:
            self.collection_prefix = collection_prefix

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

        # Every Wikontic LLM request funnels through LLMTripletExtractor.get_completion,
        # so patching this one client counts the whole pipeline.
        self.llm_counter = LLMCallCounter()
        if not count_openai_calls(self.extractor.client, self.llm_counter):
            logger.warning("Could not attach the LLM call counter to LLMTripletExtractor")

        self.entity_shape_fixes = 0
        #: Triplet-extraction replies rescued from the wrong wrapper. Counted
        #: apart from entity fixes: the two steps want opposite shapes, and the
        #: split says which one a given model actually struggles with.
        self.triplet_shape_fixes = 0
        self.empty_answers = 0
        #: Documents that finished without error but put nothing in the graph.
        self.empty_docs = 0
        if normalize_llm_replies:
            self._normalize_entity_replies()
            self._normalize_triplet_replies()
        if debug_llm:
            self._log_llm_replies()

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

    @staticmethod
    def _coerce_entity_list(value: Any) -> list[dict]:
        """Normalise an ``identify_relevant_entities`` reply to Wikontic's shape.

        ``base_inference_with_db`` does ``[e["entity"] for e in reply]``, so the
        reply must be a list of dicts carrying an ``entity`` key. Wikontic's
        prompt asks for a bare JSON array and gpt-4o-mini obliges; other models
        wrap it in an object (``{"entities": [...]}``, ``{"Entities": [...]}``,
        ``{"relevant_entities": [...]}``), which iterates as *keys* and blows up
        with ``string indices must be integers``. Observed variants also include
        a reply that failed JSON parsing (trailing junk after a valid object)
        and entries missing the ``entity`` key altogether.
        """
        if isinstance(value, str):
            value = WikonticPipeline._salvage_json(value)

        if isinstance(value, dict):
            lists = [v for v in value.values() if isinstance(v, list)]
            value = lists[0] if len(lists) == 1 else []

        if not isinstance(value, list):
            return []

        entities: list[dict] = []
        for item in value:
            if isinstance(item, dict):
                if item.get("entity"):
                    entities.append(item)
            elif isinstance(item, str) and item:
                entities.append({"entity": item})
        return entities

    #: Keys that mark a dict as *one* triplet rather than a container of them.
    _TRIPLET_KEYS = ("subject", "relation", "object")

    @staticmethod
    def _coerce_triplet_dict(value: Any) -> Any:
        """Normalise an ``extract_triplets_from_text`` reply to Wikontic's shape.

        ``base_inference_with_db._parse_extracted_triplets`` requires a dict with
        a ``"triplets"`` list; anything else is logged as "Triplet extraction
        response is not a dict" and turned into ``None``, after which the
        document silently never reaches the graph. Wikontic's prompt asks for
        that object and gpt-oss-20b obliges, but meno-lite-0.1 and
        Qwen2.5-7B-Instruct return the bare array — which cost roughly two
        thirds of the GraphRAG-Bench corpus before this existed.

        Mirror image of :meth:`_coerce_entity_list`, and deliberately
        conservative: the *elements* are never touched. Wikontic validates each
        triplet itself, and rewriting their content would change what is being
        measured rather than just how it is wrapped.

        A reply that already has the expected shape is returned **unchanged**
        (the identical object), which is what the caller uses to tell a genuine
        fix from a pass-through.
        """
        if isinstance(value, str):
            # get_completion hands back the raw string when its own JSON parse
            # fails — e.g. models that emit Python repr with single quotes.
            salvaged = WikonticPipeline._salvage_json(value)
            if salvaged is None:
                return {"triplets": []}
            coerced = WikonticPipeline._coerce_triplet_dict(salvaged)

            # Guard against salvaging a *fragment*. _salvage_json's positional
            # scan returns the first value it can decode anywhere in the text,
            # so an array that breaks partway through yields its first element —
            # one triplet out of however many the model produced. Storing that
            # is worse than storing nothing: count_triplets() sees 1,
            # is_indexed() calls the document done, and --resume never returns
            # to it. A shortfall means we truncated, so refuse and let the
            # document be retried.
            found = len(coerced.get("triplets") or [])
            markers = value.count('"subject"') + value.count("'subject'")
            if markers > found:
                logger.warning(
                    "Refusing a truncated triplet reply: the text names %d "
                    "triplet(s) but only %d could be parsed. Document left "
                    "unindexed on purpose so --resume retries it: %.300r",
                    markers, found, value,
                )
                return {"triplets": []}
            return coerced

        if isinstance(value, dict):
            if isinstance(value.get("triplets"), list):
                return value
            if any(key in value for key in WikonticPipeline._TRIPLET_KEYS):
                return {"triplets": [value]}
            lists = [v for v in value.values() if isinstance(v, list)]
            return {"triplets": lists[0]} if len(lists) == 1 else {"triplets": []}

        if isinstance(value, list):
            return {"triplets": value}

        return {"triplets": []}

    @staticmethod
    def _salvage_json(text: str) -> Any:
        """Parse the first JSON value in ``text``, ignoring anything after it.

        Falls back to :func:`ast.literal_eval` when no strict-JSON value is
        found: several models answer with a Python repr (single quotes,
        ``True``/``None``) that ``json.loads`` rejects outright. Only literals
        are evaluated — no names, no calls — so this cannot execute anything
        the model sends.
        """
        first = min((text.find(ch) for ch in "[{" if ch in text), default=-1)
        if first < 0:
            return None

        # Whole-value parse first. The positional scan below is greedy and will
        # happily return a nested empty list — a triplet's "qualifiers": [] is
        # the first thing in the string that parses as valid JSON when the reply
        # itself is a Python repr, and the whole document then reads as empty.
        try:
            return ast.literal_eval(text[first:].strip())
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            pass

        # Genuine JSON (true/false/null are not Python literals) and replies
        # with prose in front of the payload.
        decoder = json.JSONDecoder()
        for start, char in enumerate(text):
            if char in "[{":
                try:
                    parsed, _ = decoder.raw_decode(text[start:])
                except json.JSONDecodeError:
                    continue
                return parsed

        # A reply truncated by the token limit (the model looped) never closes
        # its brackets and lands here. Deliberately not repaired: half of a
        # degenerate reply is worse than a document we know is missing.
        return None

    def _normalize_entity_replies(self) -> None:
        """Make ``identify_relevant_entities`` always return Wikontic's shape."""
        original = self.extractor.identify_relevant_entities

        def normalized(*args: Any, **kwargs: Any) -> Any:
            raw = original(*args, **kwargs)
            fixed = self._coerce_entity_list(raw)
            if not (isinstance(raw, list)
                    and len(raw) == len(fixed)
                    and all(isinstance(item, dict) for item in raw)):
                self.entity_shape_fixes += 1
                logger.debug(
                    "Reshaped entity reply (%s -> %d entities): %.300r",
                    type(raw).__name__, len(fixed), raw,
                )
            return fixed

        self.extractor.identify_relevant_entities = normalized  # type: ignore[method-assign]

    def _normalize_triplet_replies(self) -> None:
        """Make triplet extraction always return Wikontic's ``{"triplets": [...]}``.

        Wraps every ``extract_triplets*`` method rather than the one we know
        about (``extract_triplets_from_text``): structured mode routes through
        its own extractor, and a silently unwrapped path would look exactly like
        a model that extracts nothing.
        """
        for name in dir(self.extractor):
            if not name.startswith("extract_triplets"):
                continue
            original = getattr(self.extractor, name, None)
            if callable(original):
                setattr(self.extractor, name, self._wrap_triplet_method(original))
                logger.debug("Triplet reply normalisation active on %s", name)

    def _wrap_triplet_method(self, original: Any) -> Any:
        def normalized(*args: Any, **kwargs: Any) -> Any:
            raw = original(*args, **kwargs)
            fixed = self._coerce_triplet_dict(raw)
            # Identity, not equality: _coerce_triplet_dict returns the very same
            # object when the shape was already right, so a pass-through never
            # inflates the counter.
            if fixed is not raw:
                self.triplet_shape_fixes += 1
                logger.warning(
                    "Reshaped triplet reply (%s -> %d triplets); without this "
                    "the document would not have reached the graph: %.300r",
                    type(raw).__name__, len(fixed.get("triplets") or []), raw,
                )
            return fixed

        return normalized

    def _log_llm_replies(self) -> None:
        """Log the parsed shape of every Wikontic LLM reply.

        ``LLMTripletExtractor.get_completion`` runs the reply through
        ``extract_json`` and returns a dict, a list — or the raw string when
        parsing fails, with no validation either way. Callers then index it as
        a dict (``e["entity"]``), so a differently shaped reply blows up deep
        inside Wikontic with a bare ``string indices must be integers``. This
        records what the model actually returned so the mismatch is visible.
        """
        original = self.extractor.get_completion

        def logged(*args: Any, **kwargs: Any) -> Any:
            result = original(*args, **kwargs)
            shape = type(result).__name__
            if isinstance(result, list) and result:
                shape += f"[{type(result[0]).__name__}]"
            elif isinstance(result, dict):
                shape += f"{sorted(result)[:8]}"
            logger.info("LLM reply shape=%s value=%.400r", shape, result)
            return result

        self.extractor.get_completion = logged  # type: ignore[method-assign]
        logger.info("LLM reply debug logging enabled")

    # ── storage helpers ────────────────────────────────────────────

    @staticmethod
    def _make_qdrant_backend(
        qdrant_url: str,
        qdrant_api_key: str | None,
        local_path: str | None,
        timeout: int | None = None,
    ) -> Any:
        """Create a Qdrant backend, optionally in server-less local-file mode.

        Wikontic's ``QdrantBackend`` builds its client without a timeout, and the
        qdrant-client default is under 10 seconds — too short on a networked
        filesystem, where a single ``create_payload_index`` can take ~10 s and
        collection creation 1-2 s each. ``timeout`` replaces the client with one
        that waits long enough.

        ``local_path`` swaps in ``QdrantClient(path=...)``, which persists to a
        directory without a server — useful where containers are not allowed.
        ``_in_memory`` stays ``True`` because the only thing it gates is
        ``create_payload_index``, which has no effect in local mode anyway.
        """
        from qdrant_client import QdrantClient

        if local_path:
            backend = create_backend("qdrant", qdrant_url=":memory:")
            kwargs = {"timeout": timeout} if timeout else {}
            backend.client = QdrantClient(path=str(local_path), **kwargs)
            logger.info("Qdrant running in local-file mode at %s (no server)", local_path)
            return backend

        backend = create_backend(
            "qdrant",
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
        )
        if timeout:
            backend.client = QdrantClient(
                url=qdrant_url, api_key=qdrant_api_key, timeout=timeout
            )
            logger.info("Qdrant client timeout set to %ss", timeout)
        return backend

    # ── RAGPipeline interface ──────────────────────────────────────

    def make_units(self, documents: list[Document]) -> list[IndexUnit]:
        """Corpus scope: one document = one sample."""
        return [
            IndexUnit(
                sample_id=doc.id,
                source_text_id="full_text",
                text=doc.text,
                doc_id=doc.id,
            )
            for doc in documents
            if doc.text
        ]

    def count_triplets(self, unit: IndexUnit) -> int:
        """How many triplets this unit put into the graph.

        Probes ``initial_triplets`` first: it holds every extracted triplet,
        including those later dropped by refinement, so it is the better
        completion marker.
        """
        query = {"sample_id": unit.sample_id, "source_text_id": unit.source_text_id}
        for collection in ("initial_triplets", "triplets"):
            try:
                found = self.triplets_db.match_documents(collection, query)
            except Exception as exc:  # collection may not exist yet
                logger.debug("Triplet probe on %s failed: %s", collection, exc)
                continue
            if found:
                return len(found)
        return 0

    def is_indexed(self, unit: IndexUnit) -> bool:
        """True when this unit's triplets are already stored.

        Mirrors the resume check in Wikontic's own ``dataset_inference.py``.
        A unit that yields no triplets at all is indistinguishable from an
        unprocessed one and will be retried.
        """
        return self.count_triplets(unit) > 0

    def _index_unit(self, unit: IndexUnit) -> None:
        if self.mode == "structured":
            self.inference.extract_triplets_with_ontology_filtering_and_add_to_db(
                text=unit.text,
                sample_id=unit.sample_id,
                source_text_id=unit.source_text_id,
                use_unidecode=self.use_unidecode,
            )
        else:
            self.inference.extract_triplets_and_add_to_db(
                text=unit.text,
                source_text_id=unit.source_text_id,
                sample_id=unit.sample_id,
            )

    def build_index(
        self,
        documents: list[Document] | None = None,
        units: list[IndexUnit] | None = None,
        workers: int = 1,
        resume: bool = False,
        timer: IndexTimer | None = None,
    ):
        """Extract triplets from documents and save them to the KG.

        ``workers`` > 1 indexes several units concurrently. Wikontic's inference
        and aligner objects are not documented as thread-safe — they share one
        contriever model and one OpenAI client — so verify triplet counts match
        a single-threaded run before trusting a parallel one.
        """
        if units is None:
            units = self.make_units(documents or [])
        total = len(units)

        def process(i_unit: tuple[int, IndexUnit]) -> None:
            i, unit = i_unit
            if resume and self.is_indexed(unit):
                logger.info("[%d/%d] Skipping already-indexed: %s", i + 1, total, unit.doc_id)
                if timer is not None:
                    timer.record_skipped()
                return
            logger.info(
                "[%d/%d] Processing document: %s (len=%d)", i + 1, total, unit.doc_id, len(unit.text)
            )
            try:
                if timer is not None:
                    with timer.measure(unit.doc_id, len(unit.text)):
                        self._index_unit(unit)
                else:
                    self._index_unit(unit)
            except Exception:
                logger.exception("  ✗ Failed: %s", unit.doc_id)
                return

            # Wikontic swallows its own extraction failures: when the model
            # loops until it hits the token limit the reply fails to parse,
            # extract_triplets_*_and_add_to_db returns normally and nothing is
            # written. Without this check the document is reported as done,
            # counted as a success, and its absence from the graph is
            # undetectable later — which matters most when the index is
            # exported and used elsewhere.
            n = self.count_triplets(unit)
            if n:
                logger.info("  ✓ Done: %s (%d triplets)", unit.doc_id, n)
            else:
                self.empty_docs += 1
                logger.warning(
                    "  !! NO TRIPLETS STORED: %s -- document is NOT in the graph "
                    "(look for 'Failed to parse JSON' above)", unit.doc_id
                )

        if workers <= 1:
            for item in enumerate(units):
                process(item)
        else:
            logger.info("Indexing %d units with %d workers", total, workers)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(process, enumerate(units)))

    @staticmethod
    def format_supporting(supporting: Any) -> list[str]:
        """Verbalise the triplets an answer was built from, one string each.

        Wikontic hands the LLM raw dicts (``subject`` / ``relation`` / ``object``
        plus optional ``qualifiers`` and ``source_text_id``) and never
        verbalises them, so the retrieved context has no textual form to export.
        GraphRAG-Benchmark's ``faithfulness``, ``context_relevancy`` and
        ``evidence_recall`` all read a list of context *strings*, which is what
        this produces.

        Never raises: a shape we did not anticipate is stringified rather than
        losing the whole answer.
        """
        if not supporting:
            return []
        if isinstance(supporting, dict):
            supporting = [supporting]

        lines: list[str] = []
        for item in supporting:
            if not isinstance(item, dict):
                lines.append(str(item))
                continue
            subject = item.get("subject")
            relation = item.get("relation") or item.get("predicate")
            obj = item.get("object")
            if subject is None and relation is None and obj is None:
                lines.append(str(item))
                continue
            line = f"{subject} — {relation} — {obj}"
            qualifiers = item.get("qualifiers")
            if qualifiers:
                line += f" ({WikonticPipeline._format_qualifiers(qualifiers)})"
            lines.append(line)
        return lines

    @staticmethod
    def _format_qualifiers(qualifiers: Any) -> str:
        """Qualifiers are a dict in some replies and a list of dicts in others."""
        if isinstance(qualifiers, dict):
            return "; ".join(f"{k}: {v}" for k, v in qualifiers.items())
        if isinstance(qualifiers, list):
            parts = []
            for qualifier in qualifiers:
                if isinstance(qualifier, dict):
                    parts.append("; ".join(f"{k}: {v}" for k, v in qualifier.items()))
                else:
                    parts.append(str(qualifier))
            return "; ".join(p for p in parts if p)
        return str(qualifiers)

    def generate_answer(self, question: str, sample_id: str | None = None) -> tuple[str, Any]:
        """Answer a question using the built KG.

        ``sample_id`` scopes retrieval to a single sample's triplets — the setup
        used in Wikontic's own ``qa_eval_musique.py``. ``None`` searches the
        whole graph.
        """
        logger.info("Answering question: %s", question)
        try:
            linked = self.inference.identify_relevant_entities_from_question_with_llm(
                question=question, sample_id=sample_id
            )
            result = self.inference.answer_question_with_llm(
                question=question,
                linked_entities=linked or [],
                sample_id=sample_id,
                hop_depth=self.hop_depth,
                use_filtered_triplets=self.use_filtered_triplets,
                use_qualifiers=self.use_qualifiers,
            )
            # answer_question_with_llm returns (supporting_triplets, answer).
            if isinstance(result, tuple) and len(result) == 2:
                supporting, answer_text = result
            else:
                supporting, answer_text = None, result

            if not answer_text:
                # Empty answers are the interesting failure mode, and the two
                # causes need different fixes: retrieval found nothing to answer
                # from, or the model returned nothing usable. Log enough to tell
                # them apart without a separate debug run.
                self.empty_answers += 1
                logger.warning(
                    "Empty answer: linked_entities=%d supporting_triplets=%s reply=%r",
                    len(linked or []),
                    len(supporting) if supporting is not None else "n/a",
                    answer_text,
                )
            else:
                logger.info("Answer: %s", str(answer_text)[:200])
            return answer_text, supporting
        except Exception:
            # Full traceback: Wikontic's prompts are model-specific and a reply
            # shaped differently than expected surfaces deep inside its code
            # (e.g. `e["entity"]` over a list of plain strings). Without the
            # traceback the message alone does not say which call broke.
            logger.exception("Failed to answer")
            return FAILED_ANSWER, None

    def answer_with_collapsing(
        self,
        question: str,
        max_attempts: int = 5,
        sample_id: str | None = None,
    ) -> tuple[str, Any]:
        """Answer with decomposition of complex questions (QA collapsing).

        This is the QA path used in Wikontic's published evaluation scripts.
        """
        logger.info("Answering (collapsing mode): %s", question)
        try:
            answer = self.inference.answer_with_qa_collapsing(
                question=question,
                sample_id=sample_id,
                max_attempts=max_attempts,
                use_qualifiers=self.use_qualifiers,
                use_filtered_triplets=self.use_filtered_triplets,
            )
            return answer, None
        except Exception:
            logger.exception("Failed to answer (collapsing)")
            return FAILED_ANSWER, None
