import asyncio
import os
from pathlib import Path
import sys
from typing import cast, Any

import yaml

import pandas as pd

from natural_rag.dashboard import run_dashboard
from natural_rag.data import ChecklistEvaluated, LLMJudgeEvalChecklist, Question, RAGAnswerAndEvals
from natural_rag.dataset import RAGDataset



dataset_name = 'bl_medium'

dataset = RAGDataset.load_from_dir(f'datasets/{dataset_name}')

evals_dir = Path(f'generated/ragu_{dataset_name}/evals')

evals = {
    int(path.stem): RAGAnswerAndEvals.model_validate(yaml.safe_load(path.read_text()))
    for path in evals_dir.glob('*.yaml')
}

run_dashboard(dataset, {'ragu': evals})