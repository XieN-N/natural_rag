import asyncio
import os
from pathlib import Path
import sys
from typing import cast, Any

from ragu.models.llm import LLM, CachedAsyncOpenAI, LLMOpenAI
import pandas as pd

from natural_rag.data import ChecklistEvaluated, LLMJudgeEvalChecklist, Question
from natural_rag.dataset import RAGDataset


from ragu.common.logger import logger as ragu_logger
ragu_logger.remove()
ragu_logger.add(sys.stdout, level="DEBUG")


judge_system_prompt = f"""\
You need to serve as LLM judge and evaluate assistant's answer. \
I will provide evaluation guideline, question and answer.

To decompose evaluation, guideline for each question contains \
a checklist: what should or should not be mentioned in \
the answer. There is also a gold answer, but you should \
avoid comparing them directly, but rather use a checklist.

The checklist schema: {LLMJudgeEvalChecklist.model_json_schema()}
"""


judge_user_prompt = f"""\
Question: {{question}}

Answer to evaluate: {{answer}}

Gold answer(s): {{reference}}

Now that you have both question and answer, I provide a concrete checklist:

{{checklist}}

Finally, I repeat the answer to evaluate: {{answer}}
"""

async def evaluate_with_llm_as_judge(question: Question, answer: str, llm: LLM) -> ChecklistEvaluated:
    assert question.eval_rules
    question.eval_rules.model_dump_json
    
    return cast(ChecklistEvaluated, await llm.chat_completion(
        [
            {"role": "system", "content": judge_system_prompt},
            {"role": "user", "content": judge_user_prompt.format(
                question=question.text,
                answer=answer,
                reference=str(question.reference_answers),
                checklist=question.eval_rules.model_dump_json(),
            )},
        ],
        output_schema=ChecklistEvaluated,
    ))

dataset_name = 'bl_tiny'

dataset = RAGDataset.load_from_dir(f'datasets/{dataset_name}')

answers_dir = Path(f'generated/ragu_{dataset_name}/answers')


judge_llm = LLMOpenAI(
    client = CachedAsyncOpenAI(
        base_url=os.environ['OPENAI_BASE_URL'],
        api_key=os.environ['OPENAI_API_KEY'],
        rate_min_delay=2,
        rate_max_simultaneous=10,
        retry_times_sec=(2, 2, 2, 2, 2),
        cache='tmp/judge_llm_cache',
        debug_errors_storage='tmp/judge_llm_debug_cache',
    ),
    model_name='google/gemini-3.1-flash-lite-pre',
)

answers = {
    int(path.stem): path.read_text()
    for path in answers_dir.glob('*.txt')
}

async def run_evals() -> list[ChecklistEvaluated]:
    return await asyncio.gather(*[
        evaluate_with_llm_as_judge(
            question=dataset.questions[question_idx],
            answer=answer,
            llm=judge_llm,
        )
        for question_idx, answer in answers.items()
    ])

evaluated = dict(zip(answers, asyncio.run(run_evals())))


df_rows: list[dict[str, Any]] = []

for question_idx, answer in answers.items():
    question = dataset.questions[question_idx]
    evaluation = evaluated[question_idx]
    assert question.eval_rules

    keys = set(question.eval_rules.checks.keys()) | set(evaluation.checks.keys())
    for key in keys:
        df_rows.append(row := {
            'q_idx': question_idx,
            'question': question.text.replace('\n', '\\n'),
            'answer': answer.replace('\n', '\\n'),
            'chk_idx': key,
        })
        if (check := question.eval_rules.checks.get(key, None)) is not None:
            row |= check
            if check.score < 0:
                row['check_type'] = 'penalty'
            elif check.score == 0:
                row['check_type'] = 'ignore'
            else:
                row['check_type'] = 'reward'
        if (check_eval := evaluation.checks.get(key, None)) is not None:
            row |= check_eval

df = pd.DataFrame(df_rows)


summary_df_rows: list[dict[str, Any]] = []

for (q_idx, question, answer), group in df.groupby(['q_idx', 'question', 'answer']):
    max_score = sum([x for x in group['score'] if x > 0])
    actual_score = group['score'][group['decision']].sum()
    score_ratio = actual_score / max_score
    summary_df_rows.append({
        'q_idx': q_idx,
        'score_ratio': score_ratio,
        'max_score': max_score,
        'actual_score': actual_score,
        'question': question,
        'answer': answer,
    })

summary_df = pd.DataFrame(summary_df_rows)


df.to_csv(answers_dir.parent / 'evals.csv', index=False)
summary_df.to_csv(answers_dir.parent / 'evals_summary.csv', index=False)