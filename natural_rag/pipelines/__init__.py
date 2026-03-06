from abc import ABC

from natural_rag.data import Document


class RAGPipeline(ABC):
    def build_index(self, documents: list[Document]): ...
    def answer_question(self, question: str) -> list[str]: ...