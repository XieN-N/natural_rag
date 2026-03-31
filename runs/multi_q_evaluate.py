from jsonl_llm_judge_evaluate import run_benchmark_evaluation


if __name__ == '__main__':
    run_benchmark_evaluation(dataset_name='multiq', answers_pattern='multi_q_*.json')
