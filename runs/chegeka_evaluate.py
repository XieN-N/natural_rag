from pathlib import Path

from runs.ragu_evaluate import run_benchmark_evaluation


if __name__ == '__main__':
    run_benchmark_evaluation(
        dataset_name='chegeka',
        answers_dir=Path('generated/ragu_chegeka/answers'),
    )
