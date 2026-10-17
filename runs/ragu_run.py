from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from ragu import QueryPlanEngine
from ragu.models.llm import CachedAsyncOpenAI, LLMOpenAI
from ragu.models.embedder import EmbedderOpenAI

from natural_rag.dataset import RAGDataset
from natural_rag.paths import dataset_name_from_path, resolve_run_dirs
from natural_rag.pipelines.ragu_pipelines import RAGUPipeline
from natural_rag.timing import IndexTimer, LLMCallCounter, attach_counter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGU on a dataset.")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/bioasq")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/ragu")),
        help="Output directory for index and answers.",
    )
    parser.add_argument(
        "--index-model",
        default=os.environ.get("INDEX_MODEL"),
        help="Label of the model that BUILT the graph (e.g. gpt-oss-20b). "
             "When set, inserted into the index/answers path as a subdirectory.",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path(os.environ["INDEX_DIR"]) if os.environ.get("INDEX_DIR") else None,
        help="Read/write the index here instead of <output-dir>/<dataset>/[<index-model>/]index. "
             "Lets several answer variants share one index.",
    )
    parser.add_argument(
        "--save-context",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("SAVE_CONTEXT", "").lower() in ("1", "true", "yes"),
        help="Write answers/<i>.context.json: the context the answer was generated from, "
             "its token count, answer seconds and retrieval metrics.",
    )
    parser.add_argument(
        "--context-budget",
        type=int,
        default=int(os.environ.get("CONTEXT_BUDGET", "0")) or None,
        help="Max context tokens for the answer prompt (RAGU max_context_length). "
             "Default: the engine default (Settings.llm_context_token_limit).",
    )
    parser.add_argument(
        "--selector",
        choices=["none", "pointwise", "cosine"],
        default=os.environ.get("SELECTOR", "none"),
        help="Retrieval-time selection (dev RAGU with ragu.decision): pointwise asks the "
             "decision model; cosine keeps the --select-top-* most query-similar candidates.",
    )
    parser.add_argument(
        "--decision-model-name",
        default=os.environ.get("DECISION_MODEL_NAME"),
        help="Model for the single-token decision model; uses the answering client.",
    )
    parser.add_argument(
        "--decision-constraint",
        choices=["none", "logit_bias", "allowed_token_ids"],
        default=os.environ.get("DECISION_CONSTRAINT", "none"),
    )
    parser.add_argument("--select-pool-entities", type=int, default=None)
    parser.add_argument("--select-pool-relations", type=int, default=None)
    parser.add_argument("--select-pool-chunks", type=int, default=None)
    parser.add_argument("--select-threshold", type=float, default=None)
    parser.add_argument("--select-floor", type=int, default=None)
    parser.add_argument("--select-top-entities", type=int, default=None)
    parser.add_argument("--select-top-relations", type=int, default=None)
    parser.add_argument("--select-top-chunks", type=int, default=None)
    parser.add_argument(
        "--select-hops", type=int, default=None,
        help="pointwise only: hops walked from relations the decision model kept (1 = seeds only).",
    )
    parser.add_argument(
        "--select-keep-seed-context", action=argparse.BooleanOptionalAction, default=None,
        help="pointwise only: keep the full seed context and append what further hops select.",
    )
    parser.add_argument(
        "--ppr-chunks", type=int, default=None,
        help="Append this many Personalized PageRank chunks (seeded by the decision model if any).",
    )
    parser.add_argument("--ppr-alpha", type=float, default=None)
    parser.add_argument(
        "--build-index",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--answer",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--limit-docs",
        type=int,
        default=int(os.environ.get("LIMIT_DOCS", "0")) or None,
        help="Index only the first N documents (smoke tests).",
    )
    parser.add_argument(
        "--limit-questions",
        type=int,
        default=int(os.environ.get("LIMIT_QUESTIONS", "0")) or None,
        help="Answer only the first N questions (smoke tests).",
    )
    parser.add_argument(
        "--chunker",
        choices=["simple", "smart"],
        default=os.environ.get("CHUNKER", "simple"),
    )
    parser.add_argument(
        "--use-chunks",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--use-summary",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--simple-chunk-size",
        type=int,
        default=int(os.environ.get("SIMPLE_CHUNK_SIZE", "2048")),
    )
    parser.add_argument(
        "--simple-chunk-overlap",
        type=int,
        default=int(os.environ.get("SIMPLE_CHUNK_OVERLAP", "0")),
    )
    parser.add_argument(
        "--openai-base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--embed-base-url",
        default=os.environ.get("EMBED_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")),
    )
    parser.add_argument(
        "--openai-api-key",
        default=os.environ.get("OPENAI_API_KEY"),
    )
    parser.add_argument(
        "--openai-rate-min-delay",
        type=float,
        default=float(os.environ.get("OPENAI_RATE_MIN_DELAY", "2")),
    )
    parser.add_argument(
        "--openai-rate-max-simultaneous",
        type=int,
        default=int(os.environ.get("OPENAI_RATE_MAX_SIMULTANEOUS", "10")),
    )
    parser.add_argument(
        "--llm-cache",
        default=os.environ.get("LLM_CACHE", "tmp/llm_cache"),
    )
    parser.add_argument(
        "--llm-debug-cache",
        default=os.environ.get("LLM_DEBUG_CACHE", "tmp/llm_debug_cache"),
    )
    parser.add_argument(
        "--max-completion-tokens",
        # 16384 is the max completion-token limit of gpt-4o-mini (via litellm);
        # a higher default triggers a 400 BadRequest. Override for models that
        # support more.
        type=int,
        default=int(os.environ.get("MAX_COMPLETION_TOKENS", "16384")),
    )
    parser.add_argument(
        "--builder-model-name",
        default=os.environ.get("BUILDER_MODEL_NAME") or os.environ.get("LLM_MODEL") or "mistralai/mistral-medium-3",
    )
    parser.add_argument(
        "--assistant-model-name",
        default=os.environ.get("ASSISTANT_MODEL_NAME") or os.environ.get("LLM_MODEL"),
    )
    parser.add_argument(
        "--embedding-model-name",
        default=os.environ.get("EMBEDDING_MODEL_NAME") or os.environ.get("EMBED_MODEL") or "emb-qwen/qwen3-embedding-8b",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=int(os.environ.get("EMBEDDING_DIM", "4096")),
    )
    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=int(os.environ.get("EMBED_BATCH_SIZE", "32")),
        help="Maximum texts per single embedding API call.",
    )
    parser.add_argument(
        "--retrieval-top-k",
        type=int,
        default=int(os.environ.get("RETRIEVAL_TOP_K", "20")),
    )
    parser.add_argument(
        "--qa-top-k",
        type=int,
        default=int(os.environ.get("QA_TOP_K", "20")),
    )
    parser.add_argument(
        "--query-engine",
        choices=["local", "query_plan", "naive"],
        default=os.environ.get("QUERY_ENGINE", "local"),
        help="Search engine for answering: local (default), query_plan "
             "(decomposes complex queries), or naive (plain vector RAG over chunks).",
    )
    parser.add_argument(
        "--short-answers",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("SHORT_ANSWERS", "").lower() in ("1", "true", "yes"),
        help="Use a brief extractive answer prompt (for short-answer benchmarks).",
    )
    parser.add_argument(
        "--always-answer",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("ALWAYS_ANSWER", "").lower() in ("1", "true", "yes"),
        help="With --short-answers: forbid 'I don't know' and always give the best answer. "
             "(Not --no-abstain: BooleanOptionalAction treats a --no- prefix as negation.)",
    )
    parser.add_argument(
        "--tokenizer-backend",
        default=os.environ.get("TOKENIZER_BACKEND", "tiktoken"),
    )
    parser.add_argument(
        "--tokenizer-llm-name",
        default=os.environ.get("TOKENIZER_LLM_NAME", "gpt-4o"),
    )
    parser.add_argument(
        "--tokenizer-embedder-name",
        default=os.environ.get("TOKENIZER_EMBEDDER_NAME", "gpt-4o"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    if not args.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")
    if not args.assistant_model_name:
        args.assistant_model_name = args.builder_model_name

    dataset = RAGDataset.load_auto(args.dataset_path)
    if args.limit_docs is not None or args.limit_questions is not None:
        documents = (
            dict(list(dataset.documents.items())[: args.limit_docs])
            if args.limit_docs is not None
            else dataset.documents
        )
        questions = dataset.questions
        if args.limit_docs is not None:
            if args.limit_questions is not None:
                # Порядок корпуса не связан с вопросами: первые попавшиеся
                # доки может не касаться ни один вопрос. Поэтому срез для
                # смоука собираем из доков, на которые ссылаются первые N
                # вопросов, и только потом добираем корпусом до лимита.
                wanted: list[str] = []
                seen_ids: set[str] = set()
                for q in questions[: args.limit_questions]:
                    for source in q.relevant or []:
                        if source.doc_id in dataset.documents and source.doc_id not in seen_ids:
                            seen_ids.add(source.doc_id)
                            wanted.append(source.doc_id)
                rest = [i for i in dataset.documents if i not in seen_ids]
                keep_ids = (wanted + rest)[: args.limit_docs]
                documents = {i: dataset.documents[i] for i in keep_ids}
            # Вопросы, чьи relevant-источники выпали при обрезке корпуса,
            # невалидны (check_ids_exist упадёт). Фильтруем по всему списку
            # и только потом берём первые N — иначе на датасетах, где первые
            # вопросы ссылаются на отрезанные доки, смоук остался бы без
            # ни одного ответимого вопроса.
            answerable = [
                q for q in questions
                if q.relevant is None
                or all(s.doc_id in documents for s in q.relevant)
            ]
            dropped = len(questions) - len(answerable)
            if dropped:
                print(
                    f"--limit-docs: {dropped} of {len(questions)} question(s) "
                    "reference docs outside the kept corpus slice"
                )
            if args.limit_questions is not None:
                questions = answerable[: args.limit_questions]
            else:
                questions = answerable
        elif args.limit_questions is not None:
            questions = questions[: args.limit_questions]
        dataset = RAGDataset(documents=documents, questions=questions)

    index_dir, answers_dir, base_dir = resolve_run_dirs(
        args.output_dir, args.dataset_path, args.index_model
    )
    if args.index_dir is not None:
        index_dir = args.index_dir
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    llm_counter = LLMCallCounter()

    llm_client = CachedAsyncOpenAI(
        base_url=args.openai_base_url,
        api_key=args.openai_api_key,
        rate_min_delay=args.openai_rate_min_delay,
        rate_max_simultaneous=args.openai_rate_max_simultaneous,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache=args.llm_cache,
        debug_errors_storage=args.llm_debug_cache,
        max_completion_tokens=args.max_completion_tokens,
    )

    embed_client = CachedAsyncOpenAI(
        base_url=args.embed_base_url,
        api_key=args.openai_api_key,
        rate_min_delay=args.openai_rate_min_delay,
        rate_max_simultaneous=args.openai_rate_max_simultaneous,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache=args.llm_cache,
        debug_errors_storage=args.llm_debug_cache,
        max_completion_tokens=args.max_completion_tokens,
    )

    # Best-effort: RAGU's client wrapper may not expose chat.completions, in
    # which case the summary simply carries no LLM-call counts.
    attach_counter(llm_client, llm_counter)

    pipeline = RAGUPipeline(
        language='english',
        index_dir=index_dir,
        builder_llm=LLMOpenAI(llm_client, args.builder_model_name),
        assistant_llm=LLMOpenAI(llm_client, args.assistant_model_name),
        embedder=EmbedderOpenAI(embed_client, args.embedding_model_name, dim=args.embedding_dim, batch_size=args.embed_batch_size),
        chunker_name=args.chunker,
        query_use_chunks=args.use_chunks,
        query_use_summary=args.use_summary,
        simple_chunk_size=args.simple_chunk_size,
        simple_chunk_overlap=args.simple_chunk_overlap,
        retrieval_top_k=args.retrieval_top_k,
        qa_top_k=args.qa_top_k,
        tokenizer_backend=args.tokenizer_backend,
        tokenizer_llm_name=args.tokenizer_llm_name,
        tokenizer_embedder_name=args.tokenizer_embedder_name,
        query_engine=args.query_engine,
        short_answers=args.short_answers,
        no_abstain=args.always_answer,
        max_context_length=args.context_budget,
        decision_llm=(
            LLMOpenAI(llm_client, args.decision_model_name) if args.decision_model_name else None
        ),
        decision_constraint=args.decision_constraint,
        selector=args.selector,
        select_options={
            key: value for key, value in {
                "select_pool_entities": args.select_pool_entities,
                "select_pool_relations": args.select_pool_relations,
                "select_pool_chunks": args.select_pool_chunks,
                "select_threshold": args.select_threshold,
                "select_floor": args.select_floor,
                "select_top_entities": args.select_top_entities,
                "select_top_relations": args.select_top_relations,
                "select_top_chunks": args.select_top_chunks,
                "select_hops": args.select_hops,
                "select_keep_seed_context": args.select_keep_seed_context,
                "ppr_chunks": args.ppr_chunks,
                "ppr_alpha": args.ppr_alpha,
            }.items() if value is not None
        },
    )

    if args.build_index:
        documents = list(dataset.documents.values())
        # RAGU indexes the whole corpus in one call, so the timer records a
        # single step covering every document rather than per-document rows.
        with IndexTimer(
            base_dir,
            engine="ragu",
            dataset=dataset_name_from_path(args.dataset_path),
            model=args.index_model or args.builder_model_name,
            counter=llm_counter,
            total_units=len(documents),
            extra={"query_engine": args.query_engine, "chunker": args.chunker},
        ) as timer:
            total_chars = sum(len(doc.text) for doc in documents if doc.text)
            with timer.measure("<corpus>", total_chars, count=len(documents)):
                pipeline.build_index(documents=documents)

    if args.answer:
        # Answer all questions within a single event loop so RAGU's shared HTTP
        # client and rate limiters stay bound to one loop (avoids cross-loop
        # reuse warnings and spurious APIConnectionError retries).
        async def _generate_all() -> None:
            for q_idx, question in enumerate(dataset.questions):
                answer_path = answers_dir / f'{q_idx}.txt'
                if answer_path.exists() and answer_path.stat().st_size > 0 and not args.force:
                    continue
                answer, context = await pipeline.a_generate_answer(question.text)
                answer_path.write_text(answer, encoding="utf-8")
                if args.save_context:
                    write_context(
                        answers_dir / f'{q_idx}.context.json',
                        pipeline,
                        context,
                        seconds=getattr(pipeline, "last_answer_seconds", None),
                    )

        asyncio.run(_generate_all())


def write_context(path: Path, pipeline: RAGUPipeline, context: Any, seconds: float | None) -> None:
    """Save the context an answer was generated from, as the answer prompt saw it.

    The text is passed through the engine's own truncation, so ``context_tokens``
    is the size of what the answering LLM actually read.
    """
    text = str(context) if context is not None else ""
    truncation = getattr(pipeline.search_engine, "truncation", None) or getattr(
        getattr(pipeline, "local_search", None), "truncation", None
    )
    tokens: int | None = None
    if truncation is not None and text:
        text = truncation(text)
        encoder = getattr(truncation, "encoder", None)
        tokens = len(encoder.encode(text)) if encoder is not None else None
    metrics = getattr(context, "metrics", None)
    payload = {
        "context": [text] if text else [],
        "context_tokens": tokens,
        "answer_seconds": seconds,
        "metrics": json.loads(json.dumps(metrics, default=str)) if metrics else None,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()