import os
from jsonl_llm_judge_evaluate import run_benchmark_evaluation

if __name__ == '__main__':
    dataset_name = os.environ['DATASET_NAME']
    answers_pattern = os.environ.get('ANSWERS_PATTERN', f'{dataset_name}_*.json')
    run_benchmark_evaluation(dataset_name=dataset_name, answers_pattern=answers_pattern)