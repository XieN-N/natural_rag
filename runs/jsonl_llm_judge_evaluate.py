import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Literal, cast, Any

import pandas as pd
from pydantic import BaseModel
from tqdm.auto import tqdm
import yaml

from ragu.common.logger import logger as ragu_logger
from ragu.models.llm import LLM, CachedAsyncOpenAI, LLMOpenAI

from natural_rag.dataset import RAGDataset


ragu_logger.remove()
ragu_logger.add(sys.stdout, level='DEBUG')


class CorrectnessJudgement(BaseModel):
    reasoning: str
    score: Literal[0, 0.5, 1]


judge_system_prompt = """\
You are an expert evaluator for QA correctness.

Task:
- Evaluate only factual correctness of assistant answer against the reference answer(s).
- Use score scale exactly: 0, 0.5, 1.
- Return valid JSON only, matching schema with fields in this order:
  1) reasoning
  2) score

Scoring rubric:
- 1 (Correct): same factual information as reference.
- 0.5 (Partial): partially correct or too broad but includes correct target fact.
- 0 (Incorrect): wrong, contradicts reference, or answer is "I don't know"/equivalent.

Few-shot examples:
Example 1:
Question: "Кто написал роман 'Преступление и наказание'?"
Reference answers: ["Фёдор Достоевский", "Достоевский"]
Assistant answer: "Автор — Фёдор Михайлович Достоевский."
Output: {"reasoning":"Ответ полностью совпадает по факту с эталоном.","score":1}

Example 2:
Question: "Назови два крупнейших города Казахстана."
Reference answers: ["Алматы и Астана"]
Assistant answer: "Алматы."
Output: {"reasoning":"Назван только один из двух требуемых городов, факт частично покрыт.","score":0.5}

Example 3:
Question: "Кто открыл пенициллин?"
Reference answers: ["Александр Флеминг", "Флеминг"]
Assistant answer: "Я не знаю."
Output: {"reasoning":"Ответ не содержит факта и явно указывает на незнание.","score":0}
"""


judge_user_prompt = """\
Question: {question}

Reference answers: {reference_answers}

Assistant answer: {answer}

First provide concise reasoning, then assign one score from [0, 0.5, 1].
"""


async def evaluate_with_llm_as_judge(question: str, reference_answers: list[str], answer: str, llm: LLM) -> CorrectnessJudgement:
    return cast(CorrectnessJudgement, await llm.chat_completion(
        [
            {'role': 'system', 'content': judge_system_prompt},
            {'role': 'user', 'content': judge_user_prompt.format(
                question=question,
                reference_answers=reference_answers,
                answer=answer,
            )},
        ],
        output_schema=CorrectnessJudgement,
    ))


def _read_answers_file(answers_dir: Path, answers_pattern: str) -> dict[str, str]:
    answer_files = sorted(answers_dir.glob(answers_pattern))
    assert len(answer_files) == 1, (
        f'Expected exactly one answers file matching {answers_pattern} in {answers_dir}, '
        f'got {len(answer_files)}'
    )
    json_answers = json.loads(answer_files[0].read_text())
    assert isinstance(json_answers, list)

    answers_by_question: dict[str, str] = {}
    for item in json_answers:
        assert isinstance(item, dict)
        question_text = item['question']
        rag_answer = item['rag_answer']
        assert isinstance(question_text, str)
        assert isinstance(rag_answer, str)
        answers_by_question.setdefault(question_text, rag_answer)

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
        model_name='google/gemini-3.1-flash-lite-preview',
    )

    async def run_evals() -> dict[int, CorrectnessJudgement]:
        tasks = {
            asyncio.create_task(evaluate_with_llm_as_judge(
                question=dataset.questions[question_idx].text,
                reference_answers=dataset.questions[question_idx].reference_answers,
                answer=answer,
                llm=judge_llm,
            )): question_idx
            for question_idx, answer in answers.items()
        }
        evaluated: dict[int, CorrectnessJudgement] = {}
        with tqdm(total=len(tasks), desc=f'LLM judge ({dataset_name})', unit='q') as pbar:
            for task in asyncio.as_completed(tasks):
                question_idx = tasks[task]
                evaluated[question_idx] = await task
                pbar.update(1)
        return evaluated

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
            'answer': answer.replace('\n', '\\n'),
            'score': float(eval_result.score),
            'reasoning': eval_result.reasoning.replace('\n', '\\n'),
        }
        rows.append(row)
        (evals_dir / f'{question_idx}.yaml').write_text(yaml.dump(row, allow_unicode=True))

    df = pd.DataFrame(rows).sort_values('q_idx')
    summary_df = pd.DataFrame([{
        'dataset': dataset_name,
        'evaluated_answers': len(df),
        'avg_score': float(df['score'].mean()),
        'score_1_ratio': float((df['score'] == 1.0).mean()),
        'score_05_ratio': float((df['score'] == 0.5).mean()),
        'score_0_ratio': float((df['score'] == 0.0).mean()),
    }])

    df.to_csv(answers_dir.parent / 'evals.csv', index=False)
    summary_df.to_csv(answers_dir.parent / 'evals_summary.csv', index=False)
    ragu_logger.info(
        f'Finished evaluation for {dataset_name}: avg_score={summary_df.iloc[0]["avg_score"]:.3f}'
    )
