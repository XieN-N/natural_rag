# RAG Pipeline Run Scripts

This directory contains scripts to run various RAG engines on benchmark datasets.

All scripts share a common dataset interface (`RAGDataset.load_auto()`) and output structure.

## File Map

One engine — one canonical runner; per-dataset/per-model variants are
flags/env, not copies. Every runner accepts `--limit-docs`/`--limit-questions`
for smoke tests.

| File | Purpose |
|---|---|
| `ragu_run.py` | **RAGU** runner (primary engine): indexing + answers; `--query-engine local/query_plan/naive`, `--short-answers`, `--index-model` |
| `lightrag_run.py` | **LightRAG** runner |
| `fast_graphrag_run.py` | **FastGraphRAG** runner |
| `nano_graphrag_run.py` | **NanoGraphRAG** runner |
| `run_hippo.py` | **HippoRAG** runner |
| `baseline_run.py` | Tree-structured **baseline** (no graph; depends on RAGU) |
| `wikontic_run.py` | **Wikontic** runner: modes dynamic/structured, scope corpus/per_sample, Qdrant/Mongo backends |
| `convert_answers.py` | Consolidate `answers/<q_idx>.txt` → `<dataset>_answers.json` |
| `jsonl_llm_judge_evaluate.py` | LLM-as-judge (any engine; plain OpenAI client, env-overridable) |
| `judge_answers.py` | EM/F1 + LLM judge over an existing index (used by `runs_cluster/eval_universal.sh`) |
| `ragu_evaluate.py` | Checklist-based evaluation for the BL family |
| `build_graphrag_bench_input.py` | Build the eval input JSON for external GraphRAG-Benchmark |
| `prepare_graphrag_bench.py` | Prepare GraphRAG-Bench datasets into the repo layout |
| `index_stats.py` | Indexing-cost summary (time, LLM calls per document) |
| `check_index_ready.py` | Verify a downloaded index loads without re-indexing |
| `ragu_dash.py` | Launch the results dashboard |
| `test_all.py` | Smoke-test every pipeline on a small dataset (`--dry-run` prints commands) |

Removed in the `cleanup-reproducibility` branch (near-duplicates of the
canonical runners): `ragu_2wiki_run.py`, `run_custom_ragu.py`,
`run_lightrag_bioasq.py`, `chegeka_evaluate.py`, `multi_q_evaluate.py` and the
whole `runs_universal/` directory (~30 copies of one sbatch script — replaced
by `runs_cluster/run_universal.sh`).

## Where the output goes

Run artifacts live under `local/`, which git ignores wholesale. `generated/` is
a junction (Windows) or symlink (Linux) pointing at `local/generated`, so every
`--output-dir generated/...` in this file keeps working. A fresh checkout has no
link — create it once:

```bash
ln -s local/generated generated
```

## Installing RAGU

The release build is an extra; the dev branch is a manual install. Never mix
them in one environment: both provide the same `ragu` package and pip keeps
whichever it resolved last.

```bash
pip install -e ".[ragu]"
```

```bash
# dev branch of RaguTeam/RAGU instead of the release
pip install -e . && pip install --force-reinstall \
    "graph-ragu @ git+https://github.com/RaguTeam/RAGU.git@dev"
```

The dev branch passes retrieval options as an `EngineParams` object instead of
`top_k` / `use_chunks` keywords. `RAGUPipeline` detects which convention the
installed build follows, so the run scripts and their flags are the same either
way. Two flags behave differently than they used to: `--no-use-chunks` now
actually reaches the engine (the answer path used to hardcode chunks on), and
`--short-answers` fails loudly on a build whose engines have no
`update_prompt()` instead of silently answering at full length.

The decision-model flags (`--selector`, `--decision-model-name`, `--select-*`,
`--ppr-*`) need RAGU with the `ragu.decision` package, which until it is merged
upstream lives in the `feature/decision-model` branch of the fork:

```bash
pip install -e . && pip install --force-reinstall \
    "graph-ragu @ git+https://github.com/XieN-N/RAGU.git@feature/decision-model"
```

Without these flags that build answers exactly like dev RAGU. With them on a
build that lacks the feature, `RAGUPipeline` stops with an error instead of
quietly running without selection.

