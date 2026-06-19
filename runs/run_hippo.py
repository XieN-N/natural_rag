from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from natural_rag.dataset import RAGDataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a HippoRAG 2 index and generate answers.",
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path("datasets/2wikimultihopqa/2wikimultihopqa.json"),
    )
    parser.add_argument(
        "--dataset-format",
        choices=["auto", "2wikimultihopqa-json", "jsonl-dir"],
        default="auto",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated/hipporag_2wikimultihopqa"),
    )
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--answers-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)

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
        "--force-index-from-scratch",
        action=argparse.BooleanOptionalAction,
        default=False,
    )

    parser.add_argument(
        "--builder-model-name",
        "--llm-model-name",
        dest="builder_model_name",
        default="gpt-4o-mini",
    )
    parser.add_argument("--assistant-model-name", default=None)
    parser.add_argument("--embedding-model-name", default="text-embedding-3-small")
    parser.add_argument(
        "--openai-base-url",
        "--llm-base-url",
        dest="openai_base_url",
        default="https://api.openai.com/v1",
    )
    parser.add_argument("--openai-api-key", default=None)
    parser.add_argument("--openai-rate-min-delay", type=float, default=None)
    parser.add_argument("--openai-rate-max-simultaneous", type=int, default=None)
    parser.add_argument("--embedding-base-url", default=None)
    parser.add_argument("--embedding-api-key", default=None)
    parser.add_argument("--embedding-rate-min-delay", type=float, default=None)
    parser.add_argument("--embedding-rate-max-simultaneous", type=int, default=None)
    parser.add_argument("--embedding-dim", type=int, default=None)
    parser.add_argument("--retrieval-top-k", type=int, default=200)
    parser.add_argument("--qa-top-k", type=int, default=5)

    args = parser.parse_args()
    args.index_dir = args.index_dir or args.output_dir / "index"
    args.answers_dir = args.answers_dir or args.output_dir / "answers"
    args.embedding_base_url = args.embedding_base_url or args.openai_base_url
    args.assistant_model_name = args.assistant_model_name or args.builder_model_name
    return args


def build_pipeline(args: argparse.Namespace):
    from natural_rag.pipelines.hipporag_pipelines import HippoRAGPipeline

    api_key = args.openai_api_key or args.embedding_api_key
    if not api_key:
        raise ValueError("--openai-api-key is required when building a HippoRAG pipeline")
    os.environ["OPENAI_API_KEY"] = api_key

    return HippoRAGPipeline(
        save_dir=args.index_dir,
        llm_model_name=args.builder_model_name,
        llm_base_url=args.openai_base_url,
        embedding_model_name=args.embedding_model_name,
        embedding_base_url=args.embedding_base_url,
        retrieval_top_k=args.retrieval_top_k,
        qa_top_k=args.qa_top_k,
        force_index_from_scratch=args.force_index_from_scratch,
    )


def load_dataset(args: argparse.Namespace) -> RAGDataset:
    dataset = RAGDataset.load_auto(args.dataset_path)
    if args.limit is not None:
        dataset = RAGDataset(
            documents=dataset.documents,
            questions=dataset.questions[:args.limit],
        )
    return dataset


def write_answers(
    dataset: RAGDataset,
    pipeline,
    args: argparse.Namespace,
) -> None:
    for q_idx, question in enumerate(dataset.questions):
        answer_path = args.answers_dir / f"{q_idx}.txt"
        if answer_path.exists() and not args.force:
            continue

        answer, _ = pipeline.generate_answer(question.text)
        answer_path.write_text(str(answer), encoding="utf-8")
        print(f"{q_idx + 1}/{len(dataset.questions)}")


def main() -> None:
    args = parse_args()
    dataset = load_dataset(args)
    args.index_dir.mkdir(parents=True, exist_ok=True)
    args.answers_dir.mkdir(parents=True, exist_ok=True)

    if not args.build_index and not args.answer:
        print(
            f"Loaded {len(dataset.documents)} documents and "
            f"{len(dataset.questions)} questions"
        )
        return

    pipeline = build_pipeline(args)
    if args.build_index:
        pipeline.build_index(documents=list(dataset.documents.values()))
    if args.answer:
        write_answers(dataset=dataset, pipeline=pipeline, args=args)


if __name__ == "__main__":
    main()
