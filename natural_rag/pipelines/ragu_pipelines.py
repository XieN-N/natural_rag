import asyncio
import inspect
import re
import sys
import time
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
from ragu.common.prompts.messages import ChatMessages, UserMessage
from ragu.common.prompts.prompt_storage import RAGUInstruction
from ragu.models.embedder import Embedder
from ragu.models.llm import LLM
from ragu.search_engine.local_search import LocalSearchEngine
from ragu.search_engine.naive_search import NaiveSearchEngine


# Brief-answer prompt used when reference answers are short (e.g. bioasq,
# musique, 2wikimultihopqa). Mirrors DEFAULT_RESPONSE_ONLY_PROMPT's jinja
# variables ({{ query }}, {{ context }}, {{ language }}) but forces a terse,
# extractive answer so the answer length matches the short gold answers.
SHORT_ANSWER_PROMPT = """
**Goal**
Answer the query as briefly as possible using the context.

**Instructions**
1. Output ONLY the direct answer: a single entity, name, number, date, or a
   short semicolon-separated list of such items.
2. No explanations, no full sentences, no restating of the question, no
   markdown, no citations.
3. If the answer is not supported by the context, output exactly: I don't know.

Query: {{ query }}
Context: {{ context }}

Provide the answer in the following language: {{ language }}
"""

# Same terse prompt without the right to abstain. On benchmarks where every
# question has an answer (MuSiQue, 2Wiki), "I don't know" always scores zero,
# while other systems (e.g. HippoRAG 2) always commit to their best guess.
NO_ABSTAIN_SHORT_ANSWER_PROMPT = SHORT_ANSWER_PROMPT.replace(
    "3. If the answer is not supported by the context, output exactly: I don't know.",
    "3. Always give your single best answer, even if the context does not state it\n"
    "   explicitly; never answer \"I don't know\".",
)
assert NO_ABSTAIN_SHORT_ANSWER_PROMPT != SHORT_ANSWER_PROMPT

# Decision prompt that counts intermediate links of a multi-hop chain as useful.
# Same variables as DEFAULT_DECISION_POINTWISE_PROMPT and the same single-token answer.
CHAIN_DECISION_POINTWISE_PROMPT = """
Query: {{ query }}
{%- if state_context %}

Facts gathered so far:
{{ state_context }}
{%- endif %}

Candidate:
{{ candidate }}

Answering the query may take a chain of facts, and the query may describe an entity without naming it.
Answer Y if the candidate states the answer, identifies an entity the query describes, or gives a fact about an entity on the way to the answer, even if it does not answer the query by itself.
Answer N only if the candidate is unrelated to every step.
Answer Y or N:
"""

_DIRECT_ANSWER_RULES = (
    "1. Output ONLY the direct answer: a single entity, name, number, date, or a\n"
    "   short semicolon-separated list of such items.\n"
    "2. No explanations, no full sentences, no restating of the question, no\n"
    "   markdown, no citations."
)
# HippoRAG 2 style: a short "Thought:" before the final "Answer:" line. Only the
# text after the last "Answer:" is kept as the answer (see extract_final_answer).
_REASON_FIRST_RULES = (
    "1. First write \"Thought:\" and reason briefly, in at most three sentences,\n"
    "   about which facts in the context lead to the answer.\n"
    "2. Then write \"Answer:\" on a new line followed ONLY by the direct answer: a\n"
    "   single entity, name, number, date, or a short semicolon-separated list of\n"
    "   such items, with no explanation."
)


def reason_first_prompt(prompt: str) -> str:
    """The terse prompt with a short reasoning step before the final answer."""
    reasoning = prompt.replace(_DIRECT_ANSWER_RULES, _REASON_FIRST_RULES)
    assert reasoning != prompt
    return reasoning


_ANSWER_MARK = re.compile(r"answer\s*:", re.IGNORECASE)


def extract_final_answer(text: str) -> str:
    """Answer after the last "Answer:" mark; the last non-empty line without one."""
    marks = list(_ANSWER_MARK.finditer(text))
    if marks:
        tail = text[marks[-1].end():].strip()
    else:
        lines = [line for line in text.splitlines() if line.strip()]
        tail = lines[-1] if lines else text
    first_line = tail.strip().splitlines()[0] if tail.strip() else ""
    return first_line.strip().strip("*").strip()


