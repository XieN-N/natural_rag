"""Collect indexing runs into one comparison table.

This is the deliverable for front #1 (indexing speed): it puts every engine ×
dataset × model × mode run side by side.

Runs that are still going — or that were killed outright by the scheduler, where
the final summary never got written — are reported too: ``index_summary.json``
is written up front with ``status="running"``, and the live numbers are
recomputed here from ``index_timing.jsonl``. That means a slow ``structured``
run can be compared against a ``dynamic`` one long before either finishes.

    python runs/index_stats.py generated                      # walk a directory
    python runs/index_stats.py generated/*/*/index_summary.json
    python runs/index_stats.py generated --format csv --out index_stats.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import time
from pathlib import Path

COLUMNS = [
    ("engine", "engine"),
    ("dataset", "dataset"),
    ("mode", "mode"),
    ("scope", "scope"),
    ("status", "status"),
    # Corpus coverage — what the graph actually holds. Read this one, not `seen`.
    ("in_graph", "in_graph"),
    ("empty_docs", "empty"),
    ("workers", "wrk"),
    # `seen` and everything through `fail` describe the LAST session only:
    # index_summary.json is rewritten by every run, and --resume runs are common.
    ("progress", "seen"),
    ("n_docs", "docs"),
    ("wall_hours", "wall_h"),
    ("docs_per_min", "docs/min"),
    ("mean_doc_seconds", "s/doc"),
    ("eta_hours", "eta_h"),
    ("llm_calls_per_doc", "calls/doc"),
    ("prompt_tokens", "prompt_tok"),
    ("failures", "fail"),
    # Cumulative across every session, from the append-only timing log.
    ("attempts", "tries"),
    ("total_doc_hours", "tot_h"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", nargs="*", type=Path, default=[Path("generated")],
                   help="index_summary.json files, or directories to search recursively.")
    p.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    p.add_argument("--out", type=Path, default=None, help="Write to a file instead of stdout.")
    p.add_argument("--done-only", action="store_true", help="Skip runs that are still going.")
    p.add_argument("--passes", action="store_true",
                   help="One row per pass instead of one per run. Reads the "
                        "frozen snapshots in passes/ that IndexTimer writes "
                        "before each rerun, so a --resume index shows how much "
                        "corpus each pass added and what it cost.")
    return p.parse_args()


def read_timing(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    # last line can be torn if the run is writing right now
                    continue
    except OSError:
        return []
    return rows


#: A run whose timing log has not grown in this long is treated as dead: the
#: scheduler killed it without __exit__ ever running, so its status is stuck at
#: "running". Measuring its throughput against wall-clock-until-now would
#: dilute it by however many hours have passed since.
STALL_SECONDS = 15 * 60


def cumulative(run_dir: Path) -> dict:
    """Totals across *every* session, from the append-only timing log.

    ``index_summary.json`` is rewritten by each run, so a resumed index reports
    only its final session — for musique that was three restarts, and the
    headline cost of the index looked like a third of what it was. The timing
    log is appended to instead, so it survives restarts.

    ``attempts`` counts document-processing attempts, not distinct documents: a
    document retried three times contributes three. That is the honest cost of
    the index — the failed passes were paid for too.
    """
    rows = read_timing(run_dir / "index_timing.jsonl")
    if not rows:
        return {}
    attempts = sum(int(r.get("n_docs", 1)) for r in rows)
    doc_seconds = sum(float(r.get("seconds", 0.0)) for r in rows)
    return {
        "attempts": attempts,
        "total_doc_seconds": round(doc_seconds, 1),
        "total_doc_hours": round(doc_seconds / 3600, 2),
    }


def refresh_running(data: dict, run_dir: Path) -> dict:
    """Recompute a still-running run's numbers from index_timing.jsonl.

    The on-disk summary of a running job is a snapshot from its start, so the
    live view has to come from the append-only timing log.
    """
    timing_path = run_dir / "index_timing.jsonl"
    rows = read_timing(timing_path)
    if not rows:
        return data

    n_docs = sum(int(r.get("n_docs", 1)) for r in rows)
    total_chars = sum(int(r.get("chars", 0)) for r in rows)
    doc_seconds = sum(float(r.get("seconds", 0.0)) for r in rows)
    failures = sum(1 for r in rows if r.get("ok") is False)

    try:
        last_activity = timing_path.stat().st_mtime
    except OSError:
        last_activity = time.time()
    idle = time.time() - last_activity

    started_at = data.get("started_at")
    # Wall clock beats summing per-document times: with workers > 1 the latter
    # over-counts, and it ignores time spent outside measured units. For a
    # stalled run the clock stops at its last write, not at now.
    end = last_activity if idle > STALL_SECONDS else time.time()
    wall = (end - started_at) if started_at else doc_seconds

    data = dict(data)
    if idle > STALL_SECONDS:
        data["status"] = "stalled"
        data["idle_hours"] = round(idle / 3600, 2)
    data.update({
        "n_docs": n_docs,
        "total_chars": total_chars,
        "failures": failures,
        "wall_seconds": round(wall, 1),
        "docs_per_min": round(n_docs / wall * 60, 3) if wall > 0 else None,
        "chars_per_sec": round(total_chars / wall, 1) if wall > 0 else None,
        "mean_doc_seconds": round(doc_seconds / n_docs, 2) if n_docs else None,
    })
    return data


def derive(data: dict) -> dict:
    """Add the presentation-only fields: in_graph, progress, hours, eta."""
    data = dict(data)
    total = data.get("total_units")
    done = data.get("n_docs") or 0
    skipped = data.get("n_skipped") or 0
    empty = data.get("empty_docs")
    wall = data.get("wall_seconds") or 0.0

    # Corpus coverage without asking Qdrant. A --resume pass visits every unit,
    # either processing or skipping it, so once done + skipped covers the corpus
    # the only units missing from the graph are the ones that stored nothing.
    # An interrupted pass says nothing about coverage, so it gets no number.
    if total and empty is not None and done + skipped >= total:
        in_graph = total - int(empty)
        data["in_graph_docs"] = in_graph
        data["in_graph"] = f"{in_graph}/{total} ({in_graph / total * 100:.0f}%)"

    if total:
        # Units visited in THIS session. Not coverage: a resumed run that
        # skipped most of the corpus shows a small number here while holding a
        # complete graph.
        data["progress"] = f"{done}/{total} ({done / total * 100:.0f}%)"
        if data.get("status") == "running" and done and wall > 0 and total > done:
            data["eta_hours"] = round((total - done) / (done / wall) / 3600, 1)
    else:
        data["progress"] = str(done) if done else None

    if wall:
        data["wall_hours"] = round(wall / 3600, 2)
    return data


def collect_passes(paths: list[Path]) -> list[dict]:
    """One row per pass: the frozen snapshots plus the current summary.

    ``IndexTimer`` freezes ``index_summary.json`` into ``passes/passNN.json``
    before each rerun overwrites it, so this reconstructs what every pass
    achieved on its own — which is the point of rerunning at all.
    """
    rows: list[dict] = []
    for run_dir in sorted({f.parent for f in summary_files(paths)}):
        snapshots = sorted((run_dir / "passes").glob("pass*.json"))
        for index, snapshot in enumerate(snapshots, start=1):
            try:
                data = json.loads(snapshot.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"skipping {snapshot}: {exc}")
                continue
            data.setdefault("status", "done")
            data.setdefault("pass", index)
            data["path"] = str(run_dir)
            rows.append(derive(data))

        current = run_dir / "index_summary.json"
        try:
            data = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data.setdefault("status", "done")
        if data["status"] == "running":
            data = refresh_running(data, run_dir)
        # The live summary is the newest pass; snapshots only exist for the ones
        # that finished before it.
        data["pass"] = len(snapshots) + 1
        data["path"] = str(run_dir)
        rows.append(derive(data))
    return rows


def summary_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("index_summary.json")))
        elif path.name == "index_summary.json" and path.exists():
            files.append(path)
    # passes/ holds snapshots, not runs — rglob must not turn them into rows.
    return [f for f in dict.fromkeys(files) if f.parent.name != "passes"]


def collect(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for file in summary_files(paths):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"skipping {file}: {exc}")
            continue
        # Pre-status runs (written before this field existed) count as done.
        data.setdefault("status", "done")
        if data["status"] == "running":
            data = refresh_running(data, file.parent)
        # Cumulative totals for every status, not just running ones: a finished
        # index that took three restarts is exactly the case the summary hides.
        data.update(cumulative(file.parent))
        data["path"] = str(file.parent)
        rows.append(derive(data))
    return rows


def fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.1f}" if value >= 100 else f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def to_markdown(rows: list[dict], columns: list[tuple[str, str]] = COLUMNS) -> str:
    header = [label for _, label in columns]
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(key)) for key, _ in columns) + " |")
    return "\n".join(lines)


def to_csv(rows: list[dict], columns: list[tuple[str, str]] = COLUMNS) -> str:
    extra = ["model", "pass", "total_chars", "chars_per_sec", "llm_calls",
             "completion_tokens", "n_skipped", "in_graph_docs", "total_units",
             "total_doc_seconds", "triplet_shape_fixes", "entity_coverage",
             "property_coverage", "swallowed_exceptions",
             "wiped_collection_evidence", "collection_prefix", "path"]
    keys = [key for key, _ in columns]
    fields = keys + [f for f in extra if f not in keys]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(fields)
    for row in rows:
        writer.writerow([row.get(key) for key in fields])
    return buf.getvalue()


def main() -> int:
    args = parse_args()
    columns = COLUMNS
    if args.passes:
        rows = collect_passes(args.paths)
        # `model` and `pass` up front: several rows now belong to one run, and
        # engine/dataset/mode/scope repeat identically down the whole table.
        # tries/tot_h are whole-run totals — per pass that is what `docs` and
        # `wall_h` already say, so showing them empty would only puzzle.
        hide = {"engine", "dataset", "mode", "scope", "attempts", "total_doc_hours"}
        columns = [("model", "model"), ("pass", "pass")] + [
            c for c in COLUMNS if c[0] not in hide
        ]
    else:
        rows = collect(args.paths)
    if args.done_only:
        rows = [r for r in rows if r.get("status") == "done"]
    if not rows:
        print("No index_summary.json found.")
        return 1

    # Model in the key: comparing several models on one dataset is the usual
    # case, and without it those rows come out in filesystem order.
    rows.sort(key=lambda r: (str(r.get("dataset")), str(r.get("engine")),
                             str(r.get("mode")), str(r.get("model")),
                             int(r.get("pass") or 0)))
    text = (to_markdown(rows, columns) if args.format == "markdown"
            else to_csv(rows, columns))

    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {len(rows)} runs to {args.out}")
    else:
        print(text)
        # Only under the markdown table: piping CSV to stdout is a normal way to
        # use this, and prose after the rows would be parsed as more rows.
        if args.format == "markdown":
            print("\nin_graph — документов в графе (total_units - empty). "
                  "Это покрытие корпуса.")
            print("seen / docs / wall_h / s/doc / calls/doc / prompt_tok — "
                  "ТОЛЬКО последняя сессия: index_summary.json перезаписывается "
                  "каждым запуском, а --resume делит прогон на несколько.")
            print("tries / tot_h — накопительно за все сессии, из "
                  "index_timing.jsonl. tries считает попытки, а не документы: "
                  "переработанный трижды документ даёт три.")
        running = sum(1 for r in rows if r.get("status") == "running")
        stalled = sum(1 for r in rows if r.get("status") == "stalled")
        if running:
            print(f"\n{running} run(s) still going - numbers are live from index_timing.jsonl.")
        if stalled:
            print(f"{stalled} run(s) stalled (no writes for >{STALL_SECONDS // 60} min) - "
                  f"likely killed by the scheduler; rates measured up to their last write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
