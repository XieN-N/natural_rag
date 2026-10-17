"""Share of gold supporting documents present in each variant's answer context.

MuSiQue-style datasets list ``gold_doc_ids`` per question; this script checks
which of those documents appear in the context the answer was generated from
(``answers/<i>.context.json``, written with ``--save-context``). It is a
retrieval-side complement to answer correctness: it shows whether the reader
even saw what it needed.

    python runs_local/gold_recall.py base dm_h2p30_na --ids 100-497
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("variants", nargs="+")
    parser.add_argument("--dataset", default="musique")
    parser.add_argument("--index-model", default="gpt-oss-20b")
    parser.add_argument("--ids", default=None, help="Question index range, e.g. 0-99 (inclusive)")
    args = parser.parse_args()

    data_dir = REPO_ROOT / "datasets" / args.dataset
    # a document counts as present when its first 200 characters occur in the context
    corpus = {}
    for line in (data_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        corpus[doc["doc_id"]] = doc["text"].strip()[:200]
    questions = [json.loads(line) for line in (data_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    lo, hi = (int(x) for x in args.ids.split("-")) if args.ids else (0, len(questions) - 1)

    print(f"questions {lo}-{hi}")
    for variant in args.variants:
        answers = REPO_ROOT / f"generated/ragu_{args.dataset}__{variant}/{args.dataset}/{args.index_model}/answers"
        recall, complete, by_hops, missing = [], 0, {}, 0
        for i in range(lo, hi + 1):
            path = answers / f"{i}.context.json"
            if not path.exists():
                missing += 1
                continue
            context = json.loads(path.read_text(encoding="utf-8"))["context"]
            context = context[0] if context else ""
            q = questions[i]
            found = [corpus[g] in context for g in q["gold_doc_ids"]]
            share = sum(found) / len(found)
            recall.append(share)
            complete += all(found)
            by_hops.setdefault(q.get("hops"), []).append(share)
        if not recall:
            print(f"{variant:12s} no saved contexts")
            continue
        hops = "  ".join(f"{h}-hop {100 * statistics.mean(v):4.0f}%" for h, v in sorted(by_hops.items(), key=str) if h is not None)
        print(f"{variant:12s} gold recall {100 * statistics.mean(recall):5.1f}%  all gold {complete:3d}/{len(recall)}  {hops}"
              + (f"  (no context for {missing})" if missing else ""))


if __name__ == "__main__":
    main()