def _set_short_prompt(engine: Any, name: str, instruction: Any) -> None:
    """Swap in the terse answer prompt, where the installed RAGU allows it.

    ``update_prompt`` is not part of every build's engine API. Losing the terse
    prompt silently would turn a short-answer benchmark into a verbose run and
    show up only as a collapsed ROUGE-L score, so refuse instead of guessing.
    """
    if not hasattr(engine, "update_prompt"):
        raise RuntimeError(
            f"--short-answers was requested but {type(engine).__name__} has no "
            "update_prompt(); this RAGU build cannot take the terse answer prompt."
        )
    engine.update_prompt(name, instruction)


def _is_environment_error(exc: BaseException) -> bool:
    """Whether an answer failure comes from the environment rather than the question.

    Connection errors (the local embedder or the LLM endpoint is down), timeouts,
    authentication failures, rate limits and server errors that survived the
    retries say nothing about the question, so the run must stop instead of
    recording a refusal for it.
    """
    try:
        import openai
    except ImportError:
        return False
    return isinstance(exc, (
        openai.APIConnectionError,
        openai.AuthenticationError,
        openai.PermissionDeniedError,
        openai.RateLimitError,
        openai.InternalServerError,
    ))


def _takes_params(engine: Any) -> bool:
    """Whether this RAGU build passes retrieval options as a ``params`` object.

    The dev branch replaced ``a_query(query, top_k=..., use_chunks=...)`` with
    ``a_query(query, params: EngineParams | None)``. Both conventions have to
    work: the pinned release still takes keyword arguments.
    """
    try:
        return "params" in inspect.signature(engine.a_query).parameters
    except (TypeError, ValueError):
        return False


def _params_class(engine: Any) -> type | None:
    """The ``EngineParams`` subclass declared next to ``engine``'s own class.

    Each engine declares only the options it accepts, so the class is found by
    looking in the module that defines the engine rather than by importing a
    fixed name -- which of the five engines is in use is decided by the caller.
    """
    module = sys.modules.get(type(engine).__module__)
    if module is None:
        return None
    found = [
        obj
        for name, obj in vars(module).items()
        if isinstance(obj, type)
        and name.endswith("Params")
        and obj.__module__ == module.__name__
    ]
    return found[0] if len(found) == 1 else None


