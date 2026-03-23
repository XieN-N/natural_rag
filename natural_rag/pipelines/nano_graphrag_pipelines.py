import asyncio
from pathlib import Path
from typing import Any, Callable

from nano_graphrag import GraphRAG, QueryParam
from nano_graphrag._utils import wrap_embedding_func_with_attrs

from natural_rag.pipelines import RAGPipeline
from natural_rag.data import Document


class NanoGraphRAGPipeline(RAGPipeline):
    def __init__(
        self,
        working_dir: str | Path,
        best_model_func: Callable,
        cheap_model_func: Callable | None = None,
        embedding_func: Callable | None = None,
        embedding_dim: int | None = None,
        max_token_size: int = 8192,
        query_mode: str = "local",
        **graphrag_kwargs,
    ):
        self.query_mode = query_mode

        kwargs: dict[str, Any] = {
            "working_dir": str(working_dir),
            "best_model_func": best_model_func,
        }

        if cheap_model_func is not None:
            kwargs["cheap_model_func"] = cheap_model_func

        if embedding_func is not None:
            if embedding_dim is None:
                raise ValueError(
                    "embedding_dim must be provided when embedding_func is used"
                )

            wrapped_embedding = wrap_embedding_func_with_attrs(
                embedding_dim=embedding_dim,
                max_token_size=max_token_size,
            )(embedding_func)

            kwargs["embedding_func"] = wrapped_embedding

        if query_mode == "naive" and "enable_naive_rag" not in graphrag_kwargs:
            kwargs["enable_naive_rag"] = True

        kwargs.update(graphrag_kwargs)

        self._rag = GraphRAG(**kwargs)

    def build_index(self, documents: list[Document]):
        for doc in documents:
            if doc.text:
                self._rag.insert(doc.text)

    def generate_answer(self, question: str) -> tuple[str, Any]:
        context = self._rag.query(
            question,
            param=QueryParam(mode=self.query_mode, only_need_context=True),
        )
        answer = self._rag.query(
            question,
            param=QueryParam(mode=self.query_mode),
        )
        return answer, context