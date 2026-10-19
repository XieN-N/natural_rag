"""Calibration and ranking quality of decision-model probabilities on labeled prompts.

Reads the JSON lines of ``runs_local/harvest_decisions.py`` (or the same rows with
a ``p_score`` column from a re-scoring run) and reports, per candidate kind and
hop: base rate, Brier score, log loss, expected calibration error (10 equal-width
bins), AUROC, area under the risk-coverage curve and coverage at a precision
target. Platt scaling (logistic regression on the logit of P(Y)) is fitted on
the dev questions and applied to the test questions; it is monotone, so it
changes calibration but never the ranking.

    python runs_local/calibration_report.py decisions_musique.jsonl --dev 0-99 --test 100-497
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict

import numpy as np

EPS = 1e-6  # clip for the log loss
LOGIT_EPS = 1e-15  # clip for Platt's logit; larger values tie distinct tiny probabilities


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+")
    parser.add_argument("--score", default="p_yes", help="Column with P(Y): p_yes (cached run) or p_score (re-scored)")
    parser.add_argument("--dev", default=None, help="Question range for Platt fitting, e.g. 0-99")
    parser.add_argument("--test", default=None, help="Question range to report on, e.g. 100-497")
    parser.add_argument("--precision", type=float, default=0.8, help="Precision target for coverage@precision")
    return parser.parse_args()


def in_range(q: int, spec: str | None) -> bool:
    if spec is None:
        return True
    lo, hi = (int(x) for x in spec.split("-"))
    return lo <= q <= hi


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, LOGIT_EPS, 1 - LOGIT_EPS)
    return np.log(p / (1 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    return np.exp(-np.logaddexp(0.0, -x))


def platt_loss(a: float, b: float, z: np.ndarray, y: np.ndarray, l2: float) -> float:
    x = a * z + b
    # log loss of sigmoid(x), written stably
    return float(np.mean(y * np.logaddexp(0.0, -x) + (1 - y) * np.logaddexp(0.0, x)) + l2 * a * a)


def fit_platt(p: np.ndarray, y: np.ndarray, steps: int = 200, l2: float = 1e-4) -> tuple[float, float]:
    """a, b of sigmoid(a * logit(p) + b): damped Newton on log loss with a small L2 on a.

    Probabilities near 0 or 1 make the data almost separable in logit space, which
    sends an undamped Newton step to infinity; the line search keeps every step a descent.
    """
    z = logit(p)
    a, b = 1.0, 0.0
    n = len(z)
    loss = platt_loss(a, b, z, y, l2)
    for _ in range(steps):
        q = sigmoid(a * z + b)
        g = np.array([np.sum((q - y) * z) / n + 2 * l2 * a, np.sum(q - y) / n])
        w = q * (1 - q) / n
        h = np.array([[np.sum(w * z * z) + 2 * l2, np.sum(w * z)], [np.sum(w * z), np.sum(w)]]) + 1e-12 * np.eye(2)
        step = np.linalg.solve(h, g)
        t = 1.0
        while t > 1e-6:
            na, nb = a - t * step[0], b - t * step[1]
            new = platt_loss(na, nb, z, y, l2)
            if new <= loss:
                break
            t /= 2
        if t <= 1e-6 or loss - new < 1e-12:
            break
        a, b, loss = na, nb, new
    return float(a), float(b)


def apply_platt(p: np.ndarray, ab: tuple[float, float]) -> np.ndarray:
    return sigmoid(ab[0] * logit(p) + ab[1])


def auroc(p: np.ndarray, y: np.ndarray) -> float:
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    values = np.concatenate([pos, neg])[order]
    # average ranks for ties
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def metrics(p: np.ndarray, y: np.ndarray, precision: float) -> dict[str, float]:
    order = np.argsort(-p, kind="mergesort")
    hits = np.cumsum(y[order])
    k = np.arange(1, len(p) + 1)
    prec = hits / k
    # risk-coverage: risk of keeping the top-k candidates = share of non-useful among them
    aurc = float(np.mean(1 - prec))
    ok = np.where(prec >= precision)[0]
    cov = float((ok.max() + 1) / len(p)) if len(ok) else 0.0
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean() for b in range(10) if (bins == b).any())
    pc = np.clip(p, EPS, 1 - EPS)
    return {
        "n": len(p), "rate": float(y.mean()), "mean_p": float(p.mean()),
        "brier": float(np.mean((p - y) ** 2)),
        "nll": float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))),
        "ece": float(ece), "auroc": auroc(p, y), "aurc": aurc, "cov": cov,
    }


def main() -> None:
    args = parse_args()
    rows = []
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f]
    rows = [r for r in rows if r.get(args.score) is not None]
    dev = [r for r in rows if args.dev and in_range(r["question"], args.dev)]
    test = [r for r in rows if in_range(r["question"], args.test)]
    platt = None
    if dev:
        platt = fit_platt(np.array([r[args.score] for r in dev]), np.array([r["label"] for r in dev], dtype=float))
        print(f"Platt on dev {args.dev}: a={platt[0]:.3f} b={platt[1]:.3f} (n={len(dev)})")

    groups: dict[str, list] = defaultdict(list)
    for r in test:
        groups["all"].append(r)
        groups[r["kind"]].append(r)
        groups[f"{r['kind']} hop{r['hop']}"].append(r)
    print(f"test {args.test or 'all'}: {len(test)} prompts; coverage at precision {args.precision}")
    header = f"{'group':16s} {'n':>6s} {'rate':>5s} | {'mean p':>6s} {'Brier':>6s} {'NLL':>6s} {'ECE':>6s} | {'AUROC':>5s} {'AURC':>5s} {'cov':>5s}"
    for name, transform in (("raw", None), ("Platt", platt)):
        if name == "Platt" and transform is None:
            continue
        print(f"\n[{name}]\n{header}")
        for g in sorted(groups, key=lambda s: (s != "all", s)):
            p = np.array([r[args.score] for r in groups[g]])
            y = np.array([r["label"] for r in groups[g]], dtype=float)
            if transform is not None:
                p = apply_platt(p, transform)
            m = metrics(p, y, args.precision)
            print(f"{g:16s} {m['n']:6d} {m['rate']:5.2f} | {m['mean_p']:6.3f} {m['brier']:6.4f} {m['nll']:6.3f} "
                  f"{m['ece']:6.3f} | {m['auroc']:5.3f} {m['aurc']:5.3f} {m['cov']:5.2f}")
    if platt is not None:
        print("\nraw threshold equivalent to a calibrated threshold t: sigmoid((logit(t) - b) / a)")
        for t in (0.1, 0.2, 0.3, 0.5):
            raw = 1 / (1 + math.exp(-((math.log(t / (1 - t)) - platt[1]) / platt[0])))
            print(f"  t={t:.1f} -> raw {raw:.4f}")


if __name__ == "__main__":
    main()
