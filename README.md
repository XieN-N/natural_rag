# natural_rag

A research framework for running Retrieval-Augmented Generation (RAG) pipelines — primarily GraphRAG — on diverse question-answering benchmarks.

## Project Structure

```
natural_rag/
├── natural_rag/           # Python package
│   ├── dataset.py         # Dataset loading (YAML, JSONL, JSON auto-detect)
│   ├── data.py            # Data model
│   ├── dashboard.py       # Dash-based result viewer
│   ├── baseline/          # Baseline RAG implementations
│   └── pipelines/         # RAG pipeline wrappers (RAGUPipeline, etc.)
├── runs/                  # Run scripts for various RAG engines
├── datasets/              # Benchmark datasets (bl_tiny, bl, musique, etc.)
├── generated/             # Output: indexes + answers
├── src/                   # Vendored dependencies (graph-ragu)
├── build/                 # Build artifacts
└── pyproject.toml
```

## Setup

```bash
# Install base framework (without RAGU)
uv pip install -e .

# Install with RAGU — the primary engine (recommended)
uv pip install -e ".[ragu]"
```

Requires Python 3.12+. Base dependencies: `openai`, `pydantic`, `httpx[socks]`, `dash`, etc.
Add `.[ragu]` to also install RAGU (`graph-ragu`) from GitHub — see [Engine-Specific Dependencies](#engine-specific-dependencies) for other engines.

## Datasets

Datasets live in `datasets/`. Supported formats:

| Format | Files | Example |
|--------|-------|---------|
| YAML   | `corpus_info.yaml` + `questions.yaml` + `docs/` | `bl_tiny/` |
| JSONL  | `corpus.jsonl` + `questions.jsonl` | `bioasq/` |
| JSON   | Single `.json` file | `2wikimultihopqa/` |

Load any dataset with:

```python
from natural_rag.dataset import RAGDataset
dataset = RAGDataset.load_auto("datasets/bl_tiny")
```

## Running RAGU

The primary run script is `runs/ragu_run.py`. See [runs/README.md](runs/README.md) for full usage.

Quick start with local embedding server + OpenAI-compatible LLM:

```bash
export OPENAI_BASE_URL="https://api.vsellm.ru/v1"
export EMBED_BASE_URL="http://127.0.0.1:8080/v1"
export OPENAI_API_KEY="your-key"
export LLM_MODEL="qwen/qwen3-vl-8b-instruct"
export EMBED_MODEL="/data"
export EMBEDDING_DIM="768"

uv run python runs/ragu_run.py \
  --dataset-path datasets/bl_tiny \
  --output-dir generated/ragu_bl_tiny \
  --no-build-index \
  --answer \
  --query-engine query_plan \
  --embed-batch-size 32
```

## Evaluation

```bash
# Checklist-based evaluation
uv run python runs/ragu_evaluate.py \
  --dataset-name bl_tiny \
  --answers-dir generated/ragu_bl_tiny/answers

# LLM-as-judge evaluation  
uv run python runs/jsonl_llm_judge_evaluate.py \
  --dataset-name bl_medium \
  --answers-pattern ragu_*.json
```

## Dashboard

```bash
uv run python natural_rag/dashboard.py
```

Opens a Dash web UI for browsing results.

## Engine-Specific Dependencies

The framework supports multiple RAG engines. **RAGU** is the primary, preferred engine — most run and evaluation scripts depend on it. Other engines are alternatives for comparison.

Each engine's Python dependencies are declared as **optional extras**. Install only what you need.

### Quick Install

```bash
# Base framework only (no engine)
uv pip install -e .

# Install with RAGU — the default / primary engine
uv pip install -e ".[ragu]"

# Install other engines
uv pip install -e ".[lightrag]"
uv pip install -e ".[nano-graphrag]"
uv pip install -e ".[fast-graphrag]"
uv pip install -e ".[hipporag]"
uv pip install -e ".[baseline]"

# All engines at once
uv pip install -e ".[all]"
```

> **Recommendation**: Start with `uv pip install -e ".[ragu]"` — this is the engine used in `runs/ragu_run.py`, evaluation scripts (`ragu_evaluate.py`, `jsonl_llm_judge_evaluate.py`), and most of the codebase.

### System Prerequisites

Some engines pull in packages with native extensions that require a C++ compiler and Python headers:

| Engine | Native package | Install system deps (Ubuntu/Debian) |
|--------|---------------|--------------------------------------|
| `fast-graphrag` | `hnswlib` (C++ HNSW index) | `sudo apt install python3-dev build-essential` |
| `hipporag` | `torch` (CUDA-enabled) | `sudo apt install build-essential` (CUDA toolkit is optional) |

Without these, `uv pip install` may fail when building the native extension from source.
If you only plan to use RAGU, LightRAG, NanoGraphRAG, or the baseline, no system packages are required beyond Python itself.

### Engine Reference

| Engine | Run Script | Dependency | Extras Key | Default? |
|--------|------------|-----------|------------|----------|
| **RAGU** 🏆 | `runs/ragu_run.py` | `graph-ragu @ git+https://github.com/RaguTeam/RAGU.git` | `ragu` | Yes |
| **Baseline** | `runs/baseline_run.py` | RAGU + `diskcache` | `baseline` | No |
| **LightRAG** | `runs/lightrag_run.py` | `lightrag-hku`, `numpy` | `lightrag` | No |
| **NanoGraphRAG** | `runs/nano_graphrag_run.py` | `nano-graphrag`, `numpy` | `nano-graphrag` | No |
| **FastGraphRAG** | `runs/fast_graphrag_run.py` | `fast-graphrag`, `instructor`, `aiohttp` | `fast-graphrag` | No |
| **HippoRAG** | `runs/run_hippo.py` | `hipporag` (→ `torch`, `transformers`, `vllm`) | `hipporag` | No |

> **HippoRAG** pulls in a large dependency chain (`torch`, `transformers`, `vllm`, `python-igraph`, etc.). Expect a longer install time and significant disk usage.
>
> **Baseline** is a tree-structured RAG approach (no knowledge graph). It depends on RAGU for LLM and caching utilities.

### Run Scripts vs Pipelines

All run scripts share the same `RAGDataset` interface and output structure. The mapping:

```
runs/
├── ragu_run.py               # → pipelines/ragu_pipelines.py     (RAGU)
├── baseline_run.py           # → natural_rag/baseline/           (no wrapper)
├── lightrag_run.py           # → pipelines/lightrag_pipelines.py
├── nano_graphrag_run.py      # → pipelines/nano_graphrag_pipelines.py
├── fast_graphrag_run.py      # → pipelines/fast_graphrag_pipelines.py
└── run_hippo.py              # → pipelines/hipporag_pipelines.py
```
