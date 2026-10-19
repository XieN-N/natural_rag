"""Train a LoRA adapter so that a decision model's Y/N readout minimizes the Brier score.

This is the direct-scorer case of OpenJev-RLCD (arXiv 2609.38850): no rationale,
the answer distribution is read from the first token and trained with a strictly
proper scoring rule. The readout matches inference exactly: P(Y) is the
probability mass of the "Y" and " Y" tokens divided by the mass of "Y", " Y",
"N" and " N" at the first answer position, the same sum that
``CachedAsyncOpenAI.option_probabilities`` takes over ``top_logprobs``. A small
penalty on -log(mass of the label tokens) keeps the mass on them, otherwise a
request could come back degraded (no label in the top 20).

Positives are not oversampled (that would break calibration). Input rows come
from ``runs_local/harvest_decisions.py``.

    python runs_local/train_brier_readout.py --model /path/meno-lite-0.1 \
        --train decisions_2wiki.jsonl --train-ids 0-449 --val-ids 450-499 --out adapters/meno-brier
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--train", nargs="+", required=True, help="Harvested JSON lines")
    parser.add_argument("--train-ids", required=True, help="Question range used for training, e.g. 0-449")
    parser.add_argument("--val-ids", required=True, help="Question range for validation, e.g. 450-499")
    parser.add_argument("--out", required=True)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--batch-tokens", type=int, default=24000, help="Padded tokens per optimizer step")
    parser.add_argument("--max-len", type=int, default=4096)
    parser.add_argument("--mass-penalty", type=float, default=0.1)
    parser.add_argument("--max-train", type=int, default=0, help="Cap on training prompts (0 = all)")
    parser.add_argument("--val-max", type=int, default=3000)
    parser.add_argument("--eval-every", type=int, default=200, help="Optimizer steps between validations")
    parser.add_argument("--check-base", type=int, default=200, help="Prompts to compare base P(Y) with the cache")
    parser.add_argument("--seed", type=int, default=17)
    return parser.parse_args()


def in_range(q: int, spec: str) -> bool:
    lo, hi = (int(x) for x in spec.split("-"))
    return lo <= q <= hi


def label_ids(tokenizer) -> tuple[list[int], list[int]]:
    ids = {}
    for label in ("Y", "N"):
        found = []
        for variant in (label, f" {label}"):
            enc = tokenizer.encode(variant, add_special_tokens=False)
            if len(enc) == 1:
                found.append(enc[0])
        assert found, f"label {label!r} is not a single token"
        ids[label] = found
    return ids["Y"], ids["N"]


def encode(tokenizer, rows, max_len):
    out = []
    for r in rows:
        ids = tokenizer.apply_chat_template(r["messages"], add_generation_prompt=True, tokenize=True)
        if len(ids) > max_len:
            continue
        out.append((ids, float(r["label"]), r.get("p_yes")))
    return out


def batches(items, batch_tokens, shuffle, rng):
    order = sorted(range(len(items)), key=lambda i: len(items[i][0]))
    groups, cur, cur_max = [], [], 0
    for i in order:
        n = len(items[i][0])
        if cur and max(cur_max, n) * (len(cur) + 1) > batch_tokens:
            groups.append(cur)
            cur, cur_max = [], 0
        cur.append(i)
        cur_max = max(cur_max, n)
    if cur:
        groups.append(cur)
    if shuffle:
        rng.shuffle(groups)
    return groups


def readout(model, items, idx, y_ids, n_ids, pad_id, device):
    seqs = [items[i][0] for i in idx]
    longest = max(len(s) for s in seqs)
    input_ids = torch.full((len(seqs), longest), pad_id, dtype=torch.long)
    attention = torch.zeros((len(seqs), longest), dtype=torch.long)
    for j, s in enumerate(seqs):
        input_ids[j, : len(s)] = torch.tensor(s)
        attention[j, : len(s)] = 1
    input_ids, attention = input_ids.to(device), attention.to(device)
    logits = model(input_ids=input_ids, attention_mask=attention).logits
    last = attention.sum(1) - 1
    lp = torch.log_softmax(logits[torch.arange(len(seqs), device=device), last].float(), dim=-1)
    # in log space: m_y / (m_y + m_n) is 0/0 once both masses underflow
    log_y = torch.logsumexp(lp[:, y_ids], dim=-1)
    log_n = torch.logsumexp(lp[:, n_ids], dim=-1)
    return torch.sigmoid(log_y - log_n), torch.logaddexp(log_y, log_n)


@torch.no_grad()
def evaluate(model, items, y_ids, n_ids, pad_id, device, batch_tokens):
    model.eval()
    # batches are sorted by length; put the probabilities back in item order
    ps: list[float] = [0.0] * len(items)
    for idx in batches(items, batch_tokens, False, None):
        p, _ = readout(model, items, idx, y_ids, n_ids, pad_id, device)
        for i, value in zip(idx, p.tolist()):
            ps[i] = value
    ys = [item[1] for item in items]
    model.train()
    brier = sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)
    return brier, ps, ys


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda"

    rows = []
    for path in args.train:
        with open(path, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f]
    train_rows = [r for r in rows if in_range(r["question"], args.train_ids)]
    val_rows = [r for r in rows if in_range(r["question"], args.val_ids)]
    rng.shuffle(train_rows)
    rng.shuffle(val_rows)
    if args.max_train:
        train_rows = train_rows[: args.max_train]
    val_rows = val_rows[: args.val_max]

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    y_ids, n_ids = label_ids(tokenizer)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    train = encode(tokenizer, train_rows, args.max_len)
    val = encode(tokenizer, val_rows, args.max_len)
    rate = sum(t[1] for t in train) / max(len(train), 1)
    print(f"train {len(train)} prompts (positives {rate:.3f}), val {len(val)}; label ids Y={y_ids} N={n_ids}", flush=True)

    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.bfloat16).to(device)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model.config.use_cache = False

    # the readout must equal what vLLM returned for the base model (cached p_yes)
    check = [t for t in val if t[2] is not None][: args.check_base]
    if check:
        _, ps, _ = evaluate(model, check, y_ids, n_ids, pad_id, device, args.batch_tokens)
        diffs = sorted(abs(p - t[2]) for p, t in zip(ps, check))
        print(f"base readout vs cached vLLM P(Y): median |diff| {diffs[len(diffs) // 2]:.5f}, "
              f"p90 {diffs[int(0.9 * len(diffs))]:.5f}", flush=True)

    model = get_peft_model(model, LoraConfig(
        r=args.rank, lora_alpha=args.alpha, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    model.print_trainable_parameters()
    base_brier, _, _ = evaluate(model, val, y_ids, n_ids, pad_id, device, args.batch_tokens)
    print(f"val Brier before training {base_brier:.5f}", flush=True)

    groups = batches(train, args.batch_tokens, True, rng)
    total = max(1, int(len(groups) * args.epochs))
    optim = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.0)
    warmup = max(1, int(0.03 * total))
    sched = torch.optim.lr_scheduler.LambdaLR(
        optim, lambda s: min(1.0, (s + 1) / warmup) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total))))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    best = base_brier
    started = time.time()
    model.train()
    for step in range(total):
        idx = groups[step % len(groups)]
        p, log_mass = readout(model, train, idx, y_ids, n_ids, pad_id, device)
        y = torch.tensor([train[i][1] for i in idx], device=device)
        brier = ((p - y) ** 2).mean()
        loss = brier + args.mass_penalty * (-log_mass).mean()
        if not torch.isfinite(loss):
            print(f"step {step}: non-finite loss, skipped", flush=True)
            optim.zero_grad(set_to_none=True)
            sched.step()
            continue
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        if not torch.isfinite(grad_norm):
            print(f"step {step}: non-finite gradient, skipped", flush=True)
            optim.zero_grad(set_to_none=True)
            sched.step()
            continue
        optim.step()
        sched.step()
        optim.zero_grad(set_to_none=True)
        if step % 20 == 0:
            print(f"step {step}/{total} brier {brier.item():.4f} mass {log_mass.exp().mean().item():.4f} "
                  f"grad {grad_norm.item():.3f} lr {sched.get_last_lr()[0]:.2e} {time.time() - started:.0f}s", flush=True)
        if (step + 1) % args.eval_every == 0 or step + 1 == total:
            val_brier, _, _ = evaluate(model, val, y_ids, n_ids, pad_id, device, args.batch_tokens)
            print(f"val Brier {val_brier:.5f} (best {best:.5f})", flush=True)
            if val_brier < best:
                best = val_brier
                model.save_pretrained(out)
                print(f"saved adapter to {out}", flush=True)
    improved = best < base_brier
    if not improved:
        model.save_pretrained(out)
        print("validation never improved; saved the final adapter anyway", flush=True)
    (out / "brier_readout.json").write_text(json.dumps({
        "args": vars(args), "val_brier_before": base_brier, "val_brier_best": best, "improved": improved,
        "label_ids": {"Y": y_ids, "N": n_ids}, "train_prompts": len(train), "train_positive_rate": rate,
    }, indent=2), encoding="utf-8")
    print(f"done: val Brier {base_brier:.5f} -> {best:.5f}", flush=True)


if __name__ == "__main__":
    main()
