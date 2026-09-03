"""Time somebody else's indexing run into our comparison table.

The GraphRAG-Bench runners in ``bond005/GraphRAG-Benchmark/Examples`` do their
own thing and know nothing about ``IndexTimer``. This wraps one of them so its
indexing phase lands in ``index_summary.json`` like every other engine, and
``runs/index_stats.py`` can put RAGU, HippoRAG and LightRAG in the same table as
Wikontic.

Deliberately **no LLM call counter**: what is wanted here is how long indexing
takes, not what it costs. ``calls/doc`` and ``prompt_tok`` stay empty in the
table, which is honest — nothing counted them.

    python runs_cluster/time_phase.py \\
        --out-dir /userspace/sse/natural_rag/generated/graphbench_ragu_gpt-oss-20b \\
        --engine ragu --dataset graphrag_bench_medical --model gpt-oss-20b \\
        --corpus ./Datasets/Corpus/medical.parquet \\
        -- python Examples/run_ragu.py --subset medical --phase index

Everything after ``--`` is run as-is, with stdout and stderr inherited so the
job log stays live. The wrapper's exit code is the child's.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from natural_rag.timing import IndexTimer  # noqa: E402


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--out-dir", type=Path, required=True,
                   help="Where index_summary.json and index_timing.jsonl go. "
                        "Use one directory per engine+model so index_stats.py "
                        "sees them as separate runs.")
    p.add_argument("--engine", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--model", default=None, help="Model that builds the index.")
    p.add_argument("--corpus", type=Path, default=None,
                   help="Corpus parquet/json, only to count how many entries "
                        "the run covered. Failure to read it is not fatal.")
    p.add_argument("--units", type=int, default=None,
                   help="Corpus entry count, when --corpus cannot be read.")
    p.add_argument("--note", action="append", default=[],
                   help="Free-form key=value recorded in the summary.")
    args, rest = p.parse_known_args()
    if rest and rest[0] == "--":
        rest = rest[1:]
    if not rest:
        p.error("nothing to run: put the command after --")
    return args, rest


def count_corpus(path: Path | None, fallback: int | None) -> int:
    """Corpus entries, or 0 when it cannot be determined.

    These engines chunk internally, so an "entry" here is a whole corpus
    document (a textbook), not a chunk. That makes seconds-per-entry
    incomparable to Wikontic, which was fed pre-split 4000-character pieces —
    the runbook says so, and the number is kept only to give the table a
    denominator.
    """
    if fallback is not None:
        return fallback
    if path is None or not path.exists():
        return 0
    try:
        if path.suffix == ".parquet":
            import pandas as pd
            return len(pd.read_parquet(path))
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else 0
    except Exception as exc:
        print(f"time_phase: could not count {path}: {exc}", file=sys.stderr)
        return 0


def main() -> int:
    args, command = parse_args()
    units = count_corpus(args.corpus, args.units)

    extra = {"phase": "index", "harness": "GraphRAG-Benchmark/Examples"}
    for note in args.note:
        key, _, value = note.partition("=")
        extra[key] = value

    print(f"time_phase: {args.engine} / {args.model} on {args.dataset}, "
          f"{units} corpus entries")
    print(f"time_phase: running {' '.join(command)}", flush=True)

    started = time.perf_counter()
    with IndexTimer(
        args.out_dir,
        engine=args.engine,
        dataset=args.dataset,
        model=args.model,
        workers=1,
        counter=None,          # время нужно, стоимость нет
        total_units=units or None,
        extra=extra,
    ) as timer:
        # stdout/stderr inherited: the job log stays live, and the engine's own
        # progress output is not swallowed by us.
        result = subprocess.run(command)
        # One step covering the whole corpus — IndexTimer.record takes `count`
        # for exactly this, engines that index everything in one go.
        timer.record(
            doc_id=f"{args.engine}:{args.dataset}",
            chars=0,
            seconds=time.perf_counter() - started,
            ok=result.returncode == 0,
            count=units or 1,
        )
        timer.extra["returncode"] = result.returncode

    print(f"time_phase: finished with {result.returncode}, "
          f"summary in {args.out_dir / 'index_summary.json'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
