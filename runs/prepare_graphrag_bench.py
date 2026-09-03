"""Convert GraphRAG-Bench into this repo's JSONL dataset format.

Source: the ``GraphRAG-Bench/GraphRAG-Bench`` dataset on HuggingFace, which
ships two domains ("medical", "novel") as::

    Datasets/Corpus/<domain>.json      [{"corpus_name": ..., "context": ...}, ...]
    Datasets/Questions/<domain>_questions.json
                                       [{"id", "source", "question", "answer",
                                         "question_type", "evidence", ...}, ...]

Run on a machine with network access (the cluster login node), then copy
``datasets/graphrag_bench_<domain>/`` over::

    python runs/prepare_graphrag_bench.py --domain medical
    python runs/prepare_graphrag_bench.py --domain medical \\
        --corpus-file ./medical.json --questions-file ./medical_questions.json

Each corpus entry is one very large document (a whole textbook / novel).
Wikontic feeds a document to the LLM whole — it has no chunker — so the corpus
is split into ``--max-doc-chars`` pieces on paragraph boundaries by default.
Pass ``--max-doc-chars 0`` to keep the originals intact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

HF_REPO = "GraphRAG-Bench/GraphRAG-Bench"
CORPUS_TEMPLATE = "Datasets/Corpus/{domain}.json"
QUESTIONS_TEMPLATE = "Datasets/Questions/{domain}_questions.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--domain", choices=["medical", "novel"], default="medical")
    p.add_argument("--out-dir", type=Path, default=None,
                   help="Default: datasets/graphrag_bench_<domain>")
    p.add_argument("--corpus-file", type=Path, default=None,
                   help="Local corpus JSON (skips the download).")
    p.add_argument("--questions-file", type=Path, default=None,
                   help="Local questions JSON (skips the download).")
    p.add_argument("--max-doc-chars", type=int, default=4000,
                   help="Split corpus entries into pieces of at most this many "
                        "characters (0 = keep whole). Wikontic has no chunker.")
    return p.parse_args()


def download(domain: str, cache_dir: Path) -> tuple[Path, Path]:
    from huggingface_hub import hf_hub_download

    paths = []
    for template in (CORPUS_TEMPLATE, QUESTIONS_TEMPLATE):
        filename = template.format(domain=domain)
        print(f"Downloading {filename} from {HF_REPO} ...")
        paths.append(Path(hf_hub_download(
            repo_id=HF_REPO,
            filename=filename,
            repo_type="dataset",
            cache_dir=str(cache_dir),
        )))
    return paths[0], paths[1]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def split_text(text: str, max_chars: int) -> list[str]:
    """Split on blank lines, packing paragraphs up to ``max_chars``."""
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in text.split("\n\n"):
        if size and size + len(paragraph) + 2 > max_chars:
            pieces.append("\n\n".join(current))
            current, size = [], 0
        if len(paragraph) > max_chars:
            # A single oversized paragraph: hard-split it.
            if current:
                pieces.append("\n\n".join(current))
                current, size = [], 0
            for start in range(0, len(paragraph), max_chars):
                pieces.append(paragraph[start:start + max_chars])
            continue
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        pieces.append("\n\n".join(current))
    return [piece for piece in pieces if piece.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir or Path(f"datasets/graphrag_bench_{args.domain}")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.corpus_file and args.questions_file:
        corpus_path, questions_path = args.corpus_file, args.questions_file
    else:
        corpus_path, questions_path = download(args.domain, out_dir / ".hf_cache")

    corpus_raw = load_json(corpus_path)
    questions_raw = load_json(questions_path)

    # ── corpus ─────────────────────────────────────────────────────
    docs: list[dict] = []
    corpus_names: set[str] = set()
    for entry in corpus_raw:
        name = str(entry.get("corpus_name") or entry.get("source") or "corpus")
        context = entry.get("context") or ""
        corpus_names.add(name)
        pieces = split_text(context, args.max_doc_chars)
        for idx, piece in enumerate(pieces):
            doc_id = name if len(pieces) == 1 else f"{name}__p{idx:04d}"
            docs.append({
                "doc_id": doc_id,
                "title": name,
                "text": piece,
                "corpus_name": name,
            })

    n_docs = write_jsonl(out_dir / "corpus.jsonl", docs)

    # ── questions ──────────────────────────────────────────────────
    # `source` names the corpus, not a document, so it is kept in metadata
    # (build_graphrag_bench_input.py reads it) rather than as gold_doc_ids.
    unknown_sources: set[str] = set()
    questions: list[dict] = []
    for entry in questions_raw:
        source = str(entry.get("source", ""))
        if source and source not in corpus_names:
            unknown_sources.add(source)
        evidence = entry.get("evidence")
        questions.append({
            "id": entry.get("id"),
            "question": entry.get("question"),
            "answer": entry.get("answer"),
            "source": source,
            "question_type": entry.get("question_type"),
            "evidence": " ".join(evidence) if isinstance(evidence, list) else (evidence or ""),
        })

    n_questions = write_jsonl(out_dir / "questions.jsonl", questions)

    print(f"Wrote {n_docs} documents and {n_questions} questions to {out_dir}")
    print(f"  corpora: {sorted(corpus_names)}")
    types: dict[str, int] = {}
    for q in questions:
        types[str(q["question_type"])] = types.get(str(q["question_type"]), 0) + 1
    print(f"  question types: {types}")
    if unknown_sources:
        print(f"  WARNING: question sources absent from the corpus: {sorted(unknown_sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
