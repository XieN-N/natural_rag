"""Generate Wikontic answers on a workstation from an index exported off the cluster.

The cluster only builds graphs; answers are produced separately, by a different
model through an OpenAI-compatible API, and scored there too. This script is the
laptop half of that split.

Everything that must match the index -- graph mode, scope, collection prefix,
the label of the model that built the graph -- is read from the bundle's
``manifest.json`` rather than retyped. Getting any of them wrong does not raise:
Wikontic simply retrieves nothing and every answer comes back empty, which costs
a full dataset of API calls to discover. Hence the preflight in
:func:`check_collections`, which refuses to start when the graph is not there.

    python runs_local/answer_from_index.py \\
        --bundle ~/wikontic_bundles/wikontic_musique_dynamic \\
        --model gpt-4o-mini --short-answers

Bundle layout (produced by ``runs_cluster/export_index.sh``)::

    <bundle>/manifest.json
    <bundle>/qdrant_storage/<RUN_ID>/
    <bundle>/generated/<RUN_ID>/          index_summary.json, index_timing.jsonl
    <bundle>/datasets/<dataset>/          only when not tracked in git
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from natural_rag.dataset import RAGDataset  # noqa: E402
from natural_rag.paths import sanitize_model_name  # noqa: E402
from runs.wikontic_run import run_answers  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--bundle", type=Path, required=True,
                   help="Unpacked bundle directory (the one holding manifest.json).")
    p.add_argument("--model", default=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
                   help="Model that ANSWERS. Unrelated to the model that built "
                        "the graph, which comes from the manifest.")
    p.add_argument("--base-url",
                   default=os.environ.get("OPENAI_BASE_URL", "https://api.vsellm.ru/v1"))
    p.add_argument("--api-key",
                   default=os.environ.get("OPENAI_API_KEY") or os.environ.get("KEY"))
    p.add_argument("--dataset-path", type=Path, default=None,
                   help="Override the dataset. Default: the copy inside the "
                        "bundle, else datasets/<name> in this repo.")
    p.add_argument("--output-dir", type=Path, default=None,
                   help="Default: generated/<run_id>__<answer-model>.")
    p.add_argument("--short-answers", action=argparse.BooleanOptionalAction, default=False,
                   help="Terse-answer instruction. Use for musique / bioasq; NOT "
                        "for GraphRAG-Bench, whose Contextual Summarize and "
                        "Creative Generation levels are scored on coverage.")
    p.add_argument("--qa-collapsing", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--use-qualifiers", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--use-filtered-triplets", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hop-depth", type=int, default=5)
    p.add_argument("--save-context", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--limit-questions", type=int, default=None)
    p.add_argument("--hf-model-path", default=os.environ.get("HF_MODEL_PATH"),
                   help="Local facebook/contriever. Must be the same weights the "
                        "cluster indexed with: a different revision does not "
                        "error, it silently embeds queries into another space.")
    p.add_argument("--device", default=os.environ.get("WIKONTIC_DEVICE"))
    p.add_argument("--qdrant-bin", default=os.environ.get("QDRANT_BIN", "./qdrant"),
                   help="Qdrant binary to launch over the bundle's storage.")
    p.add_argument("--qdrant-url", default=None,
                   help="Use an already-running Qdrant instead of launching one. "
                        "Its storage must be this bundle's.")
    p.add_argument("--qdrant-timeout", type=int, default=120)
    p.add_argument("--preflight-only", action="store_true",
                   help="Check the graph and print the plan, then exit without "
                        "touching the API.")
    return p.parse_args()


# ── bundle ─────────────────────────────────────────────────────────

def load_manifest(bundle: Path) -> dict:
    manifest_path = bundle / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(
            f"No manifest.json in {bundle}.\n"
            f"Point --bundle at the directory unpacked from <RUN_ID>.tar.gz "
            f"(it contains manifest.json and qdrant_storage/)."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in ("run_id", "collection_prefix", "mode"):
        if not manifest.get(key):
            raise SystemExit(f"manifest.json is missing {key!r}")
    return manifest


def resolve_storage(bundle: Path, manifest: dict) -> Path:
    subdir = manifest.get("qdrant_storage_subdir") or f"qdrant_storage/{manifest['run_id']}"
    storage = bundle / subdir
    if not storage.is_dir():
        raise SystemExit(f"No Qdrant storage at {storage}")
    return storage


def resolve_dataset(bundle: Path, manifest: dict, override: Path | None) -> Path:
    if override:
        return override
    name = manifest.get("dataset")
    if not name:
        raise SystemExit(
            "manifest.json has no dataset name; pass --dataset-path explicitly."
        )
    in_bundle = bundle / "datasets" / name
    if in_bundle.is_dir():
        return in_bundle
    in_repo = REPO_ROOT / "datasets" / name
    if in_repo.is_dir():
        return in_repo
    raise SystemExit(
        f"Dataset {name!r} found neither in the bundle ({in_bundle}) nor in the "
        f"repo ({in_repo}). Answers are numbered by question position, so it has "
        f"to be the same dataset the cluster indexed -- copy it over rather than "
        f"regenerating it."
    )


# ── qdrant ─────────────────────────────────────────────────────────

def free_port(start: int = 16333) -> int:
    for port in range(start, start + 200):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit("No free port for Qdrant")


def start_qdrant(binary: str, storage: Path, port: int, log_path: Path):
    env = dict(os.environ)
    env.update({
        "QDRANT__SERVICE__HTTP_PORT": str(port),
        "QDRANT__SERVICE__GRPC_PORT": str(port + 10000),
        "QDRANT__SERVICE__HOST": "127.0.0.1",
        "QDRANT__STORAGE__STORAGE_PATH": str(storage),
        "QDRANT__TELEMETRY_DISABLED": "true",
        # Wikontic rebuilds an alias collection by re-upserting every payload in
        # one request, and the payload carries the 768-float embedding: a few
        # thousand aliases run past the 32 MB default and the upsert fails after
        # the collection has already been dropped. PrefixedBackend keeps that
        # rebuild from happening on answer-only runs, but when one is genuinely
        # needed it still has to fit.
        "QDRANT__SERVICE__MAX_REQUEST_SIZE_MB": "256",
    })
    log_file = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen([binary], env=env,
                                   stdout=log_file, stderr=subprocess.STDOUT)
    except FileNotFoundError:
        raise SystemExit(
            f"Qdrant binary not found: {binary}\n"
            f"Download the same build the cluster uses:\n"
            f"  curl -L -O https://github.com/qdrant/qdrant/releases/download/"
            f"v1.18.3/qdrant-x86_64-unknown-linux-musl.tar.gz\n"
            f"  tar xzf qdrant-x86_64-unknown-linux-musl.tar.gz && chmod +x ./qdrant"
        )

    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 120
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"Qdrant died on startup, see {log_path}")
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=2):
                print(f"Qdrant ready on {url} (storage {storage})")
                return process, url
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    process.terminate()
    raise SystemExit(f"Qdrant did not become healthy in 120s, see {log_path}")


def collection_points(url: str, name: str) -> int | None:
    """Point count, or None when the collection does not exist."""
    try:
        with urllib.request.urlopen(f"{url}/collections/{name}", timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return payload.get("result", {}).get("points_count")


def check_collections(url: str, manifest: dict) -> None:
    """Refuse to answer against a graph that is not there.

    A wrong ``collection_prefix`` or graph ``mode`` produces no error anywhere in
    Wikontic -- retrieval just returns nothing and every answer is empty. On a
    full dataset that is a day and a bill's worth of API calls to find out.
    """
    required = manifest.get("required_collections") or [
        f"{manifest['collection_prefix']}__{name}"
        for name in ("triplets", "initial_triplets")
    ]
    optional = manifest.get("optional_collections") or []

    print("\nPreflight: collections in Qdrant")
    problems: list[str] = []
    for name in required:
        points = collection_points(url, name)
        if points is None:
            print(f"  MISSING  {name}")
            problems.append(f"{name}: not found")
        elif points == 0:
            print(f"  EMPTY    {name}  (0 points)")
            problems.append(f"{name}: 0 points")
        else:
            print(f"  ok       {name}  ({points} points)")
    for name in optional:
        points = collection_points(url, name)
        if points is None:
            print(f"  --       {name}  (not present)")
        else:
            print(f"  ok       {name}  ({points} points)")

    if problems:
        try:
            with urllib.request.urlopen(f"{url}/collections", timeout=30) as response:
                present = [c["name"] for c in json.load(response)["result"]["collections"]]
        except Exception:
            present = []
        raise SystemExit(
            "\nThe graph this bundle claims to hold is not in Qdrant:\n  "
            + "\n  ".join(problems)
            + f"\n\nCollections actually present ({len(present)}):\n  "
            + ("\n  ".join(sorted(present)) if present else "(none)")
            + "\n\nEither collection_prefix in manifest.json does not match the "
              "index, or the storage directory in the bundle is not the one that "
              "was built. Nothing was sent to the API."
        )
    print("Preflight OK.\n")


# ── main ───────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    bundle = args.bundle.expanduser().resolve()
    manifest = load_manifest(bundle)
    storage = resolve_storage(bundle, manifest)
    dataset_path = resolve_dataset(bundle, manifest, args.dataset_path)

    run_id = manifest["run_id"]
    index_model = manifest.get("index_model")
    output_dir = args.output_dir or (
        REPO_ROOT / "generated" / f"{run_id}__{sanitize_model_name(args.model)}"
    )

    print(f"run_id       : {run_id}")
    print(f"dataset      : {dataset_path}")
    print(f"graph        : mode={manifest['mode']} scope={manifest.get('scope')} "
          f"prefix={manifest['collection_prefix']}")
    print(f"index model  : {index_model}   (built the graph)")
    print(f"answer model : {args.model} @ {args.base_url}")
    print(f"output       : {output_dir}")
    if manifest.get("empty_docs"):
        print(f"WARNING: {manifest['empty_docs']} document(s) never made it into "
              f"this graph during indexing — answers sourced from them cannot "
              f"succeed no matter which model answers")

    process = None
    try:
        if args.qdrant_url:
            url = args.qdrant_url.rstrip("/")
        else:
            log_path = bundle / "qdrant.log"
            process, url = start_qdrant(args.qdrant_bin, storage, free_port(), log_path)

        check_collections(url, manifest)
        if args.preflight_only:
            print("--preflight-only: stopping before the API.")
            return 0

        if not args.api_key:
            raise SystemExit("No API key: set OPENAI_API_KEY or pass --api-key.")

        # Imported late: constructing the pipeline loads contriever, and there is
        # no reason to pay for that before the graph has been verified.
        from natural_rag.paths import resolve_run_dirs
        from natural_rag.pipelines.wikontic_pipeline import WikonticPipeline

        _, answers_dir, _ = resolve_run_dirs(output_dir, dataset_path, index_model)
        dataset = RAGDataset.load_auto(dataset_path)
        questions = dataset.questions
        if args.limit_questions:
            questions = questions[: args.limit_questions]

        pipeline = WikonticPipeline(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            mode=manifest["mode"],
            backend_type="qdrant",
            qdrant_url=url,
            qdrant_timeout=args.qdrant_timeout,
            collection_prefix=manifest["collection_prefix"],
            hop_depth=args.hop_depth,
            use_qualifiers=args.use_qualifiers,
            use_filtered_triplets=args.use_filtered_triplets,
            hf_model_path=args.hf_model_path,
            device=args.device,
        )

        stats = run_answers(
            pipeline,
            questions,
            answers_dir,
            scope=manifest.get("scope") or "corpus",
            qa_collapsing=args.qa_collapsing,
            short_answers=args.short_answers,
            save_context=args.save_context,
            force=args.force,
        )
        print(f"\n{json.dumps(stats, indent=2)}")
        print(f"Answers in {answers_dir}")
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
