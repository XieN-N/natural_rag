import asyncio
import json
import os
from pathlib import Path
import sys
from typing import cast, Any

import pandas as pd
from tqdm.auto import tqdm

from ragu.common.logger import logger as ragu_logger
from ragu.models.llm import LLM, CachedAsyncOpenAI, LLMOpenAI

from natural_rag.dataset import RAGDataset
from natural_rag.data import CheckEvaluated


ragu_logger.remove()
ragu_logger.add(sys.stdout, level='DEBUG')


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


async def evaluate_with_llm_as_judge(question: str, reference_answers: list[str], answer: str, llm: LLM) -> CheckEvaluated:
    return cast(CheckEvaluated, await llm.chat_completion(
        [
            {'role': 'system', 'content': judge_system_prompt},
            {'role': 'user', 'content': judge_user_prompt.format(
                question=question,
                reference_answers=reference_answers,
                answer=answer,
            )},
        ],
        output_schema=CheckEvaluated,
    ))


def _read_answers_file(answers_dir: Path, answers_pattern: str) -> dict[str, str]:
    answer_files = sorted(answers_dir.glob(answers_pattern))
    assert len(answer_files) == 1, (
        f'Expected exactly one answers file matching {answers_pattern} in {answers_dir}, '
        f'got {len(answer_files)}'
    )
    json_answers = json.loads(answer_files[0].read_text(encoding='utf-8'))
    assert isinstance(json_answers, list)

    answers_by_question: dict[str, str] = {}
    for item in json_answers:
        assert isinstance(item, dict)

        question_text = item['question']
        assert isinstance(question_text, str)

        rag_answer = item['rag_answer']
        if not isinstance(rag_answer, str):
            if rag_answer is None:
                ragu_logger.warning(f"RAG answer for question {question_text} is None")
            else:
                ragu_logger.error(f"RAG answer for question {question_text} is not a string: {rag_answer} (type {type(rag_answer)})")
            rag_answer = ""

        if question_text in answers_by_question:
            ragu_logger.warning(
                f'Duplicate question in answers file, keeping first occurrence: {question_text}'
            )
            continue
        answers_by_question[question_text] = rag_answer

    return answers_by_question


def run_benchmark_evaluation(dataset_name: str, answers_pattern: str) -> None:
    dataset = RAGDataset.load_jsonl_from_dir(f'datasets/{dataset_name}')
    answers_dir = Path(f'generated/ragu_{dataset_name}/answers')

    ragu_logger.info(f'Loading answers for {dataset_name} from {answers_dir} ({answers_pattern})')
    answers_by_question = _read_answers_file(answers_dir=answers_dir, answers_pattern=answers_pattern)

    answers = {
        question_idx: answers_by_question[question.text]
        for question_idx, question in enumerate(dataset.questions)
        if question.text in answers_by_question
    }

    ragu_logger.info(f'Loaded {len(answers)} matched answers out of {len(dataset.questions)} questions')
    if not answers:
        raise ValueError(f'No matched answers found for dataset={dataset_name}')

    judge_llm = LLMOpenAI(
        client=CachedAsyncOpenAI(
            base_url=os.environ['OPENAI_BASE_URL'],
            api_key=os.environ['OPENAI_API_KEY'],
            rate_min_delay=4,
            rate_max_simultaneous=1,
            retry_times_sec=(2, 2, 2, 2, 2),
            cache='tmp/judge_llm_cache',
            debug_errors_storage='tmp/judge_llm_debug_cache',
        ),
        model_name='gemini-3.1-flash-lite-preview',
    )

    async def process_question(question_idx: int, provided_answer: str) -> tuple[int, CheckEvaluated]:
        try:
            question = dataset.questions[question_idx]
            result = await evaluate_with_llm_as_judge(
                question=question.text,
                reference_answers=question.reference_answers,
                answer=provided_answer,
                llm=judge_llm,
            )
            return question_idx, result
        except Exception as e:
            ragu_logger.exception(f'Failed to evaluate question {question_idx}: {type(e)}; {e}; {e.args}')
            return question_idx, CheckEvaluated(reasoning="", confidence='low', decision=False)

    async def run_evals() -> dict[int, CheckEvaluated]:
        tasks = [
            process_question(question_idx, provided_answer) for question_idx, provided_answer in answers.items()
        ]
        evaluated_tasks: dict[int, CheckEvaluated] = {}
        with tqdm(total=len(tasks), desc=f'LLM judge ({dataset_name})', unit='q') as pbar:
            for task in asyncio.as_completed(tasks):
                question_idx, result = await task
                evaluated_tasks[question_idx] = result
                pbar.update(1)
        return evaluated_tasks

    evaluated = asyncio.run(run_evals())

    evals_dir = answers_dir.parent / 'evals'
    evals_dir.mkdir(exist_ok=True, parents=True)

    rows: list[dict[str, Any]] = []
    for question_idx, answer in answers.items():
        question = dataset.questions[question_idx]
        eval_result = evaluated[question_idx]
        row = {
            'q_idx': question_idx,
            'question': question.text.replace('\n', '\\n'),
            'reference_answers': question.reference_answers,
            'provided_answer': answer.replace('\n', '\\n'),
            'decision': int(eval_result.decision),
            'confidence': eval_result.confidence,
            'reasoning': eval_result.reasoning.replace('\n', '\\n'),
        }
        rows.append(row)

    df = pd.DataFrame(rows).sort_values('q_idx')

    df.to_csv(answers_dir.parent / f'{dataset_name}_evals.csv', index=False)
    ragu_logger.info(
        f'Finished evaluation for {dataset_name}: {df.decision.value_counts()} out of {len(answers)} questions'
    )
