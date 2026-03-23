from pathlib import Path

from runs.ragu_evaluate import run_benchmark_evaluation


if __name__ == '__main__':
    run_benchmark_evaluation(
        dataset_name='multi_q',
        answers_dir=Path('generated/ragu_multi_q/answers'),
    )
