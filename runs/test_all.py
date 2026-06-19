#!/usr/bin/env python
"""Test runner for all RAG pipeline scripts.

Runs each pipeline on a small dataset to verify they execute without errors.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPTS = [
    {
        "name": "fast_graphrag",
        "script": "fast_graphrag_run.py",
        "dataset": "datasets/bl_tiny",
        "extra_args": ["--build-index", "--answer", "--force"],
        "env": {},
    },
    {
        "name": "lightrag",
        "script": "lightrag_run.py",
        "dataset": "datasets/bl_tiny",
        "extra_args": ["--build-index", "--answer", "--force", "--query-mode", "naive"],
        "env": {},
    },
    {
        "name": "nano_graphrag",
        "script": "nano_graphrag_run.py",
        "dataset": "datasets/bl_tiny",
        "extra_args": ["--build-index", "--answer", "--force", "--query-mode", "naive"],
        "env": {},
    },
    {
        "name": "baseline",
        "script": "baseline_run.py",
        "dataset": "datasets/bl_tiny",
        "extra_args": ["--build-index", "--answer"],
        "env": {},
    },
    {
        "name": "ragu",
        "script": "ragu_run.py",
        "dataset": "datasets/bl_tiny",
        "extra_args": ["--build-index", "--answer", "--force", "--chunker", "simple",
            "--builder-model-name", "qwen/qwen3-vl-8b-instruct",
            "--assistant-model-name", "qwen/qwen3-vl-8b-instruct",
            "--embedding-model-name", "/data",
            "--embedding-dim", "768"],
        "env": {},
    },
    {
        "name": "ragu_2wiki",
        "script": "ragu_2wiki_run.py",
        "dataset": "datasets/2wikimultihopqa/2wikimultihopqa.json",
        "extra_args": ["--build-index", "--answer", "--force", "--limit", "50"],
        "env": {},
    },
    {
        "name": "run_custom_ragu",
        "script": "run_custom_ragu.py",
        "dataset": "datasets/2wikimultihopqa/2wikimultihopqa.json",
        "extra_args": ["--build-index", "--answer", "--force", "--limit", "50"],
        "env": {},
    },
    {
        "name": "run_hippo",
        "script": "run_hippo.py",
        "dataset": "datasets/2wikimultihopqa/2wikimultihopqa.json",
        "extra_args": ["--build-index", "--answer", "--force", "--limit", "50"],
        "env": {},
    },
    {
        "name": "run_lightrag_bioasq",
        "script": "run_lightrag_bioasq.py",
        "dataset": "datasets/bioasq",
        "extra_args": ["--dataset-dir", "datasets/bioasq",
            "--n-docs", "100",
            "--llm-model", "qwen/qwen3-vl-8b-instruct",
            "--embed-model", "/data",
            "--embedding-dim", "768"],
        "env": {},
        "skip_default_args": True,
    },
]


def run_script(
    script_info: dict[str, Any],
    output_base: Path,
    python_exe: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Run a single test script and return (success, message)."""
    name = script_info["name"]
    script = script_info["script"]
    dataset = script_info["dataset"]
    extra_args = script_info["extra_args"]
    env_vars = script_info.get("env", {})

    output_dir = output_base / f"test_{name}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    if script_info.get("skip_default_args"):
        cmd = [python_exe, f"runs/{script}"] + extra_args
    else:
        cmd = [
            python_exe,
            f"runs/{script}",
            "--dataset-path", dataset,
            "--output-dir", str(output_dir),
        ] + extra_args

    # Prepare environment
    env = os.environ.copy()
    for key, value in env_vars.items():
        if value == "${OPENAI_BASE_URL}":
            env[key] = env.get("OPENAI_BASE_URL", "")
        elif value.startswith("${"):
            env[key] = env.get(value[2:-1], "")

    # Check required env vars
    required_env = ["OPENAI_BASE_URL", "OPENAI_API_KEY"]
    missing = [v for v in required_env if not env.get(v)]
    if missing:
        return False, f"Missing required env vars: {', '.join(missing)}"

    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Command: {' '.join(cmd)}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")

    if dry_run:
        return True, "Dry run - skipped"

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            # Verify outputs
            index_dir = output_dir / Path(dataset).stem / "index"
            answers_dir = output_dir / Path(dataset).stem / "answers"
            has_index = index_dir.exists() and any(index_dir.iterdir())
            has_answers = answers_dir.exists() and any(answers_dir.glob("*.txt"))

            if has_index or has_answers:
                return True, f"OK ({elapsed:.1f}s) - index:{has_index} answers:{has_answers}"
            else:
                return False, f"No outputs generated ({elapsed:.1f}s)"
        else:
            return False, f"Exit code {result.returncode} ({elapsed:.1f}s)\nSTDERR: {result.stderr[-500:]}"

    except subprocess.TimeoutExpired:
        return False, f"Timeout after 600s"
    except Exception as e:
        return False, f"Exception: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Test all RAG pipeline scripts")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated/test_runs"),
        help="Base output directory for test runs",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use",
    )
    parser.add_argument(
        "--scripts",
        nargs="+",
        help="Specific scripts to test (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show commands without executing",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        default=[],
        help="Scripts to skip",
    )
    args = parser.parse_args()

    # Filter scripts
    scripts_to_run = SCRIPTS
    if args.scripts:
        scripts_to_run = [s for s in SCRIPTS if s["name"] in args.scripts]
    if args.skip:
        scripts_to_run = [s for s in scripts_to_run if s["name"] not in args.skip]

    print(f"Testing {len(scripts_to_run)} scripts...")
    print(f"Output directory: {args.output_dir}")
    print(f"Python: {args.python}")
    print(f"Dry run: {args.dry_run}")

    results: list[tuple[str, bool, str]] = []

    for script_info in scripts_to_run:
        success, message = run_script(script_info, args.output_dir, args.python, args.dry_run)
        results.append((script_info["name"], success, message))
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {script_info['name']}: {message}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for _, s, _ in results if s)
    failed = len(results) - passed
    for name, success, message in results:
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {name}: {message}")
    print(f"\nTotal: {len(results)}, Passed: {passed}, Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())