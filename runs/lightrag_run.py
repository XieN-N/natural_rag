from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np

from openai import AsyncOpenAI
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from natural_rag.dataset import RAGDataset
from natural_rag.paths import resolve_run_dirs
from natural_rag.pipelines.lightrag_pipelines import LightRAGPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LightRAG on a dataset.")
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path(os.environ.get("DATASET_PATH", "datasets/multiq")),
        help="Path to dataset directory or file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OUTPUT_DIR", "generated/lightrag")),
        help="Output directory for index and answers.",
    )
    parser.add_argument(
        "--index-model",
        default=os.environ.get("INDEX_MODEL"),
        help="Label of the model that BUILT the graph (e.g. gpt-oss-20b). "
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
        "--query-mode",
        default=os.environ.get("QUERY_MODE", "naive"),
    )
    parser.add_argument(
        "--short-answers",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("SHORT_ANSWERS", "").lower() in ("1", "true", "yes"),
        help="Use a brief answer style (for short-answer benchmarks).",
    )
    parser.add_argument(
        "--llm-cache",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("LLM_CACHE", "true").lower() in ("1", "true", "yes"),
        help="Use LightRAG's LLM response cache (default ON). Pass "
             "--no-llm-cache to force fresh regeneration if a stale response "
             "cache is present in the index.",
    )
    parser.add_argument(
        "--max-parallel-insert",
        type=int,
        default=int(os.environ.get("MAX_PARALLEL_INSERT", "16")),
    )
    parser.add_argument(
        "--openai-base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--openai-api-key",
        default=os.environ.get("OPENAI_API_KEY"),
    )
    parser.add_argument(
        "--embed-base-url",
        default=os.environ.get("EMBED_BASE_URL"),
    )
    parser.add_argument(
        "--llm-model",
        default=os.environ.get("LLM_MODEL", "openai/gpt-4o-mini"),
    )
    parser.add_argument(
        "--embed-model",
        default=os.environ.get("EMBED_MODEL", "emb-openai/text-embedding-3-small"),
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=int(os.environ.get("EMBEDDING_DIM", "1536")),
    )
    return parser.parse_args()


async def embedding_func(texts: list[str], args: argparse.Namespace) -> np.ndarray:
    client = AsyncOpenAI(
        base_url=args.embed_base_url or args.openai_base_url,
        api_key=args.openai_api_key,
    )
    response = await client.embeddings.create(
        input=texts,
        model=args.embed_model,
    )
    return np.array([item.embedding for item in response.data])


async def llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    **kwargs,
) -> str:
    return await openai_complete_if_cache(
        args.llm_model,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        api_key=args.openai_api_key,
        base_url=args.openai_base_url,
        **kwargs,
    )


def main() -> None:
    global args
    args = parse_args()
    
    if not args.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required")

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

    index_dir, answers_dir, _ = resolve_run_dirs(
        args.output_dir, args.dataset_path, args.index_model
    )
    index_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    pipeline = LightRAGPipeline(
        working_dir=index_dir,
        llm_model_func=lambda prompt, system_prompt=None, history_messages=None, **kwargs: llm_func(
            prompt, system_prompt, history_messages, **kwargs
        ),
        embedding_func=EmbeddingFunc(
            embedding_dim=args.embedding_dim,
            max_token_size=8192,
            func=lambda texts: embedding_func(texts, args),
        ),
        query_mode=args.query_mode,
        max_parallel_insert=args.max_parallel_insert,
        short_answers=args.short_answers,
        enable_llm_cache=args.llm_cache,
    )

    if args.build_index:
        pipeline.build_index(documents=list(dataset.documents.values()))

    if args.answer:
        for q_idx, question in enumerate(dataset.questions):
            answer_path = answers_dir / f'{q_idx}.txt'
            if not answer_path.exists() or args.force:
                answer, _ = pipeline.generate_answer(question.text)
                answer_path.write_text(answer)

    pipeline.close()


if __name__ == "__main__":
    main()