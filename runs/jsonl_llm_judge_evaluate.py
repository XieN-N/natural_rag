"""LLM-as-judge evaluation of RAG answers (factual correctness).

Works with any engine's output: reads a consolidated answers JSON (as produced
by ``runs/convert_answers.py``), matches answers to the dataset questions and
asks a judge LLM for a boolean decision with confidence and reasoning. Results
are written to ``<answers-dir>/../<dataset_name>_evals.csv``.

Usage (CLI)::

    python runs/jsonl_llm_judge_evaluate.py \\
        --dataset-name musique \\
        --answers-dir generated/lightrag_musique/musique/answers \\
        --judge-model Qwen2.5-14B-Instruct

Every CLI flag has an environment fallback (DATASET_NAME, ANSWERS_DIR,
ANSWERS_PATTERN, RAG_ENGINE, JUDGE_MODEL_NAME, OPENAI_BASE_URL,
OPENAI_API_KEY), so existing sbatch scripts that only export env vars keep
working.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
from openai import AsyncOpenAI
from tqdm.auto import tqdm

from natural_rag.dataset import RAGDataset
from natural_rag.data import CheckEvaluated

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

judge_system_prompt = """\
You are an expert evaluator for QA correctness.

Task:
- Evaluate only factual correctness of assistant answer against the reference answer(s).
- Use boolean decision (true/false) to indicate if the answer is correct enough.
- Provide confidence as one of: low, moderate, high.
- Return valid JSON only, matching schema with fields in this order:
  1) reasoning
  2) confidence
  3) decision

Decision rubric:
- decision = true: answer matches the reference fact(s) without factual errors.
- decision = false: answer is wrong, contradicts reference, or is incomplete/too broad.

Confidence rubric:
- high: reference is clear and answer clearly matches (or clearly contradicts).
- moderate: minor ambiguity or partial coverage but still clearly correct/incorrect.
- low: reference or answer is ambiguous, underspecified, or hard to judge.

Few-shot examples:
Example 1:
Question: "Кто написал роман 'Преступление и наказание'?"
Reference answers: ["Фёдор Достоевский", "Достоевский"]
Assistant answer: "Автор — Фёдор Михайлович Достоевский."
Output: {"reasoning":"Факт совпадает с эталоном.","confidence":"high","decision":true}

Example 2:
Question: "Назови два крупнейших города Казахстана."
Reference answers: ["Алматы и Астана"]
Assistant answer: "Алматы."
Output: {"reasoning":"Назван только один из двух требуемых городов, ответ неполный.","confidence":"moderate","decision":false}

Example 3:
Question: "Кто открыл пенициллин?"
Reference answers: ["Александр Флеминг", "Флеминг"]
Assistant answer: "Я не знаю."
Output: {"reasoning":"Ответ не содержит факта и указывает на незнание.","confidence":"high","decision":false}
"""

judge_user_prompt = """\
Question: {question}

Reference answers: {reference_answers}

Assistant answer: {answer}

