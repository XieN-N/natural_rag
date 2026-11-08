"""Replay harvested decisions through DecisionSearchEngine and compare the contexts.

``ReplayDecisionModel`` answers from the probabilities saved by a past run instead
of calling a model, so a change to the engine can be checked without a GPU: with
the same prompts and the same masses the old run's context must come out word for
word. Prompts come from ``runs_local/harvest_decisions.py`` output (fields
``messages``, ``mass_y``, ``mass_n``), read from a ``.jsonl`` or from a member of a
``.tar.gz``.

The check goes through ``RAGUPipeline`` and ``write_context`` of ``runs/ragu_run.py``,
only the decision model and the answering LLM are stubs. Query vectors still need
the embedder of the index (``runs_local/serve_embedder.py``).

    python runs_local/replay_decisions.py --ids 0-19 --embed-base-url http://127.0.0.1:8002/v1

The saved data has a gap at the seed hop: ``harvest_decisions.py`` keeps one row per
unique prompt, and seed-hop prompts of different runs coincide, so their masses come
from the first harvested run, not from the one compared with. vLLM answers the same
prompt slightly differently from run to run, which changes the order of the kept
facts and with it the state text of every later prompt. So by default the seed hop
is pinned to the compared run: its sorted probabilities (``metrics.selection``) are
assigned to the candidates in the order its context lists them. Pools, the threshold
and the floor are still applied by the engine, but which seed candidates pass and in
what order comes from the reference, so only further hops are replayed independently:
their prompts must be found in the saved data word for word. ``--no-pin-seed-hop``
replays the saved masses as they are, for data harvested from a single run.

A question with a prompt missing from the saved data has no verdict and is listed
separately. Exit code 1 means some question with full data differs.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tarfile
import tempfile
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, TypeVar

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "runs"))

from ragu.common.prompts.messages import render
from ragu.decision import BaseDecisionModel, DecisionModel, DecisionOutput, SingleDecision
from ragu.models.embedder import EmbedderOpenAI
from ragu.models.llm import CachedAsyncOpenAI, LLMOpenAI
from ragu.search_engine.decision_search import _format_chunk, _format_entity, _format_relation

from natural_rag.dataset import RAGDataset
from natural_rag.pipelines.ragu_pipelines import RAGUPipeline
from ragu_run import write_context

T = TypeVar("T")

STUB_ANSWER = "stub answer"

#: Section of the context per candidate formatter, and how the context renders a candidate.
_SECTIONS: dict[Callable[[Any], str], tuple[str, str, Callable[[Any], str]]] = {
    _format_entity: ("entities", "**Entities**", lambda e: f"{e.entity_name}, {e.entity_type}, {e.description}"),
    _format_relation: ("relations", "**Relations**", lambda r: (
        f"{r.subject_name}, {r.relation_type}, {r.object_name} - {r.description}, {getattr(r, 'rank', '')}"
    )),
    _format_chunk: ("chunks", "**Chunks**", lambda c: c.content),
}
_SECTION_HEADERS = ("**Entities**", "**Relations**", "**Summary**", "**Chunks**")


def prompt_key(messages: Iterable[dict[str, Any]]) -> str:
    """Hash of a conversation, by role and content only."""
    digest = hashlib.sha1()
    for message in messages:
        digest.update(f"{message['role']}\x00{message['content']}\x00".encode("utf-8"))
    return digest.hexdigest()


def section_text(context: str, header: str) -> str:
    """One section of a rendered context, framed by newlines for whole-line search."""
    start = context.find(header)
    if start < 0:
        return ""
    ends = [context.find(h, start + 1) for h in _SECTION_HEADERS]
    end = min((e for e in ends if e > start), default=len(context))
    return "\n" + context[start:end].strip() + "\n"


def load_masses(path: Path, member: str | None) -> dict[str, tuple[float, float]]:
    """Read ``prompt key -> (mass_y, mass_n)`` from harvested decisions."""

    def rows(lines: Iterable[bytes]) -> dict[str, tuple[float, float]]:
        masses: dict[str, tuple[float, float]] = {}
        for line in lines:
            row = json.loads(line)
            masses[prompt_key(row["messages"])] = (row["mass_y"], row["mass_n"])
        return masses

    if path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as archive:
            file = archive.extractfile(member or "")
            if file is None:
                raise ValueError(f"{member!r} is not a file in {path}")
            return rows(file)
    with open(path, "rb") as file:
        return rows(file)


class _ReplayBackend:
    """Stands in for an LLM: option masses come from the saved table."""

    def __init__(self, masses: dict[str, tuple[float, float]]):
        self.masses = masses
        self.missing: list[str] = []

    async def option_probabilities(
        self, conversation: list[dict[str, Any]], options: list[str], **kwargs: Any,
    ) -> dict[str, float]:
        found = self.masses.get(prompt_key(conversation))
        if found is None:
            self.missing.append(conversation[-1]["content"])
            raise LookupError("prompt not in the saved decisions")
        return {"Y": found[0], "N": found[1]}


class ReplayDecisionModel(BaseDecisionModel):
    """Decision model that repeats saved answers; only pointwise judgement was saved.

    Prompts and scoring are those of :class:`DecisionModel`, on a backend that looks
    the masses up. A prompt that is not in the table counts as a failed request
    (rejected, ``degraded``), as in a real run, and is added to :attr:`missing`.
    """

    def __init__(self, masses: dict[str, tuple[float, float]]):
        self._backend = _ReplayBackend(masses)
        self._model = DecisionModel(self._backend, skip_failed_requests=True)  # type: ignore[arg-type]
        self._pin: tuple[str, dict[str, Any]] | None = None
        self.unsaved_seed_prompts = 0
        self.changed_seed_probabilities = 0

    def pin_seed_hop(self, context: str, selection: dict[str, Any]) -> None:
        """Make the next seed hop reproduce a run's kept candidates (see the module docstring).

        :param context: The run's rendered context.
        :param selection: The run's ``metrics["selection"]``.
        """
        self._pin = (context, selection)
        self.unsaved_seed_prompts = 0
        self.changed_seed_probabilities = 0

    def _apply_pin(self, query: str, candidates: Sequence[Any], format_fn: Callable[[Any], str]) -> None:
        """Overwrite the saved masses of these seed-hop prompts with the pinned run's."""
        assert self._pin is not None
        context, selection = self._pin
        name, header, render_line = _SECTIONS[format_fn]
        probabilities = selection[name]["probabilities"]
        if len(probabilities) != len(candidates):
            return  # another pool: keep the saved masses, the comparison will show it
        section = section_text(context, header)
        offsets = {i: section.find(f"\n{render_line(c)}\n") for i, c in enumerate(candidates)}
        kept = sorted((i for i, offset in offsets.items() if offset >= 0), key=offsets.__getitem__)
        order = kept + [i for i in range(len(candidates)) if i not in kept]
        conversations = render(
            self._model.get_prompt("decision_pointwise").messages,
            query=query,
            state_context="",
            candidate=[format_fn(c) for c in candidates],
        )
        saved = []
        for rank, i in enumerate(order):
            key = prompt_key(conversations[i].to_openai())
            old = self._backend.masses.get(key)
            if old is None:
                self.unsaved_seed_prompts += 1
            elif old[0] + old[1] > 0:
                saved.append(round(old[0] / (old[0] + old[1]), 4))
            # Rounded probabilities may tie; the offset keeps the order of the context.
            probability = probabilities[rank] - rank * 1e-9
            self._backend.masses[key] = (probability, 1.0 - probability)
        self.changed_seed_probabilities += sum(
            a != b for a, b in zip(sorted(saved, reverse=True), probabilities)
        )

    @property
    def missing(self) -> list[str]:
        """User messages of the prompts not found so far."""
        return self._backend.missing

    async def a_decide(
        self, question: str, options: Sequence[str], context: str = "",
    ) -> SingleDecision:
        raise NotImplementedError("Saved decisions hold pointwise judgements only")

    async def a_score_pointwise(
        self,
        query: str,
        candidates: Sequence[T],
        format_fn: Callable[[T], str] = str,
        state_context: str = "",
        threshold: float = 0.5,
        top_k: int | None = None,
    ) -> DecisionOutput[T]:
        if self._pin is not None and not state_context:
            self._apply_pin(query, candidates, format_fn)
        return await self._model.a_score_pointwise(
            query, candidates, format_fn, state_context=state_context, threshold=threshold, top_k=top_k,
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
        raise NotImplementedError("Saved decisions hold pointwise judgements only")


class _StubAnswerLLM:
    """Answering LLM of the replay: the context is what is being checked."""

    async def batch_chat_completion(self, conversations: Sequence[Any], **kwargs: Any) -> list[str]:
        return [STUB_ANSWER] * len(conversations)


def parse_ids(text: str) -> range:
    first, _, last = text.partition("-")
    return range(int(first), int(last or first) + 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--calib", type=Path, default=REPO_ROOT.parent / "itmo_results" / "calib.tar.gz",
                        help="Harvested decisions: .jsonl or .tar.gz")
    parser.add_argument("--calib-member", default="calib/meno_musique.jsonl", help="File inside --calib, when an archive")
    parser.add_argument("--dataset-path", type=Path, default=REPO_ROOT / "datasets" / "musique")
    parser.add_argument("--index-dir", type=Path,
                        default=REPO_ROOT / "generated" / "ragu_musique" / "musique" / "gpt-oss-20b" / "index")
    parser.add_argument("--reference-dir", type=Path,
                        default=REPO_ROOT / "generated" / "ragu_musique__meno_t01" / "musique" / "gpt-oss-20b" / "answers",
                        help="answers/ of the run to compare with")
    parser.add_argument("--ids", default="0-19", help="Question range, e.g. 0-19")
    parser.add_argument("--select-hops", type=int, default=2)
    parser.add_argument("--select-pool-chunks", type=int, default=30)
    parser.add_argument("--select-threshold", type=float, default=0.1)
    parser.add_argument("--embed-base-url", default=os.environ.get("EMBED_BASE_URL", "http://127.0.0.1:8002/v1"))
    parser.add_argument("--embedding-model-name", default="gte-multilingual-base")
    parser.add_argument("--embedding-dim", type=int, default=768)
    parser.add_argument(
        "--pin-seed-hop", action=argparse.BooleanOptionalAction, default=True,
        help="Take the seed-hop outcome from the reference run (see the module docstring).",
    )
    parser.add_argument("--llm-cache", default="tmp/llm_cache_replay", help="Cache of query vectors")
    parser.add_argument("--out", type=Path, default=None, help="Write the verdict per question here (JSON)")
    return parser.parse_args()


def first_difference(left: str, right: str) -> int:
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return i
    return min(len(left), len(right))


def seed_entities_equal(reference: list[dict[str, Any]], replay: list[dict[str, Any]]) -> bool:
    """Same entities in the same order; query vectors may differ in the last float digits."""
    return len(reference) == len(replay) and all(
        a["id"] == b["id"] and abs(a["relevance_score"] - b["relevance_score"]) < 1e-5
        for a, b in zip(reference, replay)
    )


async def run(args: argparse.Namespace) -> int:
    dataset = RAGDataset.load_auto(args.dataset_path)
    print(f"reading {args.calib}", flush=True)
    masses = load_masses(args.calib, args.calib_member)
    print(f"{len(masses)} saved prompts", flush=True)

    embed_client = CachedAsyncOpenAI(
        base_url=args.embed_base_url, api_key="local", cache=args.llm_cache,
        rate_min_delay=0, rate_max_simultaneous=8,
    )
    # The builder model is never called: the index is read from disk.
    unused = LLMOpenAI(CachedAsyncOpenAI(base_url="http://127.0.0.1:9/v1", api_key="unused"), "unused")
    model = ReplayDecisionModel(masses)
    pipeline = RAGUPipeline(
        language="english",
        index_dir=args.index_dir,
        builder_llm=unused,
        assistant_llm=_StubAnswerLLM(),  # type: ignore[arg-type]
        embedder=EmbedderOpenAI(embed_client, args.embedding_model_name, dim=args.embedding_dim, batch_size=32),
        chunker_name="simple",
        query_engine="decision",
        short_answers=True,
        no_abstain=True,
        decision_model=model,
        decision_options={
            "select_hops": args.select_hops,
            "select_pool_chunks": args.select_pool_chunks,
            "select_threshold": args.select_threshold,
        },
    )

    verdicts: dict[int, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for i in parse_ids(args.ids):
            reference_path = args.reference_dir / f"{i}.context.json"
            if not reference_path.exists():
                verdicts[i] = {"verdict": "no_reference"}
                continue
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            model.missing.clear()
            if args.pin_seed_hop:
                model.pin_seed_hop("".join(reference["context"]), reference["metrics"]["selection"])
            answer, context = await pipeline.a_generate_answer(dataset.questions[i].text)
            if answer != STUB_ANSWER:
                raise RuntimeError(f"question {i}: the replay failed, see the warning above ({answer!r})")
            path = Path(tmp) / f"{i}.context.json"
            write_context(path, pipeline, context, seconds=None)
            replay = json.loads(path.read_text(encoding="utf-8"))

            metrics_ref, metrics_new = reference["metrics"] or {}, replay["metrics"] or {}
            verdict: dict[str, Any] = {
                "missing_prompts": len(model.missing),
                "tokens": [reference["context_tokens"], replay["context_tokens"]],
                "calls": [metrics_ref.get("decision_usage", {}).get("calls"),
                          metrics_new.get("decision_usage", {}).get("calls")],
                "prompt_chars_equal": (metrics_ref.get("decision_usage", {}).get("prompt_chars")
                                       == metrics_new.get("decision_usage", {}).get("prompt_chars")),
                "seed_entities_equal": seed_entities_equal(metrics_ref["entities"], metrics_new["entities"]),
                "selection_equal": metrics_ref.get("selection") == metrics_new.get("selection"),
                "hops_equal": metrics_ref.get("selection_hops") == metrics_new.get("selection_hops"),
                "unsaved_seed_prompts": model.unsaved_seed_prompts,
                "changed_seed_probabilities": model.changed_seed_probabilities,
            }
            if replay["context"] == reference["context"]:
                verdict["verdict"] = "match"
            elif model.missing:
                verdict["verdict"] = "no_data"
            else:
                verdict["verdict"] = "differs"
                verdict["first_difference"] = first_difference(
                    "".join(reference["context"]), "".join(replay["context"]),
                )
            verdicts[i] = verdict
            print(i, json.dumps(verdict), flush=True)

    counts: dict[str, list[int]] = {}
    for i, verdict in verdicts.items():
        counts.setdefault(verdict["verdict"], []).append(i)
    print({name: len(ids) for name, ids in counts.items()})
    for name in ("differs", "no_data", "no_reference"):
        if name in counts:
            print(f"{name}: {counts[name]}")
    if args.out:
        args.out.write_text(json.dumps(verdicts, indent=1), encoding="utf-8")
    return 1 if "differs" in counts else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run(parse_args())))