#: Query engines built on the decision model, and those wrapped in QueryPlanEngine.
DECISION_ENGINES = ("decision", "query_plan_decision")
QUERY_PLAN_ENGINES = ("query_plan", "query_plan_decision")


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
        # True because the answer path used to hardcode use_chunks=True and
        # ignore this field; `check_index_ready.py` relies on that default.
        query_use_chunks: bool = True,
        chunker_name: str = "smart",
        simple_chunk_size: int = 2048,
        simple_chunk_overlap: int = 0,
        retrieval_top_k: int = 20,
        qa_top_k: int = 20,
        tokenizer_backend: str = "tiktoken",
        tokenizer_llm_name: str = "gpt-4o",
        tokenizer_embedder_name: str = "gpt-4o",
        query_engine: str = "local",
        short_answers: bool = False,
        no_abstain: bool = False,
        reason_first: bool = False,
        max_context_length: int | None = None,
        decision_llm: LLM | None = None,
        decision_constraint: str = "none",
        decision_model: Any = None,
        decision_options: dict[str, Any] | None = None,
        decision_prompt: str = "default",
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
        # query_engine "decision" (dev RAGU with ragu.decision only): a ready model
        # (decision_model, e.g. a replay stub) wins over one built on decision_llm;
        # decision_options are DecisionParams fields, empty keeps the engine defaults.
        uses_decision = query_engine in DECISION_ENGINES
        self.decision_options = dict(decision_options or {})
        self.decision_model: Any = decision_model
        if self.decision_model is None and decision_llm is not None:
            from ragu.decision import DecisionModel
            # One provider-rejected candidate (e.g. a content filter) must not turn
            # the whole question into a placeholder answer.
            self.decision_model = DecisionModel(  # type: ignore[call-arg]
                decision_llm, constraint=decision_constraint, skip_failed_requests=True,  # type: ignore[arg-type]
            )
        if decision_prompt == "chain":
            from ragu.common.prompts.default_templates import DEFAULT_DECISION_SYSTEM_PROMPT
            from ragu.common.prompts.messages import SystemMessage

            self.decision_model.update_prompt("decision_pointwise", RAGUInstruction(
                messages=ChatMessages.from_messages([
                    SystemMessage(content=DEFAULT_DECISION_SYSTEM_PROMPT),
                    UserMessage(content=CHAIN_DECISION_POINTWISE_PROMPT),
                ]),
                pydantic_model=str,
                description="Y/N judgement that counts intermediate links of a chain as useful.",
            ))
        if uses_decision and self.decision_model is None:
            raise ValueError(f"query_engine={query_engine!r} needs a decision LLM (--decision-model-name)")
        if not uses_decision and (self.decision_model is not None or self.decision_options):
            # Otherwise a run asked to select would silently answer from the full context.
            raise ValueError(f"Decision-model options need a decision query engine, got {query_engine!r}")
        if reason_first and not short_answers:
            raise ValueError("reason_first works with the terse prompt only (short_answers=True)")
        self.reason_first = reason_first
        self.last_raw_answer: str | None = None

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

        # Pass only kwargs the installed RAGU version's KnowledgeGraph accepts
        # (its signature has drifted across versions: tokenizer/embedder-token
        # args were removed).
        kg_kwargs: dict[str, Any] = {
            "llm": self.builder_llm,
            "embedder": self.embedder,
            "chunker": self.chunker,
            "artifact_extractor": self.artifact_extractor,
            "builder_settings": self.builder_settings,
            "language": self.language,
            "embedder_token_limit": 8000,
            "tokenizer_backend": tokenizer_backend,
            "tokenizer_llm_name": tokenizer_llm_name,
            "tokenizer_embedder_name": tokenizer_embedder_name,
        }
        kg_params = inspect.signature(KnowledgeGraph.__init__).parameters
        self.knowledge_graph = KnowledgeGraph(
            **{k: v for k, v in kg_kwargs.items() if k in kg_params}
        )

        self.query_engine = query_engine

        def _short_instruction() -> RAGUInstruction:
            prompt = NO_ABSTAIN_SHORT_ANSWER_PROMPT if no_abstain else SHORT_ANSWER_PROMPT
            if reason_first:
                prompt = reason_first_prompt(prompt)
            return RAGUInstruction(
                messages=ChatMessages.from_messages([UserMessage(content=prompt)]),
                pydantic_model=str,
                description="Brief extractive answer prompt for short-answer benchmarks.",
            )

        if query_engine == "naive":
            # Naive = plain vector RAG over chunks (uses the same RAGU index:
            # chunk vector DB + chunk KV). Graph/entities are not traversed.
            naive_search = NaiveSearchEngine(
                self.assistant_llm,
                self.knowledge_graph,
                self.embedder,
                tokenizer_model="gpt-4o-mini",
                language=self.language,
            )
            if short_answers:
                _set_short_prompt(naive_search, "naive_search", _short_instruction())
            self.search_engine = naive_search
        else:
            engine_kwargs: dict[str, Any] = {
                "tokenizer_model": "gpt-4o-mini",
                "language": self.language,
                "max_context_length": max_context_length,
            }
            if uses_decision:
                # Imported here: the pinned release has no such module.
                from ragu.search_engine.decision_search import DecisionSearchEngine

                graph_engine: Any = DecisionSearchEngine(
                    self.assistant_llm,
                    self.knowledge_graph,
                    self.embedder,
                    self.decision_model,
                    **engine_kwargs,
                )
            else:
                # Pass only kwargs the installed LocalSearchEngine accepts.
                local_params = inspect.signature(LocalSearchEngine.__init__).parameters
                graph_engine = LocalSearchEngine(
                    self.assistant_llm,
                    self.knowledge_graph,
                    self.embedder,
                    **{k: v for k, v in engine_kwargs.items() if k in local_params and v is not None},
                )
            self.graph_engine = graph_engine
            if short_answers:
                _set_short_prompt(graph_engine, "local_search", _short_instruction())
            self.search_engine = (
                QueryPlanEngine(graph_engine) if query_engine in QUERY_PLAN_ENGINES else graph_engine
            )

        # Resolve the calling convention once, not per question. QueryPlanEngine
        # wraps a graph engine and may not declare a params class of its own,
        # so fall back to the wrapped engine's.
        self.uses_engine_params = _takes_params(self.search_engine)
        self.params_class = None
        if self.uses_engine_params:
            self.params_class = _params_class(self.search_engine)
            if self.params_class is None and hasattr(self, "graph_engine"):
                self.params_class = _params_class(self.graph_engine)
            if self.params_class is None:
                # Falling back to the engine's own defaults would silently
                # discard --retrieval-top-k / --qa-top-k, so say so out loud.
                ragu_logger.warning(
                    f"{type(self.search_engine).__name__} takes a params object but no "
                    "EngineParams subclass was found next to it; retrieval will run "
                    "with the engine's built-in defaults and top_k settings are ignored."
                )

    def build_index(self, documents: list[Document]):
        docs = [doc.text for doc in documents if doc.text]
        asyncio.run(self.knowledge_graph.build_from_docs(docs))

    def _retrieval_options(self, top_k: int) -> dict[str, Any]:
        """Retrieval options this engine understands, as plain keyword names.

        NaiveSearchEngine works on chunks only and takes neither ``use_chunks``
        nor ``use_summary``; the graph engines take both.
        """
        options: dict[str, Any] = {"top_k": top_k}
        if self.query_engine != "naive":
            options["use_chunks"] = self.query_use_chunks
            options["use_summary"] = self.query_use_summary
            options.update(self.decision_options)
        return options

    def _call_args(self, top_k: int) -> tuple[tuple, dict]:
        """Positional and keyword arguments for a_search/a_query on this build."""
        options = self._retrieval_options(top_k)
        if not self.uses_engine_params:
            # The pinned release has no ``use_summary`` keyword on the engines.
            options.pop("use_summary", None)
            return (), options
        if self.params_class is None:
            return (), {}
        accepted = inspect.signature(self.params_class).parameters
        return (self.params_class(**{k: v for k, v in options.items() if k in accepted}),), {}

    async def _answer(self, question: str, max_retries: int = 3) -> tuple[str, Any]:
        search_args, search_kwargs = self._call_args(self.retrieval_top_k)
        qa_args, qa_kwargs = self._call_args(self.qa_top_k)
        context: Any = None
        self.last_answer_seconds = 0.0
        self.last_raw_answer = None
        for attempt in range(max_retries):
            started = time.perf_counter()
            try:
                if self.uses_engine_params:
                    # dev RAGU returns the retrieval it answered from, so one
                    # retrieval per question is enough (and is what the answer saw).
                    response = await self.search_engine.a_query(question, *qa_args, **qa_kwargs)
                    context = getattr(response, "retrieval", None)
                else:
                    context = await self.search_engine.a_search(question, *search_args, **search_kwargs)
                    response = await self.search_engine.a_query(question, *qa_args, **qa_kwargs)
                self.last_answer_seconds = time.perf_counter() - started
            except Exception as exc:
                # A single bad question (e.g. provider content-filter 400, which
                # is not retryable) must not crash the whole batch. Log and
                # return a refusal placeholder so the run continues. A broken
                # environment (endpoint down, auth, rate limit after retries) is
                # raised instead: as placeholders it would be scored as answers.
                if _is_environment_error(exc):
                    raise
                ragu_logger.warning(
                    f"Answer generation failed ({type(exc).__name__}: {exc}); "
                    f"returning 'I don't know.' placeholder for this question."
                )
                return "I don't know.", context
            if response.response and response.response.strip():
                if self.reason_first:
                    self.last_raw_answer = response.response
                    return extract_final_answer(response.response) or response.response, context
                return response.response, context
            ragu_logger.warning(f"Empty answer on attempt {attempt+1}/{max_retries}, retrying...")
        return "NO ANSWER OBTAINED", context

    def generate_answer(self, question: str) -> tuple[str, Any]:
        return asyncio.run(self._answer(question))

    async def a_generate_answer(self, question: str) -> tuple[str, Any]:
        """Async entry point so a caller can answer many questions inside a
        single event loop. Using this (instead of per-question ``asyncio.run``
        via :meth:`generate_answer`) keeps RAGU's shared HTTP client and rate
        limiters bound to one loop, avoiding cross-loop reuse warnings and the
        spurious ``APIConnectionError`` retries that come with it.
        """
        return await self._answer(question)