## Quick Start — RAGU

```bash
export OPENAI_BASE_URL="https://api.vsellm.ru/v1"
export EMBED_BASE_URL="http://127.0.0.1:8080/v1"
export OPENAI_API_KEY="your-key"
export LLM_MODEL="qwen/qwen3-vl-8b-instruct"
export EMBED_MODEL="/data"
export EMBEDDING_DIM="768"

python runs/ragu_run.py \
  --dataset-path datasets/musique \
  --output-dir generated/ragu_musique \
  --no-build-index --answer --force \
  --query-engine query_plan \
  --embed-batch-size 32
```

**All paths are relative to the `natural_rag/` project root.** Run from that directory.

## Common Arguments

| Argument | Env Var | Default | Description |
|----------|---------|---------|-------------|
| `--dataset-path` | `DATASET_PATH` | `datasets/bioasq` | Path to dataset (dir or file) |
| `--output-dir` | `OUTPUT_DIR` | `generated/ragu` | Output directory |
| `--build-index` / `--no-build-index` | `BUILD_INDEX` | `true` | Build index from documents |
| `--answer` / `--no-answer` | `ANSWER` | `true` | Generate answers |
| `--force` | `FORCE` | `false` | Overwrite existing answers |
| `--index-model` | `INDEX_MODEL` | — | Label of the model that **built** the graph (e.g. `gpt-oss-20b`). When set, inserted as a subdirectory into the index/answers path so graphs from different builder models coexist |
| `--short-answers` / `--no-short-answers` | `SHORT_ANSWERS` | `false` | Terse extractive answer prompt (for short-answer benchmarks like bioasq/musique/2wiki) |
| `--openai-base-url` | `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM API base URL |
| `--embed-base-url` | `EMBED_BASE_URL` | `OPENAI_BASE_URL` | Embedding API base URL |
| `--openai-api-key` | `OPENAI_API_KEY` | — | API key (required) |

> `--index-model` and `--short-answers` are available in both `ragu_run.py` and
> `lightrag_run.py`.

## RAGU-Specific Arguments

| Argument | Env Var | Default | Description |
|----------|---------|---------|-------------|
| `--builder-model-name` | `BUILDER_MODEL_NAME` / `LLM_MODEL` | `mistralai/mistral-medium-3` | LLM for indexing |
| `--assistant-model-name` | `ASSISTANT_MODEL_NAME` / `LLM_MODEL` | same as builder | LLM for answering |
| `--embedding-model-name` | `EMBEDDING_MODEL_NAME` / `EMBED_MODEL` | `emb-qwen/qwen3-embedding-8b` | Embedding model |
| `--embedding-dim` | `EMBEDDING_DIM` | `4096` | Embedding dimension |
| `--embed-batch-size` | `EMBED_BATCH_SIZE` | `32` | Max texts per embed API call |
| `--retrieval-top-k` | `RETRIEVAL_TOP_K` | `20` | Entities to retrieve for context |
| `--qa-top-k` | `QA_TOP_K` | `20` | Entities for answer generation |
| `--query-engine` | `QUERY_ENGINE` | `local` | `local`, `query_plan`, or `naive` |
| `--chunker` | `CHUNKER` | `simple` | `simple` or `smart` |
| `--use-chunks` / `--no-use-chunks` | `USE_CHUNKS` | `true` | Use text chunks in queries |
| `--use-summary` / `--no-use-summary` | `USE_SUMMARY` | `false` | Use community summaries |
| `--simple-chunk-size` | `SIMPLE_CHUNK_SIZE` | `2048` | Chunk size (characters) |
| `--simple-chunk-overlap` | `SIMPLE_CHUNK_OVERLAP` | `0` | Chunk overlap |
| `--max-completion-tokens` | `MAX_COMPLETION_TOKENS` | `16384` | Max LLM output tokens (16384 is the ceiling for `gpt-4o-mini`; raise for models that allow more) |
| `--openai-rate-min-delay` | `OPENAI_RATE_MIN_DELAY` | `2` | Min delay between requests (s) |
| `--openai-rate-max-simultaneous` | `OPENAI_RATE_MAX_SIMULTANEOUS` | `10` | Max concurrent requests |
| `--llm-cache` | `LLM_CACHE` | `tmp/llm_cache` | Response cache directory |
| `--tokenizer-backend` | `TOKENIZER_BACKEND` | `tiktoken` | Tokenizer backend |
| `--tokenizer-llm-name` | `TOKENIZER_LLM_NAME` | `gpt-4o` | Tokenizer model name (LLM) |
| `--tokenizer-embedder-name` | `TOKENIZER_EMBEDDER_NAME` | `gpt-4o` | Tokenizer model name (embedder) |
| `--index-dir` | `INDEX_DIR` | — | Read/write the index here instead of `<output-dir>/<dataset>/[<model>/]index`, so several answer variants share one index |
| `--save-context` / `--no-save-context` | `SAVE_CONTEXT` | `false` | Write `answers/<i>.context.json`: context as the answer prompt saw it, its tokens, answer seconds, retrieval metrics (incl. per-stage `timing`) |
| `--context-budget` | `CONTEXT_BUDGET` | engine default (30k) | Max context tokens for the answer prompt |
| `--always-answer` / `--no-always-answer` | `ALWAYS_ANSWER` | `false` | With `--short-answers`: forbid "I don't know" (benchmarks where every question has an answer) |
| `--selector` | `SELECTOR` | `none` | dev RAGU: `pointwise` (decision model) or `cosine` context selection in LocalSearch |
| `--decision-model-name` | `DECISION_MODEL_NAME` | — | Model for the single-token decision model (same client as answers) |
| `--decision-constraint` | `DECISION_CONSTRAINT` | `none` | `none`, `logit_bias` (OpenAI) or `allowed_token_ids` (vLLM) |
| `--select-pool-entities/relations/chunks`, `--select-threshold`, `--select-floor`, `--select-top-entities/relations/chunks` | — | RAGU defaults | Selection pools and rules, see `ragu/search_engine/README.md` |
| `--select-hops` | — | `1` | pointwise: hops walked from relations the decision model kept |
| `--select-keep-seed-context` / `--no-select-keep-seed-context` | — | `false` | pointwise: keep the full seed context and append what further hops select |
| `--ppr-chunks`, `--ppr-alpha` | — | `0`, `0.5` | Append Personalized PageRank chunks (seeded by the decision model when present) |

All of these are off by default, so a run without them is the plain LocalSearch
it always was. Best MuSiQue setup so far: `--short-answers --always-answer
--selector pointwise --decision-model-name gpt-4o-mini --select-hops 2 --select-pool-chunks 30`
(+3.8 pp answer correctness over the same prompt without the decision model on
395 held-out questions; scripts and numbers in
[runs_local/README.md](../runs_local/README.md#эксперименты-с-decision-model)).

## Query Engines

### `local` (default)
Single-stage retrieval + LLM answer generation. Good for simple questions.

### `query_plan`
Decomposes complex questions into sub-query DAGs via LLM planning, executes sub-queries in topological order, and returns the final answer. Falls back to the underlying engine when no decomposition is needed.

### `naive`
Plain vector RAG: retrieves the most similar text **chunks** from the chunk vector DB and answers from them — the knowledge graph (entities/relations) is **not** traversed. Uses the same on-disk RAGU index, so it can reuse an existing graph's index (e.g. symlink the RAGU `index/` into a `generated/naive_<dataset>/` output dir).

## Output Structure

```
<output-dir>/<dataset-name>/[<index-model>/]
├── index/       # Built index (vectors + graph)
└── answers/     # Generated answers (0.txt, 1.txt, ...)
```

The `<index-model>` segment is present only when `--index-model` is passed
(e.g. `generated/ragu_bioasq/bioasq/gpt-oss-20b/{index,answers}`); otherwise the
layout is `<output-dir>/<dataset-name>/{index,answers}`.

## Environment Variables (RAGU)

```bash
# LLM endpoint
export OPENAI_BASE_URL="https://api.vsellm.ru/v1"
export OPENAI_API_KEY="sk-..."
export LLM_MODEL="qwen/qwen3-vl-8b-instruct"

