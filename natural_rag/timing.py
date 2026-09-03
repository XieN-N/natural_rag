"""Uniform indexing-cost measurement shared by all engines.

Front #1 of the Wikontic comparison is *indexing speed*, so the number has to be
produced the same way for every engine. :class:`IndexTimer` writes two files next
to the run's ``index/`` and ``answers/`` folders:

``index_timing.jsonl``
    One record per document: ``doc_id``, ``chars``, ``seconds``, ``ok``,
    ``cumulative_seconds``. Appended as the run progresses, so a job killed by
    the SLURM time limit still leaves usable data.

``index_summary.json``
    Totals: wall time, docs/min, chars/sec, LLM calls and token counts.

LLM calls are counted by patching the OpenAI client instance in place
(:func:`count_openai_calls`), which works for both the synchronous client
Wikontic uses (``LLMTripletExtractor.client``) and RAGU's async
``CachedAsyncOpenAI``.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def describe_request(kwargs: dict) -> str:
    """Size of a chat request, for when the gateway rejects it without saying why.

    Wikontic sends the retrieved subgraph as one user message, so a question
    that links to a well-connected entity can produce a prompt far past the
    model's context window. Gateways tend to answer that with a bare
    ``400 / Request failed``, which is indistinguishable from a malformed
    request -- and the request is never saved, so there is nothing to inspect
    afterwards. Measuring it here turns that into a number.
    """
    messages = kwargs.get("messages") or []
    parts = []
    total_chars = 0
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        size = len(content) if isinstance(content, str) else 0
        total_chars += size
        parts.append(f"{message.get('role', '?')}={size}")

    tokens = "n/a"
    try:
        import tiktoken

        encoding = tiktoken.encoding_for_model(kwargs.get("model", "gpt-4o-mini"))
        tokens = str(sum(
            len(encoding.encode(m["content"]))
            for m in messages
            if isinstance(m, dict) and isinstance(m.get("content"), str)
        ))
    except Exception:
        pass  # diagnostics must never be the thing that breaks a run
    return (f"model={kwargs.get('model')} chars={total_chars} tokens={tokens} "
            f"({', '.join(parts)})")


@dataclass
class LLMCallCounter:
    """Thread-safe tally of chat-completion calls and tokens."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt
            self.completion_tokens += completion

    def as_dict(self) -> dict[str, int]:
        with self._lock:
            return {
                "llm_calls": self.calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
            }


def count_openai_calls(client: Any, counter: LLMCallCounter) -> bool:
    """Patch ``client.chat.completions.create`` in place to feed ``counter``.

    Returns ``True`` when the patch was applied. Tolerates clients whose shape
    differs (returns ``False`` instead of raising) so a missing counter never
    breaks an actual run.
    """
    try:
        completions = client.chat.completions
        original = completions.create
    except AttributeError:
        return False

    if getattr(original, "_natural_rag_counted", False):
        return True

    import inspect

    if inspect.iscoroutinefunction(original):

        async def counted(*args: Any, **kwargs: Any) -> Any:
            try:
                response = await original(*args, **kwargs)
            except Exception as exc:
                logger.error("LLM call failed: %s | %s", exc, describe_request(kwargs))
                raise
            counter.add(response)
            return response

    else:

        def counted(*args: Any, **kwargs: Any) -> Any:
            try:
                response = original(*args, **kwargs)
            except Exception as exc:
                logger.error("LLM call failed: %s | %s", exc, describe_request(kwargs))
                raise
            counter.add(response)
            return response

    counted._natural_rag_counted = True  # type: ignore[attr-defined]
    completions.create = counted  # type: ignore[method-assign]
    return True


def attach_counter(obj: Any, counter: LLMCallCounter) -> bool:
    """Patch ``obj`` or a nested client attribute, whichever exposes chat.completions.

    Wrappers such as RAGU's ``CachedAsyncOpenAI`` may hold the real client in an
    attribute rather than exposing ``chat`` themselves.
    """
    for candidate in (obj, getattr(obj, "client", None), getattr(obj, "_client", None)):
        if candidate is not None and count_openai_calls(candidate, counter):
            return True
    return False


