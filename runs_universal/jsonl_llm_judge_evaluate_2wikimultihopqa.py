"""Alias for jsonl_llm_judge_evaluate, kept for callers importing this name.

The variants used to differ in one line: which RAGDataset loader was called.
The canonical module now uses RAGDataset.load_auto, which picks the loader from
the layout of the dataset directory, so there is nothing left to differ in.
"""
from jsonl_llm_judge_evaluate import *  # noqa: F401,F403
from jsonl_llm_judge_evaluate import run_benchmark_evaluation  # noqa: F401