# Embedding endpoint (separate server)
export EMBED_BASE_URL="http://127.0.0.1:8080/v1"
export EMBED_MODEL="/data"
export EMBEDDING_DIM="768"

# Optional
export QUERY_ENGINE="query_plan"
export EMBED_BATCH_SIZE="32"
export RETRIEVAL_TOP_K="20"
export QA_TOP_K="20"
```

## Other Scripts

### FastGraphRAG
```bash
python runs/fast_graphrag_run.py \
  --dataset-path datasets/chegeka \
  --openai-base-url $OPENAI_BASE_URL \
  --openai-api-key $OPENAI_API_KEY \
  --llm-model Qwen2.5-14B-Instruct \
  --embed-model gte-multilingual-base \
  --embedding-dim 768
```

### LightRAG
```bash
python runs/lightrag_run.py \
  --dataset-path datasets/multiq \
  --openai-base-url $OPENAI_BASE_URL \
  --openai-api-key $OPENAI_API_KEY \
  --llm-model openai/gpt-4o-mini \
  --embed-model emb-openai/text-embedding-3-small \
  --embedding-dim 1536 \
  --query-mode naive
```

LightRAG-specific extras (besides the shared `--index-model` / `--short-answers`):

| Argument | Env Var | Default | Description |
|----------|---------|---------|-------------|
| `--query-mode` | `QUERY_MODE` | `naive` | `naive` / `local` / `global` / `hybrid` / `mix` |
| `--llm-cache` / `--no-llm-cache` | `LLM_CACHE` | on | Use LightRAG's LLM response cache. Pass `--no-llm-cache` to force fresh regeneration when a stale response cache ships inside the index |

> `--short-answers` for LightRAG replaces its built-in `rag_response` /
> `naive_rag_response` templates with terse, reference-free ones (removes the
> `### References` section and long-form output).