class IndexTimer:
    """Records per-document indexing time and writes the summary on exit.

    Usage::

        with IndexTimer(base_dir, engine="wikontic", dataset="musique") as timer:
            for doc in docs:
                with timer.measure(doc.id, len(doc.text or "")):
                    index(doc)
    """

    def __init__(
        self,
        out_dir: str | Path,
        engine: str,
        dataset: str,
        model: str | None = None,
        workers: int = 1,
        counter: LLMCallCounter | None = None,
        extra: dict[str, Any] | None = None,
        total_units: int | None = None,
    ):
        self.out_dir = Path(out_dir)
        self.engine = engine
        self.dataset = dataset
        self.model = model
        self.workers = workers
        self.counter = counter
        self.extra = dict(extra or {})
        self.total_units = total_units

        self.timing_path = self.out_dir / "index_timing.jsonl"
        self.summary_path = self.out_dir / "index_summary.json"
        #: One frozen copy of index_summary.json per finished pass. See
        #: _rotate_previous_summary.
        self.passes_dir = self.out_dir / "passes"

        self._lock = threading.Lock()
        self._start: float | None = None
        self._started_at: float | None = None
        self._wall_seconds = 0.0
        self.n_docs = 0
        self.n_skipped = 0
        self.failures = 0
        self.total_chars = 0
        self.total_doc_seconds = 0.0

    # ── lifecycle ──────────────────────────────────────────────────

    def _rotate_previous_summary(self) -> None:
        """Freeze the previous pass's summary before this one overwrites it.

        ``index_summary.json`` is rewritten at the start of every run, so a
        resumed index loses the numbers of the pass before it the moment the
        next job is submitted. Those numbers are the measurement: how much of
        the corpus one pass covers, and what it cost.

        Rotating here rather than asking the operator to copy files first is
        deliberate — several passes across three models, submitted at odd hours,
        is exactly the setting where "remember to snapshot" fails once and takes
        the comparison with it.

        Never raises: losing a snapshot must not end a run that has hours of
        indexing behind it.
        """
        if not self.summary_path.exists():
            return
        try:
            self.passes_dir.mkdir(parents=True, exist_ok=True)
            existing = len(list(self.passes_dir.glob("pass*.json")))
            for number in range(existing + 1, existing + 100):
                target = self.passes_dir / f"pass{number:02d}.json"
                if target.exists():
                    continue  # never overwrite a snapshot
                data = json.loads(self.summary_path.read_text(encoding="utf-8"))
                data["pass"] = number
                data["snapshot_at"] = time.time()
                # Where this pass ends in the append-only timing log. Without it
                # the per-pass rows cannot be separated afterwards.
                data["timing_lines"] = self._count_timing_lines()
                target.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                return
        except Exception as exc:
            logger.warning(
                "Could not snapshot the previous pass into %s: %s. Indexing "
                "continues; the earlier numbers survive only in the run log.",
                self.passes_dir, exc,
            )

    def _count_timing_lines(self) -> int:
        try:
            with self.timing_path.open(encoding="utf-8") as fh:
                return sum(1 for line in fh if line.strip())
        except OSError:
            return 0

    def __enter__(self) -> IndexTimer:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._rotate_previous_summary()
        self._start = time.perf_counter()
        self._started_at = time.time()
        # Write the summary up front with status="running" so a run that is
        # still going — or one killed outright by the scheduler, where __exit__
        # never fires — is still reportable. runs/index_stats.py recomputes the
        # live numbers from index_timing.jsonl whenever it sees this status.
        self.write_summary(status="running")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._wall_seconds = time.perf_counter() - (self._start or time.perf_counter())
        self.write_summary(status="interrupted" if exc_type is not None else "done")

    # ── recording ──────────────────────────────────────────────────

    @contextmanager
    def measure(self, doc_id: str, chars: int = 0, count: int = 1) -> Iterator[None]:
        started = time.perf_counter()
        ok = True
        try:
            yield
        except BaseException:
            ok = False
            raise
        finally:
            self.record(doc_id, chars, time.perf_counter() - started, ok=ok, count=count)

    def record(
        self,
        doc_id: str,
        chars: int,
        seconds: float,
        ok: bool = True,
        count: int = 1,
    ) -> None:
        """Record one indexing step.

        ``count`` is the number of documents the step covered — engines that
        index the whole corpus in one call (RAGU) report a single step covering
        many documents.
        """
        with self._lock:
            self.n_docs += count
            self.total_chars += chars
            self.total_doc_seconds += seconds
            if not ok:
                self.failures += 1
            cumulative = self.total_doc_seconds
            line = json.dumps(
                {
                    "doc_id": doc_id,
                    "n_docs": count,
                    "chars": chars,
                    "seconds": round(seconds, 3),
                    "ok": ok,
                    "cumulative_seconds": round(cumulative, 3),
                },
                ensure_ascii=False,
            )
            with self.timing_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def record_skipped(self, count: int = 1) -> None:
        """Documents skipped by --resume (not counted as indexing work)."""
        with self._lock:
            self.n_skipped += count

    # ── summary ────────────────────────────────────────────────────

    def write_summary(self, status: str = "done") -> dict[str, Any]:
        wall = self._wall_seconds or (
            time.perf_counter() - self._start if self._start else 0.0
        )
        summary: dict[str, Any] = {
            "engine": self.engine,
            "dataset": self.dataset,
            "model": self.model,
            "workers": self.workers,
            "status": status,
            "started_at": self._started_at,
            "total_units": self.total_units,
            "n_docs": self.n_docs,
            "n_skipped": self.n_skipped,
            "failures": self.failures,
            "total_chars": self.total_chars,
            "wall_seconds": round(wall, 3),
            "docs_per_min": round(self.n_docs / wall * 60, 3) if wall > 0 else None,
            "chars_per_sec": round(self.total_chars / wall, 1) if wall > 0 else None,
            "mean_doc_seconds": (
                round(self.total_doc_seconds / self.n_docs, 3) if self.n_docs else None
            ),
            "interrupted": status == "interrupted",
        }
        if self.counter is not None:
            counts = self.counter.as_dict()
            summary.update(counts)
            if self.n_docs:
                summary["llm_calls_per_doc"] = round(counts["llm_calls"] / self.n_docs, 2)
        summary.update(self.extra)

        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return summary
