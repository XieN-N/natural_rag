"""Alias for convert_answers.py, kept because the sbatch scripts call this name.

The variants used to differ in one line: which RAGDataset loader was called.
convert_answers.py now uses RAGDataset.load_auto, which picks the loader from the layout
of the dataset directory, so there is nothing left to differ in.
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("convert_answers.py")), run_name="__main__")