### NanoGraphRAG
```bash
python runs/nano_graphrag_run.py \
  --dataset-path datasets/bl_medium \
  --openai-base-url $OPENAI_BASE_URL \
  --openai-api-key $OPENAI_API_KEY \
  --llm-model openai/gpt-4o-mini \
  --embed-model emb-openai/text-embedding-3-small \
  --embedding-dim 1536
```

### Baseline
```bash
python runs/baseline_run.py \
  --dataset-path datasets/bl_medium \
  --openai-base-url $OPENAI_BASE_URL \
  --openai-api-key $OPENAI_API_KEY \
  --llm-model mistralai/mistral-medium-3
```

### HippoRAG
```bash
python runs/run_hippo.py \
  --dataset-path datasets/2wikimultihopqa/2wikimultihopqa.json \
  --openai-base-url $OPENAI_BASE_URL \
  --openai-api-key $OPENAI_API_KEY \
  --builder-model-name gpt-4o-mini \
  --embedding-model-name text-embedding-3-small \
  --retrieval-top-k 200 \
  --qa-top-k 5
```

### Wikontic

For cluster runs (SLURM + vLLM + GigaChat) use `runs_cluster/` — see
[runs_cluster/README.md](../runs_cluster/README.md). This section covers the
script itself.

**Dynamic mode** (fast, no Wikidata ontology required):

```bash
python runs/wikontic_run.py \
  --dataset-path datasets/bl_tiny \
  --mode dynamic \
  --qdrant-url ":memory:" \
  --output-dir generated/wikontic_bl_tiny
```

**Structured mode** (requires pre-built Wikidata ontology — run `setup_wikontic_ontology` first):

```bash
# One-time ontology setup
python -m scripts.setup_wikontic_ontology \
  --backend qdrant --qdrant-url ":memory:"

# Then run the pipeline
python runs/wikontic_run.py \
  --dataset-path datasets/bl_tiny \
  --mode structured \
  --qdrant-url ":memory:" \
  --output-dir generated/wikontic_bl_tiny
```

Wikontic-specific arguments (`--index-model`, `--short-answers`, `--force` and
the output layout behave as for `ragu_run.py`):

