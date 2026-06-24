from abc import ABC
from pathlib import Path
from typing import Any

from natural_rag.data import Document
from natural_rag.dataset import RAGDataset

class RAGPipeline(ABC):
    def build_index(self, documents: list[Document]): ...
    def generate_answer(self, question: str) -> tuple[str, Any]: ...

try:
    from natural_rag.pipelines.ragu_pipelines import RAGUPipeline
except ImportError:
    pass

try:
    from natural_rag.pipelines.lightrag_pipelines import LightRAGPipeline
except ImportError:
    pass

try:
    from natural_rag.pipelines.nano_graphrag_pipelines import NanoGraphRAGPipeline
except ImportError:
    pass

try:
    from natural_rag.pipelines.fast_graphrag_pipelines import FastGraphRAGPipeline
except ImportError:
    pass

try:
    from natural_rag.pipelines.wikontic_pipeline import WikonticPipeline
except ImportError:
    pass
