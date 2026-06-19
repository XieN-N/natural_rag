import asyncio
import inspect
from pathlib import Path
from typing import Any, Callable

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

from natural_rag.pipelines import RAGPipeline
from natural_rag.data import Document


class LightRAGPipeline(RAGPipeline):
    def __init__(
        self,
        working_dir: str | Path,
        llm_model_func: Callable,
        embedding_func: EmbeddingFunc,
        tokenizer: Any = None,
        query_mode: str = "hybrid",
        addon_params: dict[str, Any] | None = None,
        max_parallel_insert: int | None = None,
    ):
        self.query_mode = query_mode

        self._loop = asyncio.new_event_loop()
        try:
            self._previous_loop = asyncio.get_event_loop()
        except Exception:
            self._previous_loop = None

        asyncio.set_event_loop(self._loop)

        rag_kwargs: dict[str, Any] = {
            'working_dir': str(working_dir),
            'llm_model_func': llm_model_func,
            'embedding_func': embedding_func,
            'tokenizer': tokenizer,
        }
        lightrag_parameters = inspect.signature(LightRAG).parameters
        if addon_params is not None and 'addon_params' in lightrag_parameters:
            rag_kwargs['addon_params'] = addon_params
        if (
            max_parallel_insert is not None
            and 'max_parallel_insert' in lightrag_parameters
        ):
            rag_kwargs['max_parallel_insert'] = max_parallel_insert

        self._rag = LightRAG(**rag_kwargs)

        self._run(self._rag.initialize_storages())

        try:
            from lightrag.kg.shared_storage import initialize_pipeline_status
            self._run(initialize_pipeline_status())
        except ImportError:
            pass

    def _run(self, coro):
        asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coro)

    async def _cancel_pending_tasks(self):
        current_task = asyncio.current_task(loop=self._loop)
        pending_tasks = [
            task
            for task in asyncio.all_tasks(self._loop)
            if task is not current_task and not task.done()
        ]
        if not pending_tasks:
            return
        for task in pending_tasks:
            task.cancel()
        await asyncio.gather(*pending_tasks, return_exceptions=True)

    # def build_index(self, documents: list[Document]):
    #     for doc in documents:
    #         if doc.text:
    #             self._run(self._rag.ainsert(doc.text))

    def build_index(self, documents: list[Document]):
        docs = [doc for doc in documents if doc.text]
        texts = [doc.text for doc in docs]
        ids = [doc.id for doc in docs]

        self._run(self._rag.ainsert(texts, ids=ids))

    def generate_answer(self, question: str) -> tuple[str, Any]:
        context_param = QueryParam(
            mode=self.query_mode,
            only_need_context=True,
        )
        context = self._run(self._rag.aquery(question, param=context_param))

        answer_param = QueryParam(mode=self.query_mode)
        answer = self._run(self._rag.aquery(question, param=answer_param))

        return answer, context

    def close(self):
        try:
            self._run(self._rag.finalize_storages())
        except Exception:
            pass
        finally:
            if hasattr(self, "_loop") and not self._loop.is_closed():
                try:
                    self._run(self._cancel_pending_tasks())
                    self._run(self._loop.shutdown_asyncgens())
                except Exception:
                    pass
                self._loop.close()

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
            if hasattr(self, "_loop") and not self._loop.is_closed():
                self.close()
        except Exception:
            pass
