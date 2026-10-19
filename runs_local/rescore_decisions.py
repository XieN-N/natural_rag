"""Re-score harvested decision prompts with another model, the same way RAGU reads them.

Sends every prompt of ``runs_local/harvest_decisions.py`` output through
``CachedAsyncOpenAI.option_probabilities`` (one greedy token, top-20 logprobs,
"Y" and " Y" summed), so the probabilities equal what a LocalSearch run with
that model would see. The result keeps all input columns and adds ``p_score``
for ``runs_local/calibration_report.py --score p_score``.

    python runs_local/rescore_decisions.py --base-url http://127.0.0.1:8711/v1 --model meno-brier \
        --ids 100-497 decisions_musique.jsonl --out rescored_musique.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ragu.common.logger import logger
from ragu.models.openai import CachedAsyncOpenAI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ids", default=None, help="Question range, e.g. 100-497")
    parser.add_argument("--concurrency", type=int, default=64)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logger.remove()
    rows = []
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f]
    if args.ids:
        lo, hi = (int(x) for x in args.ids.split("-"))
        rows = [r for r in rows if lo <= r["question"] <= hi]
    client = CachedAsyncOpenAI(base_url=args.base_url, api_key="local", cache=None,
                               rate_min_delay=0, rate_max_simultaneous=args.concurrency)
    done = 0

    async def score(row: dict) -> None:
        nonlocal done
        masses = await client.option_probabilities(args.model, row["messages"], ["Y", "N"], top_logprobs=20)
        m_y, m_n = masses["Y"], masses["N"]
        row["p_score"] = m_y / (m_y + m_n) if m_y + m_n > 0 else None
        row["score_mass"] = m_y + m_n
        row["score_model"] = args.model
        done += 1
        if done % 5000 == 0:
            print(f"{done}/{len(rows)}", flush=True)

    await asyncio.gather(*(score(r) for r in rows))
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    missing = sum(1 for r in rows if r["p_score"] is None)
    print(f"scored {len(rows)} prompts with {args.model}; degraded {missing}")


if __name__ == "__main__":
    asyncio.run(main())
