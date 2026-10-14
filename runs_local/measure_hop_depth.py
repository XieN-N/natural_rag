"""Pick ``--hop-depth`` for a corpus-scope bundle by measuring, not guessing.

``answer_question_with_llm`` expands ``hop_depth`` hops from the entities linked
to the question and puts **every** triplet it reaches into a single prompt --
no cap, no ranking (``wikontic/utils/base_inference_with_db.py``). On a
``scope: corpus`` graph that overruns the model's context window, and the
gateway reports it as a bare ``400 / Request failed`` that says nothing about
size. The default of 5 is only safe on the small per-sample subgraphs.

The trap this script exists to avoid: **sampling random entities understates the
risk.** Most entities are peripheral, so a random-seed distribution looks
comfortable while real questions land on hubs. On ``graphrag_bench_medical`` no
random 3-entity seed exceeded the limit at depth 2, yet the hub ``cancer``
alone reached 116 007 tokens there and the run failed. So the hub row below,
not the percentiles, is what should decide the depth.

    python runs_local/measure_hop_depth.py --bundle ~/wikontic_bundles/<RUN_ID>
"""
from __future__ import annotations

import httpx

from natural_rag.url_guard import assert_http_url

import argparse
import json
import os
import random
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from answer_from_index import (  # noqa: E402
    free_port,
    load_manifest,
    resolve_storage,
    start_qdrant,
)

# gpt-4o-mini: 128k context, but the API reserves room for the completion, so
# the usable input budget is materially smaller than the headline number.
CONTEXT_WINDOW = 128_000
RESERVED_FOR_OUTPUT = 16_384


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--max-depth", type=int, default=5)
    p.add_argument("--samples", type=int, default=200)
    p.add_argument("--seed-sizes", type=int, nargs="+", default=[1, 3, 10, 20],
                   help="Entities per random seed, standing in for the set an LLM "
                        "links to one question. Swept rather than fixed: "
                        "`retrieve_similar_entity_names` returns up to 10 "
                        "candidates for *each* entity pulled out of the question, "
                        "so a seed of 3 badly understates a real one. Measuring "
                        "at 3 alone is what made an earlier run recommend a depth "
                        "that then produced 370k-token prompts.")
    p.add_argument("--encoding", default="o200k_base",
                   help="tiktoken encoding; o200k_base covers gpt-4o / gpt-4o-mini.")
    p.add_argument("--qdrant-bin", default=None)
    p.add_argument("--qdrant-url", default=None)
    return p.parse_args()


def scroll(url: str, collection: str) -> list[dict]:
    payloads: list[dict] = []
    offset = None
    while True:
        body: dict = {"limit": 1000, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        response = httpx.post(
            f"{url}/collections/{collection}/points/scroll",
            json=body, timeout=300,
        )
        response.raise_for_status()
        result = response.json()["result"]
        payloads.extend(p["payload"] for p in result["points"] if p.get("payload"))
        offset = result.get("next_page_offset")
        if offset is None:
            return payloads


def main() -> int:
    args = parse_args()
    bundle = args.bundle.expanduser().resolve()
    manifest = load_manifest(bundle)

    import tiktoken
    encoding = tiktoken.get_encoding(args.encoding)

    process = None
    try:
        if args.qdrant_url:
            url = assert_http_url(args.qdrant_url.rstrip("/"), what="--qdrant-url")
        else:
            binary = args.qdrant_bin or os.environ.get("QDRANT_BIN", "./qdrant")
            process, url = start_qdrant(
                binary, resolve_storage(bundle, manifest), free_port(),
                bundle / "measure_qdrant.log",
            )

        triplets = scroll(url, f"{manifest['collection_prefix']}__triplets")
        adjacency: dict[str, list[int]] = defaultdict(list)
        for i, triplet in enumerate(triplets):
            adjacency[triplet.get("subject")].append(i)
            adjacency[triplet.get("object")].append(i)
        adjacency.pop(None, None)

        def as_sent(index: int) -> dict:
            # The exact shape answer_question_with_llm builds with
            # use_qualifiers=True, which is answer_from_index.py's default.
            t = triplets[index]
            return {"subject": t.get("subject"), "relation": t.get("relation"),
                    "object": t.get("object"), "qualifiers": t.get("qualifiers"),
                    "source_text_id": t.get("source_text_id")}

        def closure(seed, depth: int) -> set[int]:
            found: set[int] = set()
            frontier = {s for s in seed if s in adjacency}
            for _ in range(depth):
                fresh = set()
                for entity in frontier:
                    for i in adjacency.get(entity, ()):
                        if i not in found:
                            found.add(i)
                            fresh.add(triplets[i].get("subject"))
                            fresh.add(triplets[i].get("object"))
                frontier = fresh - {None}
                if not frontier:
                    break
            return found

        def tokens(indices) -> int:
            return len(encoding.encode(str([as_sent(i) for i in indices])))

        budget = CONTEXT_WINDOW - RESERVED_FOR_OUTPUT
        hub = max(adjacency, key=lambda e: len(adjacency[e]))
        print(f"граф: {len(triplets)} триплетов, {len(adjacency)} сущностей")
        print(f"весь граф одним промптом: {tokens(range(len(triplets)))} токенов")
        print(f"бюджет входа: {budget} ({CONTEXT_WINDOW} минус {RESERVED_FOR_OUTPUT} "
              f"под ответ)\n")

        names = [e for e in adjacency if e]
        random.seed(0)

        print(f"хаб = {hub!r} ({len(adjacency[hub])} триплетов)\n")
        header = "".join(f"{f'сид={k}':>12}" for k in args.seed_sizes)
        print(f"{'хоп':>4}{header} {'ХАБ':>12}   (p90 токенов; ХАБ — от самой "
              f"связной сущности)")

        recommended = None
        for depth in range(1, args.max_depth + 1):
            cells = []
            worst_over = 0
            for size in args.seed_sizes:
                seeds = [random.sample(names, min(size, len(names)))
                         for _ in range(args.samples)]
                counts = sorted(tokens(closure(s, depth)) for s in seeds)
                p90 = counts[int(len(counts) * 0.9)]
                over = 100 * sum(1 for c in counts if c > budget) / len(counts)
                worst_over = max(worst_over, over)
                cells.append(f"{p90:>11}{'!' if p90 > budget else ' '}")
            hub_tokens = tokens(closure([hub], depth))
            flag = "" if hub_tokens <= budget else "  ← не влезает"
            print(f"{depth:>4}{''.join(cells)} {hub_tokens:>12}{flag}")
            # The hub is the binding constraint, and the largest seed is the
            # honest stand-in for real linking; require both to fit.
            if hub_tokens <= budget and worst_over == 0:
                recommended = depth

        print()
        print(f"БЕЗОПАСНЫЙ МИНИМУМ: --hop-depth {recommended or 1}")
        print("Критерий: и хаб, и p90 при наибольшем размере сида влезают в "
              "бюджет входа. Восклицательный знак — превышение.")
        print()
        print("Это нижняя граница, а не предсказание. Строка ХАБ — худший случай:")
        print("она реализуется, только если вопросы действительно линкуются в "
              "самую связную сущность. На тематически однородном корпусе так и "
              "происходит, на разнородном — почти никогда. Если p90 на следующей "
              "глубине укладывается, а не влезает только хаб, проверьте её "
              "смоуком на 50 вопросах: отказы будут видны как `failed` и в логе "
              "строкой `LLM call failed: ... tokens=N`.")
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
