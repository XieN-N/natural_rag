# RAG Pipeline Run Scripts

This directory contains scripts to run various RAG engines on benchmark datasets.

All scripts share a common dataset interface (`RAGDataset.load_auto()`) and output structure.

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
| `--openai-base-url` | `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM API base URL |
| `--embed-base-url` | `EMBED_BASE_URL` | `OPENAI_BASE_URL` | Embedding API base URL |
| `--openai-api-key` | `OPENAI_API_KEY` | — | API key (required) |

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
| `--query-engine` | `QUERY_ENGINE` | `local` | `local` or `query_plan` |
| `--chunker` | `CHUNKER` | `simple` | `simple` or `smart` |
| `--use-chunks` / `--no-use-chunks` | `USE_CHUNKS` | `true` | Use text chunks in queries |
| `--use-summary` / `--no-use-summary` | `USE_SUMMARY` | `false` | Use community summaries |
| `--simple-chunk-size` | `SIMPLE_CHUNK_SIZE` | `2048` | Chunk size (characters) |
| `--simple-chunk-overlap` | `SIMPLE_CHUNK_OVERLAP` | `0` | Chunk overlap |
| `--max-completion-tokens` | `MAX_COMPLETION_TOKENS` | `100000` | Max LLM output tokens |
| `--openai-rate-min-delay` | `OPENAI_RATE_MIN_DELAY` | `2` | Min delay between requests (s) |
| `--openai-rate-max-simultaneous` | `OPENAI_RATE_MAX_SIMULTANEOUS` | `10` | Max concurrent requests |
| `--llm-cache` | `LLM_CACHE` | `tmp/llm_cache` | Response cache directory |
| `--tokenizer-backend` | `TOKENIZER_BACKEND` | `tiktoken` | Tokenizer backend |
| `--tokenizer-llm-name` | `TOKENIZER_LLM_NAME` | `gpt-4o` | Tokenizer model name (LLM) |
| `--tokenizer-embedder-name` | `TOKENIZER_EMBEDDER_NAME` | `gpt-4o` | Tokenizer model name (embedder) |

## Query Engines

### `local` (default)
Single-stage retrieval + LLM answer generation. Good for simple questions.

### `query_plan`
Decomposes complex questions into sub-query DAGs via LLM planning, executes sub-queries in topological order, and returns the final answer. Falls back to the underlying engine when no decomposition is needed.

## Output Structure

```
<output-dir>/<dataset-name>/
├── index/       # Built index (vectors + graph)
└── answers/     # Generated answers (0.txt, 1.txt, ...)
```

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

**Separate containers per dataset:**

When `sample_id=None` (default), triplet search goes through **all collections** in Qdrant.
If multiple datasets are indexed into the same Qdrant, answers for one dataset may
use triplets from another when entities are similar. To avoid
cross-contamination, use a **separate container + volume** per dataset:

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

## Evaluation Scripts

```bash
# Checklist-based RAGU evaluation
python runs/ragu_evaluate.py \
  --dataset-name bl_medium \
  --answers-dir generated/ragu_bl_medium/answers

# LLM-as-judge
python runs/jsonl_llm_judge_evaluate.py \
  --dataset-name multiq \
  --answers-pattern multi_q_*.json

# Chegeka-specific
python runs/chegeka_evaluate.py

# Multi-Q
python runs/multi_q_evaluate.py
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
