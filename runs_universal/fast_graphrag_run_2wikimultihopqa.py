"""Alias for fast_graphrag_run.py, kept because the sbatch scripts call this name.

The variants used to differ in which RAGDataset loader was called and in two
embedder guards that existed only in the _bl copy. The canonical script now
uses RAGDataset.load_auto and carries both guards, so there is nothing left to
differ in.
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("fast_graphrag_run.py")), run_name="__main__")
