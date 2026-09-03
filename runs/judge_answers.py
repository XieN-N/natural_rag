"""Score ``answers/<i>.txt`` produced by any engine in this repo.

Works off the shared run layout (``natural_rag.paths.resolve_run_dirs``), so the
same command scores Wikontic and RAGU runs and the numbers are comparable.

Reports three things per run:

* ``em``  — exact match after normalisation (lowercase, strip articles/punct)
* ``f1``  — token-level F1 against the best-matching reference answer
* ``judge_accuracy`` — fraction an LLM judge marks factually correct

EM/F1 need no LLM. Pass ``--no-judge`` to skip the model entirely.

    python runs/judge_answers.py \
        --dataset-path datasets/musique \
        --output-dir generated/wikontic_musique --index-model gigachat \
        --judge-model Qwen2.5-14B-Instruct
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import string
from collections import Counter
from pathlib import Path
from typing import Any

from natural_rag.dataset import RAGDataset
from natural_rag.paths import dataset_name_from_path, resolve_run_dirs

JUDGE_PROMPT = """You are grading a question-answering system.

Question: {question}
Reference answer(s): {references}
System answer: {answer}

Is the system answer factually correct with respect to the reference answer(s)?
Ignore differences in wording, length and formatting; judge only the facts.
An answer that is missing part of a required list is incorrect.

Reply with JSON only: {{"correct": true or false, "reason": "<one short sentence>"}}"""


# ── normalisation & lexical metrics (SQuAD-style) ──────────────────

def normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def exact_match(answer: str, references: list[str]) -> float:
    normalized = normalize(answer)
    return float(any(normalized == normalize(ref) for ref in references))


def token_f1(answer: str, references: list[str]) -> float:
    best = 0.0
    answer_tokens = normalize(answer).split()
    for ref in references:
        ref_tokens = normalize(ref).split()
        common = Counter(answer_tokens) & Counter(ref_tokens)
        overlap = sum(common.values())
        if overlap == 0:
            continue
        precision = overlap / len(answer_tokens)
        recall = overlap / len(ref_tokens)
        best = max(best, 2 * precision * recall / (precision + recall))
    return best


# ── LLM judge ──────────────────────────────────────────────────────

def parse_judge_reply(content: str) -> tuple[bool | None, str]:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None, content.strip()[:200]
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None, content.strip()[:200]
    correct = data.get("correct")
    if isinstance(correct, str):
        correct = correct.strip().lower() in ("true", "yes", "1")
    return (bool(correct) if correct is not None else None), str(data.get("reason", ""))[:300]


async def judge_all(
    rows: list[dict[str, Any]],
    model: str,
    base_url: str,
    api_key: str,
    concurrency: int,
) -> None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    semaphore = asyncio.Semaphore(concurrency)

    async def judge(row: dict[str, Any]) -> None:
        prompt = JUDGE_PROMPT.format(
            question=row["question"],
            references=" | ".join(row["references"]) or "(none)",
            answer=row["answer"],
        )
        async with semaphore:
            for attempt in range(3):
                try:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0,
                    )
                    correct, reason = parse_judge_reply(response.choices[0].message.content or "")
                    row["judge_correct"] = correct
                    row["judge_reason"] = reason
                    return
                except Exception as exc:  # network hiccup / rate limit
                    if attempt == 2:
                        row["judge_correct"] = None
                        row["judge_reason"] = f"judge failed: {type(exc).__name__}: {exc}"
                    else:
                        await asyncio.sleep(2)

    done = 0
    tasks = [asyncio.create_task(judge(row)) for row in rows]
    for task in asyncio.as_completed(tasks):
        await task
        done += 1
        if done % 25 == 0 or done == len(tasks):
            print(f"  judged {done}/{len(tasks)}", flush=True)


# ── aggregation ────────────────────────────────────────────────────

def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean EM / F1 / judge accuracy over ``rows``.

    Questions without reference answers carry ``em is None`` and are excluded
    from the lexical means but still counted in ``n``, so the denominators are
    visible rather than implied.
    """
    scored = [r for r in rows if r["em"] is not None]
    judged = [r for r in rows if r.get("judge_correct") is not None]
    return {
        "n": len(rows),
        "n_scored": len(scored),
        "em": round(sum(r["em"] for r in scored) / len(scored), 4) if scored else None,
        "f1": round(sum(r["f1"] for r in scored) / len(scored), 4) if scored else None,
        "n_judged": len(judged),
        "judge_accuracy": (
            round(sum(1 for r in judged if r["judge_correct"]) / len(judged), 4) if judged else None
        ),
    }


# ── main ───────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset-path", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True,
                   help="The generated/<engine>_<dataset> dir used when answering.")
    p.add_argument("--index-model", default=os.environ.get("INDEX_MODEL"))
    p.add_argument("--judge", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL_NAME", "gpt-4o-mini"))
    p.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    p.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "token-abc123"))
    p.add_argument("--concurrency", type=int, default=int(os.environ.get("JUDGE_CONCURRENCY", "8")))
    p.add_argument("--group-by", default="question_type",
                   help="Question-metadata field to break the scores down by. "
                        "GraphRAG-Bench ships question_type (Fact Retrieval / "
                        "Complex Reasoning / Contextual Summarize / Creative "
                        "Generation) and grades each differently, so a single "
                        "average hides the interesting part. Silently ignored "
                        "when the field is absent; pass '' to disable.")
    p.add_argument("--out", type=Path, default=None,
                   help="Where to write eval_results.json (default: next to answers/).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dataset = RAGDataset.load_auto(args.dataset_path)
    dataset_name = dataset_name_from_path(args.dataset_path)
    _, answers_dir, base_dir = resolve_run_dirs(args.output_dir, args.dataset_path, args.index_model)

    rows: list[dict[str, Any]] = []
    missing = 0
    for q_idx, question in enumerate(dataset.questions):
        answer_path = answers_dir / f"{q_idx}.txt"
        if not answer_path.exists():
            missing += 1
            continue
        answer = answer_path.read_text(encoding="utf-8").strip()
        references = question.reference_answers or []
        references = list(references) + list(question.metadata.get("answer_aliases") or [])
        rows.append({
            "q_idx": q_idx,
            "group": str(question.metadata.get(args.group_by)) if args.group_by
                     and question.metadata.get(args.group_by) is not None else None,
            "question": question.text,
            "references": [str(r) for r in references],
            "answer": answer,
            "em": exact_match(answer, [str(r) for r in references]) if references else None,
            "f1": token_f1(answer, [str(r) for r in references]) if references else None,
        })

    if not rows:
        print(f"No answers found in {answers_dir}")
        return 1
    print(f"{len(rows)} answers, {missing} missing, dataset={dataset_name}")

    if args.judge:
        print(f"Judging with {args.judge_model} at {args.base_url}")
        asyncio.run(judge_all(rows, args.judge_model, args.base_url, args.api_key, args.concurrency))

    summary = {
        "dataset": dataset_name,
        "output_dir": str(base_dir),
        "index_model": args.index_model,
        "n_questions": len(dataset.questions),
        "n_answers": len(rows),
        "n_missing": missing,
        **aggregate(rows),
        "judge_model": args.judge_model if args.judge else None,
    }

    groups = sorted({r["group"] for r in rows if r["group"] is not None})
    if groups:
        summary["group_by"] = args.group_by
        summary["by_group"] = {
            group: aggregate([r for r in rows if r["group"] == group]) for group in groups
        }

    out_path = args.out or (base_dir / "eval_results.json")
    out_path.write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
