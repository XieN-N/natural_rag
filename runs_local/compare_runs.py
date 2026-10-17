"""Paired comparison of RAGU answer variants on the same questions.

Each variant lives in ``generated/ragu_<dataset>__<variant>/<dataset>/<index-model>/``
(as written by ``runs_local/run_musique_variant.sh``) with ``eval_results*.json``
from ``runs_local/eval_graphrag_bench.sh``. Answer correctness is averaged over
all judge passes of a variant. Every variant is compared with the first one:
mean paired difference, 95% paired bootstrap interval, two-sided bootstrap
p-value with Holm correction, and how many questions got better or worse.
A second table reports latency per stage and generation cost per question,
read from ``answers/<i>.context.json`` (``--save-context``).

    python runs_local/compare_runs.py base base_na dm_h2p30_na --ids 100-497
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import string
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("variants", nargs="+", help="Baseline first, then the variants to compare with it")
    parser.add_argument("--dataset", default="musique")
    parser.add_argument("--index-model", default="gpt-oss-20b")
    parser.add_argument("--ids", default=None, help="Question index range, e.g. 100-497 (inclusive)")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument(
        "--rub-per-m-tokens", type=float, default=14.0,
        help="Input price of the answering/decision model per 1M tokens (gpt-4o-mini via vsellm ~14)",
    )
    parser.add_argument(
        "--answer-prompt-overhead", type=int, default=150,
        help="Tokens of the answer prompt around the context",
    )
    return parser.parse_args()


def norm(text: str) -> str:
    text = text.lower()
    text = "".join(c for c in text if c not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def mean_of(values) -> float:
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else float("nan")


def pct(values, q: float) -> float:
    values = sorted(v for v in values if v is not None)
    return values[min(len(values) - 1, int(q * len(values)))] if values else float("nan")


def load(run: Path, index_of: dict[str, int]) -> dict:
    passes = [p for p in sorted(run.glob("eval_results*.json")) if "partial" not in p.name]
    per_q: dict[str, dict] = {}
    for path in passes:
        for section in json.loads(path.read_text(encoding="utf-8")).values():
            for item in section.get("detailed", []):
                metrics = item.get("metrics", item)
                entry = per_q.setdefault(item["id"], {"ac": [], "rouge": [], "answer": item.get("generated_answer", "")})
                entry["ac"].append(float(metrics.get("answer_correctness", 0.0)))
                entry["rouge"].append(float(metrics.get("rouge_score", 0.0)))
    tokens, seconds, calls, timing, dm_chars = {}, {}, {}, {}, {}
    for qid in per_q:
        path = run / "answers" / f"{index_of.get(qid, -1)}.context.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        metrics = data.get("metrics") or {}
        n = sum(s.get("n_calls", 0) for s in (metrics.get("selection") or {}).values())
        n += sum(h[k]["n_calls"] for h in metrics.get("selection_hops", []) for k in ("entities", "relations", "chunks"))
        usage = metrics.get("decision_usage")
        tokens[qid] = data.get("context_tokens")
        seconds[qid] = data.get("answer_seconds")
        calls[qid] = n
        timing[qid] = metrics.get("timing") or {}
        dm_chars[qid] = usage.get("prompt_chars") if usage else (0 if n == 0 else None)
    return {"q": per_q, "tokens": tokens, "seconds": seconds, "calls": calls,
            "timing": timing, "dm_chars": dm_chars, "passes": len(passes)}


def main() -> None:
    args = parse_args()
    questions_path = REPO_ROOT / "datasets" / args.dataset / "questions.jsonl"
    questions = [json.loads(line) for line in (questions_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    index_of = {q["id"]: i for i, q in enumerate(questions)}

    runs = {
        v: load(REPO_ROOT / f"generated/ragu_{args.dataset}__{v}/{args.dataset}/{args.index_model}", index_of)
        for v in args.variants
    }
    common = set.intersection(*(set(r["q"]) for r in runs.values()))
    if args.ids:
        lo, hi = (int(x) for x in args.ids.split("-"))
        common = {q for q in common if lo <= index_of.get(q, -1) <= hi}
    common = sorted(common, key=lambda q: index_of.get(q, -1))
    print(f"questions in common: {len(common)}" + (f" (ids {args.ids})" if args.ids else ""))
    if not common:
        return

    def em(qid: str, answer: str) -> int:
        q = questions[index_of[qid]]
        golds = [q.get("answer", "")] + list(q.get("answer_aliases") or [])
        parts = [norm(p) for p in answer.split(";")] + [norm(answer)]
        return int(any(norm(g) and norm(g) in parts for g in golds))

    for v, r in runs.items():
        ac = [statistics.mean(r["q"][q]["ac"]) for q in common]
        rouge = [statistics.mean(r["q"][q]["rouge"]) for q in common]
        ems = sum(em(q, r["q"][q]["answer"]) for q in common)
        idk = sum(1 for q in common if "don't know" in r["q"][q]["answer"].lower())
        by_hops: dict = {}
        for q, a in zip(common, ac):
            by_hops.setdefault(questions[index_of[q]].get("hops"), []).append(a)
        hops = " ".join(f"{h}h:{100 * statistics.mean(x):.1f}" for h, x in sorted(by_hops.items(), key=str) if h is not None)
        print(f"{v:12s} AC {100 * statistics.mean(ac):5.1f} ({r['passes']} eval files)  ROUGE-L {100 * statistics.mean(rouge):5.1f}  "
              f"EM {ems:3d}  IDK {idk:3d}  ctx {mean_of([r['tokens'].get(q) for q in common]):6.0f}  [{hops}]")

    base = args.variants[0]
    rng = random.Random(42)
    results = []
    for v in args.variants[1:]:
        diffs = [statistics.mean(runs[v]["q"][q]["ac"]) - statistics.mean(runs[base]["q"][q]["ac"]) for q in common]
        observed = statistics.mean(diffs)
        boots = sorted(statistics.mean(diffs[rng.randrange(len(diffs))] for _ in diffs) for _ in range(args.bootstrap))
        lo_ci, hi_ci = boots[int(0.025 * args.bootstrap)], boots[int(0.975 * args.bootstrap)]
        centred = [b - observed for b in boots]
        p = min(1.0, 2 * min(sum(1 for c in centred if c >= abs(observed)),
                             sum(1 for c in centred if c <= -abs(observed))) / args.bootstrap)
        results.append([v, observed, lo_ci, hi_ci, p, sum(d > 0.05 for d in diffs), sum(d < -0.05 for d in diffs)])

    running = 0.0
    for rank, i in enumerate(sorted(range(len(results)), key=lambda i: results[i][4])):
        running = max(running, min(1.0, (len(results) - rank) * results[i][4]))
        results[i].append(running)
    for v, observed, lo_ci, hi_ci, p, better, worse, p_holm in results:
        print(f"{v} - {base}: AC {100 * observed:+.1f} pp, 95% CI [{100 * lo_ci:+.1f}, {100 * hi_ci:+.1f}], "
              f"p={p:.3f}, Holm p={p_holm:.3f}; better {better}, worse {worse}")

    print("\nlatency (s per question) and generation cost:")
    print(f"{'variant':12s} {'mean':>5s} {'med':>5s} {'p90':>5s} | {'retr':>5s} {'select':>6s} {'hops':>5s} {'ppr':>5s} {'gen':>5s} | "
          f"{'dm calls':>8s} {'dm tok':>7s} {'ans tok':>7s} {'RUB/q':>6s}")
    cost = {}
    for v, r in runs.items():
        secs = [r["seconds"].get(q) for q in common]
        stage = {k: mean_of([r["timing"].get(q, {}).get(k, 0.0) for q in common])
                 for k in ("retrieve", "select", "hops", "ppr", "generate")}
        dm_chars = [r["dm_chars"].get(q) for q in common]
        known = all(c is not None for c in dm_chars)
        dm_tok = mean_of(dm_chars) / 4 if known else float("nan")  # ~4 characters per token
        ans_tok = mean_of([r["tokens"].get(q) for q in common]) + args.answer_prompt_overhead
        cost[v] = (ans_tok + (dm_tok if known else 0.0)) * args.rub_per_m_tokens / 1e6 if known else None
        print(f"{v:12s} {mean_of(secs):5.1f} {pct(secs, 0.5):5.1f} {pct(secs, 0.9):5.1f} | "
              f"{stage['retrieve']:5.2f} {stage['select']:6.2f} {stage['hops']:5.2f} {stage['ppr']:5.2f} {stage['generate']:5.2f} | "
              f"{mean_of([r['calls'].get(q) for q in common]):8.0f} {dm_tok:7.0f} {ans_tok:7.0f} "
              + (f"{cost[v]:6.3f}" if cost[v] is not None else "     -  (decision tokens not recorded)"))
    print("\nTimings are only comparable between runs with separate LLM caches that ran one at a time.")


if __name__ == "__main__":
    main()
