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
