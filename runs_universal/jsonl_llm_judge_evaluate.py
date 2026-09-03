import asyncio
import json
import os
import logging
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

async def evaluate_with_llm_as_judge(question: str, reference_answers: list[str], answer: str, client: AsyncOpenAI, model_name: str) -> CheckEvaluated:
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
        return CheckEvaluated(reasoning="parsing error", confidence="low", decision=False)

def _read_answers_file(answers_dir: Path, answers_pattern: str) -> dict[str, str]:
    answer_files = sorted(answers_dir.glob(answers_pattern))
    if len(answer_files) != 1:
        raise FileNotFoundError(f"Found {len(answer_files)} files matching {answers_pattern} in {answers_dir}, expected 1")
    with open(answer_files[0], 'r', encoding='utf-8') as f:
        json_answers = json.load(f)
    assert isinstance(json_answers, list)
    answers_by_question: dict[str, str] = {}
    for item in json_answers:
        question_text = item['question']
        rag_answer = item.get('rag_answer', '')
        if not isinstance(rag_answer, str):
            rag_answer = str(rag_answer) if rag_answer else ''
        answers_by_question[question_text] = rag_answer
    return answers_by_question

def run_benchmark_evaluation(dataset_name: str, answers_pattern: str) -> None:
    dataset = RAGDataset.load_auto(f'datasets/{dataset_name}')
    answers_dir = Path(os.environ.get('ANSWERS_DIR', f'generated/fast_graphrag_{dataset_name}/answers'))
    logger.info(f'Loading answers for {dataset_name} from {answers_dir} ({answers_pattern})')
    answers_by_question = _read_answers_file(answers_dir=answers_dir, answers_pattern=answers_pattern)
    answers = {}
    for idx, q in enumerate(dataset.questions):
        if q.text in answers_by_question:
            answers[idx] = answers_by_question[q.text]
    logger.info(f'Matched {len(answers)} out of {len(dataset.questions)} questions')
    if not answers:
        raise ValueError("No answers matched")

    client = AsyncOpenAI(
        base_url=os.environ['OPENAI_BASE_URL'],
        api_key=os.environ['OPENAI_API_KEY'],
    )
    model_name = os.environ.get('JUDGE_MODEL_NAME', 'Qwen2.5-14B-Instruct')

    async def process_question(idx: int, ans: str) -> tuple[int, CheckEvaluated]:
        q = dataset.questions[idx]
        res = await evaluate_with_llm_as_judge(q.text, q.reference_answers, ans, client, model_name)
        return idx, res

    async def run_evals():
        tasks = [process_question(idx, ans) for idx, ans in answers.items()]
        results = {}
        with tqdm(total=len(tasks), desc='LLM judge', unit='q') as pbar:
            for coro in asyncio.as_completed(tasks):
                idx, ev = await coro
                results[idx] = ev
                pbar.update(1)
        return results

    evaluated = asyncio.run(run_evals())

    evals_dir = answers_dir.parent / 'evals'
    evals_dir.mkdir(exist_ok=True, parents=True)
    rows = []
    for idx, ans in answers.items():
        q = dataset.questions[idx]
        ev = evaluated[idx]
        rows.append({
            'q_idx': idx,
            'question': q.text.replace('\n', '\\n'),
            'reference_answers': q.reference_answers,
            'provided_answer': ans.replace('\n', '\\n'),
            'decision': int(ev.decision),
            'confidence': ev.confidence,
            'reasoning': ev.reasoning.replace('\n', '\\n'),
        })
    df = pd.DataFrame(rows).sort_values('q_idx')
    csv_path = answers_dir.parent / f'{dataset_name}_evals.csv'
    df.to_csv(csv_path, index=False)
    logger.info(f'Evaluation saved to {csv_path} – true: {df.decision.sum()}, false: {(df.decision == 0).sum()}')