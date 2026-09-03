"""Run Wikontic on a dataset.

Two graph scopes are supported:

``corpus`` (default)
    One knowledge graph over the whole corpus; questions are answered against
    all of it (``sample_id=None``). This is the realistic RAG regime and the one
    RAGU is compared in.

``per_sample``
    The setup used in Wikontic's own published evaluation
    (``inference_and_eval/qa_eval_musique.py``): each question gets its own
    little graph built from its supporting paragraphs plus distractors, and
    retrieval is filtered by ``sample_id``. Use it to reproduce paper-like
    conditions on a multi-hop dataset.
"""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv ships with the [wikontic] extra
    def load_dotenv(*args, **kwargs) -> bool:
        return False

from natural_rag.dataset import RAGDataset
from natural_rag.graph_health import collect_from_backend
from natural_rag.paths import dataset_name_from_path, resolve_run_dirs, sanitize_model_name
from natural_rag.pipelines.wikontic_pipeline import FAILED_ANSWER, IndexUnit, WikonticPipeline
from natural_rag.timing import IndexTimer

# Wikontic's answer prompts live inside the installed package and are not
# parameterised, so short-answer mode is applied by appending an instruction to
# the question text. Keep this in mind when comparing against RAGU, whose
# --short-answers replaces the prompt template itself.
SHORT_ANSWER_SUFFIX = (
    "\n\nAnswer as briefly as possible: output only the direct answer — a single "
    "entity, name, number, date, or a short semicolon-separated list. No "
    "explanations, no full sentences. If the answer is unsupported, output "
    "exactly: I don't know."
)