First provide concise reasoning, then assign confidence and decision.
"""


async def evaluate_with_llm_as_judge(
    question: str,
    reference_answers: list[str],
    answer: str,
    client: AsyncOpenAI,
    model_name: str,
) -> CheckEvaluated:
    prompt = judge_user_prompt.format(
        question=question,
        reference_answers=reference_answers,
        answer=answer,
    )
    messages = [
        {"role": "system", "content": judge_system_prompt},
        {"role": "user", "content": prompt},
    ]
    try:
        completion = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content.strip()
        data = json.loads(raw)
        return CheckEvaluated(
            reasoning=data.get("reasoning", ""),
            confidence=data.get("confidence", "low"),
            decision=data.get("decision", False),
        )
    except Exception:
        logger.exception("Judge call failed for question: %s", question[:80])
        return CheckEvaluated(reasoning="parsing error", confidence="low", decision=False)


def _read_answers_file(answers_dir: Path, answers_pattern: str) -> dict[str, str]:
    answer_files = sorted(answers_dir.glob(answers_pattern))
    if len(answer_files) != 1:
        raise FileNotFoundError(
            f"Found {len(answer_files)} files matching {answers_pattern} in {answers_dir}, expected 1"
        )
    json_answers = json.loads(answer_files[0].read_text(encoding="utf-8"))
    if not isinstance(json_answers, list):
        raise ValueError(f"Answers file must contain a JSON list: {answer_files[0]}")

    answers_by_question: dict[str, str] = {}
    for item in json_answers:
        if not isinstance(item, dict):
            continue
        question_text = item["question"]
        rag_answer = item.get("rag_answer", "")
        if not isinstance(rag_answer, str):
            if rag_answer is None:
                logger.warning("RAG answer for question %s is None", question_text)
            else:
                logger.error(
                    "RAG answer for question %s is not a string: %r (type %s)",
                    question_text, rag_answer, type(rag_answer),
                )
            rag_answer = ""
        if question_text in answers_by_question:
            logger.warning("Duplicate question in answers file, keeping first occurrence: %s", question_text)
            continue
        answers_by_question[question_text] = rag_answer
    return answers_by_question


def run_benchmark_evaluation(
    dataset_name: str,
    answers_pattern: str | None = None,
    answers_dir: str | Path | None = None,
    judge_model: str | None = None,
    judge_base_url: str | None = None,
    judge_api_key: str | None = None,
) -> None:
    """Evaluate answers of one dataset; see module docstring for defaults."""
    answers_pattern = answers_pattern or f"{dataset_name}_*.json"
    if answers_dir is None:
        answers_dir = os.environ.get("ANSWERS_DIR")
    if answers_dir is None:
        engine = os.environ.get("RAG_ENGINE", "ragu")
        answers_dir = Path(f"generated/{engine}_{dataset_name}") / "answers"
    answers_dir = Path(answers_dir)

    dataset = RAGDataset.load_auto(f"datasets/{dataset_name}")
    logger.info("Loading answers for %s from %s (%s)", dataset_name, answers_dir, answers_pattern)
    answers_by_question = _read_answers_file(answers_dir=answers_dir, answers_pattern=answers_pattern)

    answers = {
        question_idx: answers_by_question[question.text]
        for question_idx, question in enumerate(dataset.questions)
        if question.text in answers_by_question
    }
    logger.info("Matched %d out of %d questions", len(answers), len(dataset.questions))
    if not answers:
        raise ValueError(f"No matched answers found for dataset={dataset_name}")

    client = AsyncOpenAI(
        base_url=judge_base_url or os.environ["OPENAI_BASE_URL"],
        api_key=judge_api_key or os.environ["OPENAI_API_KEY"],
    )
    model_name = judge_model or os.environ.get("JUDGE_MODEL_NAME", "Qwen2.5-14B-Instruct")

    async def process_question(idx: int, ans: str) -> tuple[int, CheckEvaluated]:
        q = dataset.questions[idx]
        res = await evaluate_with_llm_as_judge(q.text, q.reference_answers, ans, client, model_name)
        return idx, res

    async def run_evals() -> dict[int, CheckEvaluated]:
        tasks = [process_question(idx, ans) for idx, ans in answers.items()]
        results: dict[int, CheckEvaluated] = {}
        with tqdm(total=len(tasks), desc=f"LLM judge ({dataset_name})", unit="q") as pbar:
            for coro in asyncio.as_completed(tasks):
                idx, ev = await coro
                results[idx] = ev
                pbar.update(1)
        return results

    evaluated = asyncio.run(run_evals())

    evals_dir = answers_dir.parent / "evals"
    evals_dir.mkdir(exist_ok=True, parents=True)
    rows: list[dict[str, Any]] = []
    for idx, ans in answers.items():
        q = dataset.questions[idx]
        ev = evaluated[idx]
        rows.append({
            "q_idx": idx,
            "question": q.text.replace("\n", "\\n"),
            "reference_answers": q.reference_answers,
            "provided_answer": ans.replace("\n", "\\n"),
            "decision": int(ev.decision),
            "confidence": ev.confidence,
            "reasoning": ev.reasoning.replace("\n", "\\n"),
        })
    df = pd.DataFrame(rows).sort_values("q_idx")
    csv_path = answers_dir.parent / f"{dataset_name}_evals.csv"
    df.to_csv(csv_path, index=False)
    logger.info(
        "Evaluation saved to %s – true: %d, false: %d",
        csv_path, df.decision.sum(), int((df.decision == 0).sum()),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-as-judge evaluation of RAG answers.")
    parser.add_argument(
        "--dataset-name",
        default=os.environ.get("DATASET_NAME"),
        help="Dataset folder name under datasets/ (env: DATASET_NAME).",
    )
    parser.add_argument(
        "--answers-dir",
        type=Path,
        default=None,
        help="Directory with the consolidated answers JSON "
             "(env: ANSWERS_DIR; default generated/<RAG_ENGINE|ragu>_<dataset>/answers).",
    )
    parser.add_argument(
        "--answers-pattern",
        default=None,
        help=f"Glob for the answers file (default <dataset>_*.json).",
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("JUDGE_MODEL_NAME", "Qwen2.5-14B-Instruct"),
        help="Judge model name (env: JUDGE_MODEL_NAME).",
    )
    parser.add_argument(
        "--judge-base-url",
        default=os.environ.get("OPENAI_BASE_URL"),
        help="OpenAI-compatible base URL of the judge (env: OPENAI_BASE_URL).",
    )
    parser.add_argument(
        "--judge-api-key",
        default=os.environ.get("OPENAI_API_KEY"),
        help="API key for the judge endpoint (env: OPENAI_API_KEY).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dataset_name:
        raise SystemExit("--dataset-name is required (or set DATASET_NAME)")
    run_benchmark_evaluation(
        dataset_name=args.dataset_name,
        answers_pattern=args.answers_pattern,
        answers_dir=args.answers_dir,
        judge_model=args.judge_model,
        judge_base_url=args.judge_base_url,
        judge_api_key=args.judge_api_key,
    )


if __name__ == "__main__":
    main()
