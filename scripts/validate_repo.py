"""Cheap repository self-check: no GPU, no LLM calls, seconds to run.

Verifies three things:

1. Every benchmark from ``natural_rag.benchmarks`` loads through
   ``RAGDataset.load_auto`` (format detected, documents/questions counted and
   cross-checked against the registry). Benchmarks marked ``in_repo=False``
   are checked only when their directory exists.
2. Every ``.py`` file in the script directories compiles (``py_compile``).
3. Every ``.sh`` file passes ``bash -n`` syntax check.

Usage::

    python scripts/validate_repo.py                 # всё
    python scripts/validate_repo.py --skip-loaders  # только компиляция
    python scripts/validate_repo.py --dataset bl_tiny
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from natural_rag.benchmarks import BENCHMARKS  # noqa: E402

PY_DIRS = ["natural_rag", "runs", "runs_cluster", "runs_local", "scripts"]
SH_DIRS = ["runs_cluster"]


def check_benchmarks(only: str | None) -> list[tuple[str, bool, str]]:
    from natural_rag.dataset import RAGDataset

    results: list[tuple[str, bool, str]] = []
    for name, bench in BENCHMARKS.items():
        if only and name != only:
            continue
        path = PROJECT_ROOT / bench.path
        if not path.exists():
            if bench.in_repo:
                results.append((name, False, f"missing: {bench.path}"))
            else:
                results.append((name, True, "not installed (optional, see docs/benchmarks.md)"))
            continue
        try:
            dataset = RAGDataset.load_auto(path)
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            results.append((name, False, f"load failed: {type(exc).__name__}: {exc}"))
            continue
        n_docs = len(dataset.documents)
        n_questions = len(dataset.questions)
        msg = f"OK: {n_docs} docs, {n_questions} questions"
        if bench.in_repo and (n_docs, n_questions) != (bench.docs, bench.questions):
            msg += (
                f" [REGISTRY MISMATCH: expected {bench.docs} docs,"
                f" {bench.questions} questions — update natural_rag/benchmarks.py]"
            )
            results.append((name, False, msg))
            continue
        results.append((name, True, msg))
    return results


def check_python_compiles() -> list[tuple[str, bool, str]]:
    import ast

    results: list[tuple[str, bool, str]] = []
    for dir_name in PY_DIRS:
        for py_file in sorted((PROJECT_ROOT / dir_name).glob("*.py")):
            try:
                ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError as exc:
                results.append((str(py_file.relative_to(PROJECT_ROOT)), False, str(exc)))
            else:
                results.append((str(py_file.relative_to(PROJECT_ROOT)), True, "syntax OK"))
    return results


def check_shell_syntax() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    bash = shutil.which("bash")
    if bash is None:
        return [("bash", False, "bash not found — shell scripts not checked")]
    for dir_name in SH_DIRS:
        for sh_file in sorted((PROJECT_ROOT / dir_name).glob("*.sh")):
            proc = subprocess.run(
                [bash, "-n", str(sh_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            rel = str(sh_file.relative_to(PROJECT_ROOT))
            if proc.returncode == 0:
                results.append((rel, True, "syntax OK"))
            else:
                results.append((rel, False, proc.stderr.strip()[:300]))
    return results


def report(title: str, results: list[tuple[str, bool, str]]) -> bool:
    print(f"\n=== {title} ===")
    ok = True
    for name, passed, message in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            ok = False
        print(f"  [{status}] {name}: {message}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-loaders", action="store_true",
                        help="Skip dataset loading (compile/syntax checks only).")
    parser.add_argument("--dataset", default=None,
                        help="Check a single benchmark by name.")
    parser.add_argument("--skip-shell", action="store_true",
                        help="Skip bash -n checks (e.g. on hosts without bash).")
    args = parser.parse_args()

    all_ok = True
    if not args.skip_loaders:
        all_ok &= report("Benchmark loaders", check_benchmarks(args.dataset))
    all_ok &= report("Python compile", check_python_compiles())
    if not args.skip_shell:
        all_ok &= report("Shell syntax", check_shell_syntax())

    print("\nRESULT:", "OK" if all_ok else "FAILURES DETECTED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