| Argument | Env Var | Default | Description |
|----------|---------|---------|-------------|
| `--mode` | `WIKONTIC_MODE` | `dynamic` | `dynamic` (no ontology) or `structured` (Wikidata types + property constraints) |
| `--scope` | `WIKONTIC_SCOPE` | `corpus` | `corpus` = one graph over everything (`sample_id=None`); `per_sample` = one graph per question, retrieval filtered by `sample_id` — the setup used in Wikontic's own `qa_eval_musique.py` |
| `--per-sample-docs` | `WIKONTIC_PER_SAMPLE_DOCS` | `20` | Documents per sample in `per_sample` scope: gold docs plus seeded distractors |
| `--workers` | `WIKONTIC_WORKERS` | `1` | Concurrent documents during indexing (upstream indexes strictly sequentially — verify triplet counts before trusting >1) |
| `--resume` / `--no-resume` | `WIKONTIC_RESUME` | on | Skip documents whose triplets are already stored, keyed on `(sample_id, source_text_id)` |
| `--collection-prefix` | `WIKONTIC_COLLECTION_PREFIX` | `<dataset>__<index-model>__<mode>__<scope>` | Namespaces the triplet collections so several indexes share one database / Qdrant instance |
| `--triplets-db-name` | `WIKONTIC_TRIPLETS_DB_NAME` | `triplets_db` | MongoDB database for triplets |
| `--ontology-db-name` | `WIKONTIC_ONTOLOGY_DB_NAME` | `wikidata_ontology` | MongoDB database for the ontology |
| `--qdrant-local-path` | `WIKONTIC_QDRANT_LOCAL_PATH` | — | Server-less persistent Qdrant (`QdrantClient(path=...)`) — no container, no port, but brute-force search |
| `--hf-model-path` | `HF_MODEL_PATH` | — | Local `facebook/contriever` — required on offline nodes |
| `--qa-collapsing` | `WIKONTIC_QA_COLLAPSING` | off | Answer via `answer_with_qa_collapsing` (question decomposition), the path used in Wikontic's published evaluation |
| `--use-qualifiers` | `WIKONTIC_USE_QUALIFIERS` | **on** | Matches the default in Wikontic's own `qa_eval_*` scripts |
| `--limit-docs` / `--limit-questions` | `LIMIT_DOCS` / `LIMIT_QUESTIONS` | — | Truncate for smoke tests |
| `--timing` / `--no-timing` | — | on | Write `index_timing.jsonl` + `index_summary.json` |

Things to know about Wikontic before interpreting results:

- Its embedder is hardcoded to `facebook/contriever` (768 dim); the OpenAI-compatible
  embedding endpoint is not used. Only `HF_MODEL_PATH` can point it elsewhere.
- Its collection names are hardcoded in the aligners, hence `--collection-prefix`
  (implemented in `natural_rag/wikontic_prefix.py`).
- The Mongo backend requires **Atlas Vector Search** (`create_search_index`,
  `$vectorSearch`) — MongoDB Community will fail on index creation.
- There is no chunker: a document is sent to the LLM whole. Split large corpora
  when preparing the dataset (see `runs/prepare_graphrag_bench.py`).
- `--short-answers` appends an instruction to the question text, because the
  answer prompts live inside the installed package. RAGU's `--short-answers`
  replaces the prompt template — the two are not equivalent.

**Persistent index** (Qdrant, reused across runs):

Start Qdrant in Docker first (one-time):

```bash
# Create a volume for data storage
docker volume create qdrant_storage

# Start the container
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant

# Verify it is running
curl http://localhost:6333/health
```

Stop and restart:

```bash
docker stop qdrant
docker start qdrant  # data persists
```

Then run the pipeline:

```bash
# First run: indexing + answers
python runs/wikontic_run.py \
  --dataset-path datasets/bl_tiny \
  --mode dynamic \
  --qdrant-url http://localhost:6333 \
  --output-dir generated/wikontic_bl_tiny

# Subsequent runs: answers only (index already exists)
python runs/wikontic_run.py \
  --dataset-path datasets/bl_tiny \
  --mode dynamic \
  --qdrant-url http://localhost:6333 \
  --no-build-index --answer
```

**Separate indexes in one storage:**

