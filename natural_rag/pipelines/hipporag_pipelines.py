from pathlib import Path
from typing import Any

from hipporag import HippoRAG
from hipporag.utils.config_utils import BaseConfig

from natural_rag.data import Document
from natural_rag.pipelines import RAGPipeline


class HippoRAGPipeline(RAGPipeline):
    def __init__(
        self,
        save_dir: str | Path,
        llm_model_name: str,
        embedding_model_name: str,
        llm_base_url: str | None = None,
        embedding_base_url: str | None = None,
        retrieval_top_k: int = 200,
        qa_top_k: int = 5,
        force_index_from_scratch: bool = False,
        **config_overrides: Any,
    ):
        self.retrieval_top_k = retrieval_top_k

        config = BaseConfig(
            save_dir=str(save_dir),
            llm_name=llm_model_name,
            llm_base_url=llm_base_url,
            embedding_model_name=embedding_model_name,
            embedding_base_url=embedding_base_url,
            retrieval_top_k=retrieval_top_k,
            qa_top_k=qa_top_k,
            force_index_from_scratch=force_index_from_scratch,
            **config_overrides,
        )
        self._rag = HippoRAG(global_config=config)

    def build_index(self, documents: list[Document]):
        docs = [
            self._format_document(doc)
            for doc in documents
            if doc.text
        ]
        self._rag.index(docs=docs)

    def generate_answer(self, question: str) -> tuple[str, Any]:
        retrieval_results = self._rag.retrieve(
            queries=[question],
            num_to_retrieve=self.retrieval_top_k,
        )
        query_solutions, response_messages, metadata = self._rag.rag_qa(
            retrieval_results,
        )

        return query_solutions[0].answer, {
            "retrieval": retrieval_results[0],
            "response_message": response_messages[0],
            "metadata": metadata[0],
        }

    @staticmethod
    def _format_document(doc: Document) -> str:
        if doc.title:
            return f"Title: {doc.title}\n\n{doc.text}"
        return doc.text or ""
