from abc import ABC
from pathlib import Path
from typing import Any

from natural_rag.data import Document
from natural_rag.dataset import RAGDataset


class RAGPipeline(ABC):
    def build_index(self, documents: list[Document]): ...
    def generate_answer(self, question: str) -> tuple[str, Any]: ...