When `sample_id=None` (default), triplet search goes through **all collections** in Qdrant.
If multiple datasets are indexed into the same Qdrant, answers for one dataset may
use triplets from another when entities are similar. The cheap fix is
`--collection-prefix` (on by default, derived from dataset/model/mode/scope): every
triplet collection is namespaced, so several indexes coexist in one Qdrant instance
or one MongoDB database. The ontology database is shared on purpose and is not
prefixed.

Alternatively — a **separate container + volume** per dataset:

```bash
# bl_tiny
docker run -d --name qdrant_bl_tiny \
  -p 6333:6333 \
  -v qdrant_bl_tiny:/qdrant/storage \
  qdrant/qdrant

# multiq
docker run -d --name qdrant_multiq \
  -p 6334:6333 \
  -v qdrant_multiq:/qdrant/storage \
  qdrant/qdrant
```

Each container gets its own port (`-p`), its own volume, and its own database.

**Transferring the index to another machine:**

Option A — Qdrant snapshot (recommended):

```bash
# Export
curl -X POST http://localhost:6333/collections/triplets_db/snapshots
# → returns the path to the .snapshot file inside the container

# Copy the snapshot out
docker cp qdrant:/qdrant/storage/snapshots/triplets_db/<name>.snapshot ./triplets_db.snapshot

# On the target machine — restore
curl -X POST \
  -F "snapshot=@triplets_db.snapshot" \
  http://localhost:6333/collections/upload?wait=true
```

Option B — copying the Docker volume:

```bash
# Export
docker run --rm -v qdrant_storage:/source alpine \
  tar czf - -C /source . > qdrant_backup.tar.gz

# Transfer qdrant_backup.tar.gz to the target machine
# Import (creates the volume if it doesn't exist)
docker run --rm -v qdrant_storage:/target alpine \
  tar xzf - -C /target < qdrant_backup.tar.gz
```

Docker volume `qdrant_storage` holds both collections (`triplets_db` and `wikidata_ontology`) — Qdrant distinguishes them internally.

