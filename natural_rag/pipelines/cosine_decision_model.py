"""Control for the decision model: cosine similarity instead of a judgement.

``CosineDecisionModel`` returns the cosine between the query and a candidate where
:class:`~ragu.decision.DecisionModel` returns ``P(Y)``. The search engine then works
as usual: same pools, budgets and walk. Comparing a run with this model against a run
with a real one shows what the model's judgement adds on top of the rest of the
engine. It ignores ``state_context``: the score depends on the query only.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

import numpy as np
from ragu.decision import BaseDecisionModel, DecisionOutput, SingleDecision
from ragu.decision.types import ScoredCandidate

T = TypeVar("T")


class CosineDecisionModel(BaseDecisionModel):
    """Scores candidates by cosine similarity to the query; no LLM requests."""

    def __init__(self, embedder: Any):
        """
        :param embedder: Embedder of the index, with ``batch_embed_text``.
        """
        self.embedder = embedder

    async def a_decide(
        self, question: str, options: Sequence[str], context: str = "",
    ) -> SingleDecision:
        raise NotImplementedError("The cosine control only scores candidates pointwise")

    async def a_score_pointwise(
        self,
        query: str,
        candidates: Sequence[T],
        format_fn: Callable[[T], str] = str,
        state_context: str = "",
        threshold: float = 0.5,
        top_k: int | None = None,
    ) -> DecisionOutput[T]:
        """
        Score every candidate by its cosine to the query.

        Cosines are clipped to ``[0, 1]``. ``n_calls`` counts one per candidate, as for a
        real model, so that the decision budget of the walk means the same.

        :param query: User query.
        :param candidates: Items to score.
        :param format_fn: Renders a candidate as text.
        :param state_context: Ignored.
        :param threshold: Lowest score of a selected candidate.
        :param top_k: Keep at most this many selected candidates.
        :return: Candidates sorted by score, best first.
        """
        if not candidates:
            return DecisionOutput()
        vectors = np.asarray(
            await self.embedder.batch_embed_text([query, *(format_fn(c) for c in candidates)]),
            dtype=np.float32,
        )
        norms = np.linalg.norm(vectors, axis=1)
        norms[norms == 0] = 1.0
        vectors = vectors / norms[:, None]
        cosines = np.clip(vectors[1:] @ vectors[0], 0.0, 1.0)
        scored = sorted(
            (
                ScoredCandidate(index=i, item=c, probability=float(p), passed_threshold=float(p) >= threshold)
                for i, (c, p) in enumerate(zip(candidates, cosines))
            ),
            key=lambda candidate: -candidate.probability,
        )
        selected = [candidate.item for candidate in scored if candidate.passed_threshold]
        return DecisionOutput(
            selected=selected[:top_k] if top_k is not None else selected,
            scored=scored,
            n_calls=len(candidates),
        )

    async def a_score_listwise(
        self,
        query: str,
        candidates: Sequence[T],
        format_fn: Callable[[T], str] = str,
        state_context: str = "",
        top_k: int = 3,
        min_prob: float = 0.05,
        max_none_prob: float = 0.5,
    ) -> DecisionOutput[T]:
        raise NotImplementedError("The cosine control only scores candidates pointwise")
