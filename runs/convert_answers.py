"""Consolidate per-question answer files into a single JSON.

Engines write answers as ``answers/<q_idx>.txt`` (one file per question,
resume-friendly). This script joins them with the dataset questions and writes
``<answers-dir>/<dataset_name>_answers.json`` — the format consumed by
``runs/jsonl_llm_judge_evaluate.py``.

Usage::

    python runs/convert_answers.py --dataset-name musique \\
        --answers-dir generated/lightrag_musique/musique/answers

Environment fallbacks: DATASET_NAME, ANSWERS_DIR, ANSWERS_JSON_FILE
(and RAG_ENGINE for the default answers dir), so sbatch scripts that only
export env vars keep working.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from natural_rag.dataset import RAGDataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidate <q_idx>.txt answers into one JSON.")
    parser.add_argument(
        "--dataset-name",
        default=os.environ.get("DATASET_NAME"),
        help="Dataset folder name under datasets/ (env: DATASET_NAME).",
    )
    parser.add_argument(
        "--answers-dir",
        type=Path,
        default=None,
        help="Directory with <q_idx>.txt answers "
             "(env: ANSWERS_DIR; default generated/<RAG_ENGINE|ragu>_<dataset>/answers).",
    )
    parser.add_argument(
        "--answers-json-file",
        default=None,
        help="Output file name (env: ANSWERS_JSON_FILE; default <dataset>_answers.json).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dataset_name:
        raise SystemExit("--dataset-name is required (or set DATASET_NAME)")
    if args.answers_dir is None:
        args.answers_dir = Path(os.environ.get("ANSWERS_DIR", ""))
        if not str(args.answers_dir):
            engine = os.environ.get("RAG_ENGINE", "ragu")
            args.answers_dir = Path(f"generated/{engine}_{args.dataset_name}") / "answers"
    answers_json_file = args.answers_json_file or os.environ.get(
        "ANSWERS_JSON_FILE", f"{args.dataset_name}_answers.json"
    )

    dataset = RAGDataset.load_auto(f"datasets/{args.dataset_name}")

    answers_json = []
    for q_idx, question in enumerate(dataset.questions):
        answer_path = args.answers_dir / f"{q_idx}.txt"
        if answer_path.exists():
            answers_json.append({
                "question": question.text,
                "rag_answer": answer_path.read_text(encoding="utf-8"),
            })
        else:
            print(f"Warning: answer for question {q_idx} not found")

    json_path = args.answers_dir / answers_json_file
    json_path.write_text(
        json.dumps(answers_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved {len(answers_json)} answers to {json_path}")


if __name__ == "__main__":
    main()