Environment variables (see `.env.wikontic.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKONTIC_API_KEY` | — | LLM API key |
| `OPENAI_API_KEY` | — | Fallback API key |
| `WIKONTIC_BASE_URL` | `https://api.openai.com/v1` | LLM API base URL |
| `OPENAI_BASE_URL` | — | Fallback base URL |
| `WIKONTIC_MODEL` | — | LLM model |
| `LLM_MODEL` | `gpt-4o` | Fallback model |
| `WIKONTIC_MODE` | `dynamic` | `dynamic` or `structured` |
| `WIKONTIC_STORAGE_BACKEND` | `qdrant` | `qdrant` or `mongo` |
| `WIKONTIC_QDRANT_URL` | `:memory:` | Qdrant URL |
| `WIKONTIC_HOP_DEPTH` | `5` | Multi-hop traversal depth |

Fallback chain: **key** — `WIKONTIC_API_KEY` → `OPENAI_API_KEY` → `KEY` → `OPENROUTER_KEY`; **base_url** — `WIKONTIC_BASE_URL` → `OPENAI_BASE_URL` → `OPENROUTER_BASE_URL`; **model** — `WIKONTIC_MODEL` → `LLM_MODEL` → `gpt-4o`. So `ragu_run.py` env vars (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL`) also work for Wikontic with no extra config.

## Index Readiness Check

`runs/check_index_ready.py` verifies a downloaded index is laid out correctly so
answers can be generated **without** re-indexing.

```bash
# Create the (model-scoped) folders, then drop the index files into index/
python runs/check_index_ready.py --engine ragu \
  --dataset-path datasets/bioasq --output-dir generated/ragu_bioasq \
  --index-model gpt-oss-20b --make-dirs

# Full probe: load the index and answer question 0 (needs live embedder + LLM)
python runs/check_index_ready.py --engine ragu \
  --dataset-path datasets/bioasq --output-dir generated/ragu_bioasq \
  --index-model gpt-oss-20b --probe
```

- Offline check: confirms required files exist (RAGU: `knowledge_graph.gml`,
  `vdb_*.json`, `kv_chunks.json`; LightRAG: `graph_chunk_entity_relation.graphml`,
  `vdb_*.json`, `kv_store_*.json`) and reports the stored `embedding_dim`
  (must match the answer-time embedder, e.g. 768 for `gte-multilingual-base`).
- `--make-dirs` creates the `index/` + `answers/` folders. `--probe` loads the
  pipeline with indexing disabled and generates one answer to prove the graph
  loads and no re-indexing happens.

## Evaluation with GraphRAG-Benchmark

Convert generated answers into the input JSON expected by
[GraphRAG-Benchmark](https://github.com/bond005/GraphRAG-Benchmark)'s
`Evaluation/generation_eval.py`, then run the judge.

```bash
# 1) Build the eval input (reads the dataset + answers/*.txt)
python runs/build_graphrag_bench_input.py \
  --dataset-path datasets/bioasq \
  --output-dir generated/ragu_bioasq --index-model gpt-oss-20b
# → generated/ragu_bioasq/bioasq/gpt-oss-20b/graphrag_bench_input.json

# 2) Score it (from the GraphRAG-Benchmark repo / its own env)
export LLM_API_KEY="..."
python -m Evaluation.generation_eval --mode API \
  --model gemini-3-flash-preview --base_url "https://api.vsellm.ru/v1" \
  --embedding_model text-embedding-3-small \
  --embedding_base_url "https://api.vsellm.ru/v1" \
  --data_file <path>/graphrag_bench_input.json \
  --output_file <path>/eval_results.json --detailed_output
```

Each item carries `id`, `question`, `source`, `context`, `evidence`,
`question_type`, `generated_answer`, `ground_truth`. `question_type` maps to the
metrics: `Fact Retrieval` (bioasq) and `Complex Reasoning` (musique / 2wiki)
both use `rouge_score` + `answer_correctness`. The judge model
(`gemini-3-flash-preview`) and embedder (`text-embedding-3-small`) are used
**only** inside the eval script — they are unrelated to answer generation.

## Indexing Cost

`ragu_run.py` and `wikontic_run.py` both write, next to `index/` and `answers/`:

- `index_timing.jsonl` — one row per indexing step (`doc_id`, `chars`, `seconds`,
  `cumulative_seconds`). Wikontic emits a row per document; RAGU indexes the whole
  corpus in a single call, so it emits one row covering every document.
- `index_summary.json` — `wall_seconds`, `docs_per_min`, `chars_per_sec`,
  `llm_calls`, `llm_calls_per_doc`, `prompt_tokens`, `completion_tokens`, `failures`.

Both come from `natural_rag/timing.py`, so the numbers are directly comparable.
Collect them into one table:

```bash
python runs/index_stats.py generated
python runs/index_stats.py generated --format csv --out index_stats.csv
```

## Scoring answers

`runs/judge_answers.py` scores `answers/<i>.txt` for any engine using the shared
run layout, so Wikontic and RAGU runs are scored identically:

```bash
python runs/judge_answers.py \
  --dataset-path datasets/musique \
  --output-dir generated/wikontic_musique --index-model gigachat \
  --judge-model Qwen2.5-14B-Instruct
```

Reports normalised exact match, token F1 and LLM-judge accuracy into
`eval_results.json`. `--no-judge` computes EM/F1 only (no model needed).

## Evaluation Scripts

```bash
# Checklist-based RAGU evaluation
python runs/ragu_evaluate.py \
  --dataset-name bl_medium \
  --answers-dir generated/ragu_bl_medium/answers

# Consolidate .txt answers into one JSON, then LLM-as-judge (any engine)
python runs/convert_answers.py \
  --dataset-name multiq \
  --answers-dir generated/lightrag_multiq/multiq/answers

python runs/jsonl_llm_judge_evaluate.py \
  --dataset-name multiq \
  --answers-dir generated/lightrag_multiq/multiq/answers \
  --judge-model Qwen2.5-14B-Instruct
```

## Dataset Examples

```
datasets/
├── bl_tiny/                # YAML format
│   ├── corpus_info.yaml
│   ├── questions.yaml
│   └── docs/
├── bioasq/                 # JSONL format
│   ├── corpus.jsonl
│   └── questions.jsonl
├── musique/                # JSONL format
│   ├── corpus.jsonl
│   └── questions.jsonl
├── 2wikimultihopqa/        # Single JSON file
│   └── 2wikimultihopqa.json
```