def report_graph_health(pipeline, collection_prefix: str | None):
    """Measure the finished graph and say so out loud. Never raises.

    Without this the only end-of-run signal is ``failures: 0``, which Wikontic
    prints even after its Qdrant adapter has dropped a collection: exceptions
    raised while a triplet is processed are caught upstream and filed under
    ``filtered_triplets``. A graph with 5% of its entities reachable is
    indistinguishable from a healthy one until someone tries to answer
    questions with it, which is how one shipped.
    """
    if not collection_prefix:
        return None  # unprefixed runs share collections; coverage is not per-run
    try:
        health = collect_from_backend(pipeline.triplets_db, collection_prefix)
    except Exception:
        return None
    if health is None:
        return None

    print(f"\nGraph health ({collection_prefix}):")
    print(f"  entities with an alias : {health.entity_alias_labels}/"
          f"{health.distinct_entities} ({health.entity_coverage:.1%})")
    print(f"  relations with an alias: {health.property_alias_labels}/"
          f"{health.distinct_relations} ({health.property_coverage:.1%})")
    for note in health.warnings():
        print(f"  WARNING: {note}")
    for problem in health.problems():
        print(f"  BROKEN : {problem}")
    return health


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    """Tolerates an empty env var, which the shell scripts can easily produce."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def parse_args() -> argparse.Namespace:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/bl_tiny")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/wikontic")),
        help="Output directory for index and answers.",
    )
    parser.add_argument(
        "--index-model",
        default=os.environ.get("INDEX_MODEL"),
        help="Label of the model that BUILT the graph (e.g. gigachat). "
             "When set, inserted into the index/answers path as a subdirectory.",
    )
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
        "--mode",
        choices=["dynamic", "structured"],
        default=os.environ.get("WIKONTIC_MODE", "dynamic"),
        help="Pipeline mode: dynamic (no ontology) or structured (Wikidata).",
    )
    parser.add_argument(
        "--scope",
        choices=["corpus", "per_sample"],
        default=os.environ.get("WIKONTIC_SCOPE", "corpus"),
        help="Graph scope: corpus-wide, or one graph per question sample.",
    )
    parser.add_argument(
        "--per-sample-docs",
        type=int,
        default=_env_int("WIKONTIC_PER_SAMPLE_DOCS", 20),
        help="Documents per sample in per_sample scope: the gold documents plus "
             "deterministically sampled distractors, matching the ~20 paragraphs "
             "MuSiQue ships per question.",
    )
    parser.add_argument(
        "--limit-docs",
        type=int,
        default=_env_int("LIMIT_DOCS", 0) or None,
        help="Index only the first N documents (smoke tests).",
    )
    parser.add_argument(
        "--limit-questions",
        type=int,
        default=_env_int("LIMIT_QUESTIONS", 0) or None,
        help="Answer only the first N questions.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=_env_int("WIKONTIC_WORKERS", 1),
        help="Concurrent documents during indexing. See build_index() caveats.",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("WIKONTIC_RESUME", True),
        help="Skip documents whose triplets are already in the database.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("WIKONTIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("KEY")
        or os.environ.get("OPENROUTER_KEY"),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("WIKONTIC_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENROUTER_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("WIKONTIC_MODEL")
        or os.environ.get("LLM_MODEL", "gpt-4o"),
    )
    parser.add_argument(
        "--language",
        default=os.environ.get("WIKONTIC_LANGUAGE", "en"),
    )
    parser.add_argument(
        "--hf-model-path",
        default=os.environ.get("HF_MODEL_PATH"),
        help="Local path to facebook/contriever (Wikontic's hardcoded embedder). "
             "Required on offline compute nodes.",
    )
    parser.add_argument(
        "--backend-type",
        choices=["qdrant", "mongo"],
        default=os.environ.get("WIKONTIC_STORAGE_BACKEND", "qdrant"),
    )
    parser.add_argument(
        "--qdrant-url",
        default=os.environ.get("WIKONTIC_QDRANT_URL", ":memory:"),
    )
    parser.add_argument(
        "--qdrant-local-path",
        default=os.environ.get("WIKONTIC_QDRANT_LOCAL_PATH"),
        help="Persist to this directory using qdrant-client's server-less local "
             "mode (no container, no port). Slower: brute-force search.",
    )
    parser.add_argument(
        "--qdrant-timeout",
        type=int,
        default=_env_int("WIKONTIC_QDRANT_TIMEOUT", 120),
        help="Qdrant client timeout, seconds. The qdrant-client default is under "
             "10s, which a networked filesystem exceeds: creating one payload "
             "index there takes ~10s and each collection 1-2s.",
    )
    parser.add_argument(
        "--mongo-uri",
        default=os.environ.get("WIKONTIC_MONGO_URI"),
    )
    parser.add_argument(
        "--triplets-db-name",
        default=os.environ.get("WIKONTIC_TRIPLETS_DB_NAME"),
        help="MongoDB database holding the triplet collections.",
    )
    parser.add_argument(
        "--ontology-db-name",
        default=os.environ.get("WIKONTIC_ONTOLOGY_DB_NAME"),
        help="MongoDB database holding the Wikidata ontology (structured mode).",
    )
    parser.add_argument(
        "--collection-prefix",
        default=os.environ.get("WIKONTIC_COLLECTION_PREFIX"),
        help="Namespace for the triplet collections so several indexes can share "
             "one database / Qdrant instance. Defaults to "
             "<dataset>__<index-model>__<mode>__<scope>.",
    )
    parser.add_argument(
        "--hop-depth",
        type=int,
        default=_env_int("WIKONTIC_HOP_DEPTH", 5),
    )
    parser.add_argument(
        "--use-qualifiers",
        action=argparse.BooleanOptionalAction,
        # True matches the defaults in Wikontic's own qa_eval_* scripts.
        default=_env_flag("WIKONTIC_USE_QUALIFIERS", True),
    )
    parser.add_argument(
        "--use-filtered-triplets",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("WIKONTIC_USE_FILTERED_TRIPLETS", False),
    )
    parser.add_argument(
        "--qa-collapsing",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("WIKONTIC_QA_COLLAPSING", False),
        help="Answer via answer_with_qa_collapsing (question decomposition), the "
             "path used in Wikontic's published evaluation.",
    )
    parser.add_argument(
        "--short-answers",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("SHORT_ANSWERS", False),
        help="Append a terse-answer instruction to each question (see module docstring).",
    )
    parser.add_argument(
        "--normalize-llm-replies",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("WIKONTIC_NORMALIZE_LLM_REPLIES", True),
        help="Accept entity replies wrapped in an object ({\"entities\": [...]}) "
             "instead of the bare JSON array Wikontic's prompts assume. Without "
             "this, models other than gpt-4o-mini fail every question with "
             "'string indices must be integers'. Pass --no-... to measure "
             "Wikontic exactly as shipped.",
    )
    parser.add_argument(
        "--debug-llm",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("WIKONTIC_DEBUG_LLM", False),
        help="Log the parsed shape and value of every Wikontic LLM reply. Use when "
             "answers fail inside Wikontic: its prompts are model-specific and a "
             "reply of the wrong shape surfaces as a bare TypeError.",
    )
    parser.add_argument(
        "--save-context",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("WIKONTIC_SAVE_CONTEXT", True),
        help="Write answers/<i>.context.json with the triplets each answer was "
             "built from. Needed by GraphRAG-Benchmark's faithfulness / "
             "context_relevancy / evidence_recall, and it tells an empty answer "
             "caused by an empty graph apart from one caused by the model.",
    )
    parser.add_argument(
        "--timing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write index_timing.jsonl / index_summary.json.",
    )
    return parser.parse_args()


def sample_id_for(question, index: int) -> str:
    """Stable per-question sample id."""
    return str(question.metadata.get("id") or index)


def build_per_sample_units(dataset: RAGDataset, per_sample_docs: int) -> list[IndexUnit]:
    """One mini-corpus per question: gold documents plus seeded distractors.

    Our musique corpus is a deduplicated pool, so the original 20 paragraphs
    that MuSiQue ships with each question are not recoverable; the gold
    documents are. Filling up to ``per_sample_docs`` with deterministically
    sampled distractors keeps the per-sample graph the same size as the paper's
    instead of handing Wikontic a gold-only corpus with perfect retrieval.
    """
    all_doc_ids = list(dataset.documents)
    units: list[IndexUnit] = []

    for q_idx, question in enumerate(dataset.questions):
        sample_id = sample_id_for(question, q_idx)
        gold_ids = [src.doc_id for src in (question.relevant or [])]
        selected = list(dict.fromkeys(gold_ids))

        if per_sample_docs > len(selected):
            rng = random.Random(f"{sample_id}")
            gold_set = set(selected)
            pool = [doc_id for doc_id in all_doc_ids if doc_id not in gold_set]
            n_extra = min(per_sample_docs - len(selected), len(pool))
            selected.extend(rng.sample(pool, n_extra))

        for idx, doc_id in enumerate(selected):
            doc = dataset.documents.get(doc_id)
            if doc is None or not doc.text:
                continue
            units.append(
                IndexUnit(
                    sample_id=sample_id,
                    source_text_id=str(idx),
                    text=doc.text,
                    doc_id=f"{sample_id}/{doc_id}",
                )
            )
    return units


def run_answers(
    pipeline: WikonticPipeline,
    questions: list,
    answers_dir: Path,
    *,
    scope: str = "corpus",
    qa_collapsing: bool = False,
    short_answers: bool = False,
    save_context: bool = True,
    force: bool = False,
) -> dict[str, int]:
    """Answer ``questions`` into ``answers_dir``/<i>.txt.

    Shared by ``main()`` here and by ``runs_local/answer_from_index.py``, which
    answers from an index exported off the cluster. Both must skip, retry and
    count identically or the two sets of numbers stop being comparable.
    """
    answers_dir.mkdir(parents=True, exist_ok=True)
    n_failed = 0
    n_written = 0
    n_skipped = 0
    collapsing_context_warned = False

    for q_idx, question in enumerate(questions):
        answer_path = answers_dir / f"{q_idx}.txt"
        if answer_path.exists() and not force:
            n_skipped += 1
            continue
        text = question.text + (SHORT_ANSWER_SUFFIX if short_answers else "")
        sample_id = sample_id_for(question, q_idx) if scope == "per_sample" else None
        if qa_collapsing:
            answer, supporting = pipeline.answer_with_collapsing(text, sample_id=sample_id)
        else:
            answer, supporting = pipeline.generate_answer(text, sample_id=sample_id)
        if not answer or answer == FAILED_ANSWER:
            # Do not persist the failure placeholder: it would satisfy the
            # "answer already exists" check above and the question would
            # never be retried. Missing files are counted by
            # judge_answers.py and build_graphrag_bench_input.py instead.
            n_failed += 1
            continue
        answer_path.write_text(answer, encoding="utf-8")
        n_written += 1

        if save_context:
            context = pipeline.format_supporting(supporting)
            if qa_collapsing and not collapsing_context_warned:
                # answer_with_qa_collapsing returns no triplets at all, so the
                # context files would be uniformly empty. Say so once rather
                # than letting retrieval metrics silently read as zero.
                print("NOTE: --qa-collapsing returns no supporting triplets; "
                      "context files will be empty and retrieval metrics "
                      "(evidence_recall / context_relevancy) are not computable "
                      "for this run")
                collapsing_context_warned = True
            (answers_dir / f"{q_idx}.context.json").write_text(
                json.dumps(
                    {"context": context, "n_triplets": len(context)},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    if n_failed:
        print(f"WARNING: {n_failed} question(s) produced no answer; "
              f"no file written, rerun to retry them")
    if pipeline.empty_answers:
        print(f"NOTE: {pipeline.empty_answers} question(s) got an empty answer "
              f"from Wikontic; see 'Empty answer:' lines for whether retrieval "
              f"or the model came up short")
    if pipeline.entity_shape_fixes:
        # Worth reporting: it measures how far this model's replies drift
        # from the shape Wikontic's prompts assume.
        print(f"NOTE: reshaped {pipeline.entity_shape_fixes} entity reply(ies) "
              f"that did not match Wikontic's expected bare-array format")

    return {
        "written": n_written,
        "skipped": n_skipped,
        "failed": n_failed,
        "empty_answers": pipeline.empty_answers,
    }


def default_collection_prefix(args: argparse.Namespace, dataset_name: str) -> str:
    parts = [dataset_name]
    if args.index_model:
        parts.append(sanitize_model_name(args.index_model))
    parts.extend([args.mode, args.scope])
    return "__".join(parts)


def main() -> None:
    args = parse_args()

    if not args.api_key:
        raise ValueError(
            "API key is required. Set WIKONTIC_API_KEY / OPENAI_API_KEY / "
            "KEY / OPENROUTER_KEY or pass --api-key."
        )

    dataset = RAGDataset.load_auto(args.dataset_path)
    dataset_name = dataset_name_from_path(args.dataset_path)

    index_dir, answers_dir, base_dir = resolve_run_dirs(
        args.output_dir, args.dataset_path, args.index_model
    )
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    collection_prefix = args.collection_prefix or default_collection_prefix(args, dataset_name)

    pipeline = WikonticPipeline(
        language=args.language,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        mode=args.mode,
        backend_type=args.backend_type,
        qdrant_url=args.qdrant_url,
        qdrant_local_path=args.qdrant_local_path,
        qdrant_timeout=args.qdrant_timeout,
        mongo_uri=args.mongo_uri,
        triplets_db_name=args.triplets_db_name,
        ontology_db_name=args.ontology_db_name,
        collection_prefix=collection_prefix,
        hop_depth=args.hop_depth,
        use_qualifiers=args.use_qualifiers,
        use_filtered_triplets=args.use_filtered_triplets,
        hf_model_path=args.hf_model_path,
        debug_llm=args.debug_llm,
        normalize_llm_replies=args.normalize_llm_replies,
    )

    if args.build_index:
        if args.scope == "per_sample":
            units = build_per_sample_units(dataset, args.per_sample_docs)
        else:
            units = pipeline.make_units(list(dataset.documents.values()))
        if args.limit_docs:
            units = units[: args.limit_docs]

        timer_cm = (
            IndexTimer(
                base_dir,
                engine="wikontic",
                dataset=dataset_name,
                model=args.index_model or args.model,
                workers=args.workers,
                counter=pipeline.llm_counter,
                total_units=len(units),
                extra={
                    "mode": args.mode,
                    "scope": args.scope,
                    # The pipeline's, not ours: it is sanitized to match the
                    # collections that actually exist, and this value is what
                    # export_index.sh puts in the bundle manifest and what the
                    # preflight on the laptop looks for.
                    "collection_prefix": pipeline.collection_prefix,
                    "backend": args.backend_type,
                },
            )
            if args.timing
            else None
        )
        if timer_cm is None:
            pipeline.build_index(units=units, workers=args.workers, resume=args.resume)
        else:
            with timer_cm as timer:
                pipeline.build_index(
                    units=units,
                    workers=args.workers,
                    resume=args.resume,
                    timer=timer,
                )
                # `extra` is merged into the summary on exit, so set this after
                # indexing: it is the count of documents that finished without
                # error yet stored nothing.
                timer.extra["empty_docs"] = pipeline.empty_docs
                # How far this model's replies drift from the shape Wikontic's
                # prompts assume. Without the adapter each of these would have
                # been a document missing from the graph.
                timer.extra["triplet_shape_fixes"] = pipeline.triplet_shape_fixes
                health = report_graph_health(pipeline, pipeline.collection_prefix)
                if health is not None:
                    timer.extra.update(health.as_summary())

        if pipeline.triplet_shape_fixes:
            print(f"NOTE: reshaped {pipeline.triplet_shape_fixes} triplet-extraction "
                  f"reply(ies) that were not the {{\"triplets\": [...]}} object "
                  f"Wikontic requires; each would otherwise be a document missing "
                  f"from the graph")
        if pipeline.empty_docs:
            print(f"WARNING: {pipeline.empty_docs} document(s) stored no triplets and "
                  f"are NOT in the graph. Rerun with --resume to retry them; "
                  f"see the '⚠ No triplets stored' lines")

    if args.answer:
        questions = dataset.questions
        if args.limit_questions:
            questions = questions[: args.limit_questions]
        run_answers(
            pipeline,
            questions,
            answers_dir,
            scope=args.scope,
            qa_collapsing=args.qa_collapsing,
            short_answers=args.short_answers,
            save_context=args.save_context,
            force=args.force,
        )


if __name__ == "__main__":
    main()
