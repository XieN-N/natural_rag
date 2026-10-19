"""Run GraphRAG-Benchmark's generation_eval with a YandexGPT judge.

The judge itself goes through ``ChatOpenAI`` unchanged (Yandex AI Studio speaks
the OpenAI chat API). Embeddings do not: Yandex accepts one text per request
and only float encoding, while langchain's ``OpenAIEmbeddings`` sends token
arrays in base64. This wrapper replaces ``langchain_openai.OpenAIEmbeddings``
with a compatible client before running the module, so the benchmark's code is
used as is. Run it from the GraphRAG-Benchmark checkout with the module's flags:

    cd $GRAPHRAG_BENCH_ROOT && LLM_API_KEY=<key> python <natural_rag>/runs_local/judge_yandex.py \
        --mode API --model gpt://<folder>/yandexgpt-5.1/latest --base_url https://llm.api.cloud.yandex.net/v1 \
        --embedding_model emb://<folder>/text-search-query/latest --data_file in.json --output_file out.json
"""
from __future__ import annotations

import asyncio
import os
import runpy
import sys

import langchain_openai
from langchain_core.embeddings import Embeddings
from openai import AsyncOpenAI, OpenAI


class OneTextEmbeddings(Embeddings):
    """Embeddings over an OpenAI-compatible API that takes a single string per request."""

    def __init__(self, model: str, base_url: str, api_key, **_ignored):
        key = api_key.get_secret_value() if hasattr(api_key, "get_secret_value") else api_key
        self.model = model
        self._sync = OpenAI(api_key=key, base_url=base_url, max_retries=8, timeout=60)
        self._async = AsyncOpenAI(api_key=key, base_url=base_url, max_retries=8, timeout=60)
        self._limit = int(os.environ.get("JUDGE_EMBED_CONCURRENCY", "4"))
        self._semaphore: asyncio.Semaphore | None = None

    def embed_query(self, text: str) -> list[float]:
        response = self._sync.embeddings.create(model=self.model, input=[text or " "], encoding_format="float")
        return response.data[0].embedding

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    async def aembed_query(self, text: str) -> list[float]:
        if self._semaphore is None:  # bound to the running loop
            self._semaphore = asyncio.Semaphore(self._limit)
        async with self._semaphore:
            response = await self._async.embeddings.create(model=self.model, input=[text or " "], encoding_format="float")
        return response.data[0].embedding

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [await self.aembed_query(t) for t in texts]


if __name__ == "__main__":
    langchain_openai.OpenAIEmbeddings = OneTextEmbeddings
    sys.path.insert(0, os.getcwd())
    runpy.run_module("Evaluation.generation_eval", run_name="__main__", alter_sys=True)
