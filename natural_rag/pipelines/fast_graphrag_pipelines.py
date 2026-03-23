import asyncio
from pathlib import Path
from typing import Any

from fast_graphrag import GraphRAG

from natural_rag.pipelines import RAGPipeline
from natural_rag.data import Document


class FastGraphRAGPipeline(RAGPipeline):
    def __init__(
        self,
        working_dir: str | Path,
        domain: str,
        example_queries: list[str],
        entity_types: list[str],
        config: Any = None,
    ):
        kwargs: dict[str, Any] = {
            "working_dir": str(working_dir),
            "domain": domain,
            "example_queries": "\n".join(example_queries),
            "entity_types": entity_types,
        }
        if config is not None:
            kwargs["config"] = config

        self._loop = asyncio.new_event_loop()
        try:
            self._previous_loop = asyncio.get_event_loop()
        except Exception:
            self._previous_loop = None

        self._grag = GraphRAG(**kwargs)

    def _run(self, coro):
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coro)

    def build_index(self, documents: list[Document]):
        for doc in documents:
            if doc.text:
                self._run(self._grag.async_insert(doc.text))

    def generate_answer(self, question: str) -> tuple[str, Any]:
        result = self._run(self._grag.async_query(question))

        if isinstance(result, str):
            return result, None

        answer = getattr(result, "response", str(result))
        context = getattr(result, "context", None)
        return answer, context

    def close(self):
        try:
            if hasattr(self, "_loop") and not self._loop.is_closed():
                self._loop.close()
        finally:
            try:
                asyncio.set_event_loop(self._previous_loop)
            except Exception:
                try:
                    asyncio.set_event_loop(None)
                except Exception:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass