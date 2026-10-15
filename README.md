# natural_rag

A research framework for running Retrieval-Augmented Generation (RAG) pipelines — primarily GraphRAG — on diverse question-answering benchmarks.

## Project Structure

```
natural_rag/
├── natural_rag/           # Python package
│   ├── dataset.py         # Dataset loading (YAML, JSONL, JSON auto-detect)
│   ├── benchmarks.py      # Benchmark registry (name → path, format, flags)
│   ├── data.py            # Data model
│   ├── paths.py           # Output-dir resolver (<engine>_<dataset>/<dataset>/[<model>]/...)
│   ├── timing.py          # Indexing time / LLM-call accounting
│   ├── graph_health.py    # Corpus coverage checks (empty_docs, triplets)
│   ├── dashboard.py       # Dash-based result viewer
│   ├── baseline/          # Baseline RAG implementations
│   └── pipelines/         # RAG pipeline wrappers (RAGUPipeline, etc.)
├── runs/                  # Canonical per-engine runners + evaluation (README.md inside)
├── runs_cluster/          # SLURM wrappers for the NSU cluster (README.md inside)
├── runs_local/            # Local answering/eval over exported indexes (README.md inside)
├── scripts/               # Repo self-check (validate_repo.py) and setup utilities
├── datasets/              # Benchmark datasets (see docs/benchmarks.md)
├── notebooks/             # BL corpus preparation notebooks
├── legacy/                # Original BL questions before cleanup
├── docs/                  # benchmarks.md, research journal
└── pyproject.toml
```

One engine — one canonical runner in `runs/` (RAGU: `ragu_run.py`, LightRAG:
`lightrag_run.py`, …). Every combination of «dataset × engine × model» is a
matter of flags/environment, not a new script.

Output layout (see `natural_rag/paths.py`):

```
generated/<engine>_<dataset>/<dataset>/[<index-model>/]{index,answers}
# e.g. generated/ragu_bioasq/bioasq/gpt-oss-20b/{index,answers}
```

The `<index-model>` segment (from `--index-model`, e.g. `gpt-oss-20b`) is
optional and lets graphs built by different models coexist side by side.

## Setup

```bash
# Install base framework (without RAGU)
uv pip install -e .

# Install with RAGU — the primary engine (recommended)
uv pip install -e ".[ragu]"
```

Requires Python 3.12+. Base dependencies: `openai`, `pydantic`, `httpx[socks]`, `dash`, etc.
Add `.[ragu]` to also install RAGU (`graph-ragu`) from GitHub — see [Engine-Specific Dependencies](#engine-specific-dependencies) for other engines.

> **The release and dev builds of RAGU are mutually exclusive** — both provide
> the `ragu` package (the dev branch takes `EngineParams` in
> `a_search`/`a_query`). Install exactly one: the release via `.[ragu]`, the
> dev branch via the manual command in [runs/README.md](runs/README.md#installing-ragu)
> (a git-URL extra would make `uv lock` fail on two URLs for one package, so
> dev is not an extra).

## Datasets

Nine benchmarks are committed to the repo; three more (multiq, chegeka,
graphrag_bench_medical) are installed manually. Full table with document and
question counts, languages and per-benchmark flags:
[docs/benchmarks.md](docs/benchmarks.md). Supported formats:

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

Smoke-testing any benchmark on a slice of the data:

```bash
... ragu_run.py --dataset-path datasets/bioasq --limit-docs 50 --limit-questions 5 ...
```

### Short-answer mode & NaiveRAG

For benchmarks whose gold answers are short (bioasq, musique, 2wikimultihopqa),
long generations get under-scored. Pass `--short-answers` to make RAGU **and**
LightRAG emit a terse, extractive answer (a single entity/name/number/date or a
short `;`-separated list, `I don't know.` when unsupported). For LightRAG this
also strips its `### References` section.

`ragu_run.py --query-engine naive` runs **NaiveRAG** — plain vector RAG over the
index's text chunks (no graph traversal), reusing the same RAGU index. Use
`--index-model <name>` (e.g. `gpt-oss-20b`) to keep graphs from different builder
models in separate folders.

## Evaluation

```bash
# Checklist-based evaluation (BL family)
uv run python runs/ragu_evaluate.py \
  --dataset-name bl_tiny \
  --answers-dir generated/ragu_bl_tiny/answers

# Consolidate per-question .txt answers into one JSON, then LLM-as-judge
uv run python runs/convert_answers.py \
  --dataset-name bl_medium \
  --answers-dir generated/ragu_bl_medium/answers
uv run python runs/jsonl_llm_judge_evaluate.py \
  --dataset-name bl_medium \
  --answers-dir generated/ragu_bl_medium/answers \
  --judge-model Qwen2.5-14B-Instruct
```

### GraphRAG-Benchmark generation eval

To score answers with [GraphRAG-Benchmark](https://github.com/bond005/GraphRAG-Benchmark)
(judge `gemini-3-flash-preview`, embedder `text-embedding-3-small`), first build
the eval input, then run `generation_eval` from that repo:

```bash
python runs/build_graphrag_bench_input.py \
  --dataset-path datasets/bioasq \
  --output-dir generated/ragu_bioasq --index-model gpt-oss-20b
```

See [runs/README.md](runs/README.md#evaluation-with-graphrag-benchmark) for the
full flow (input schema, `question_type` → metric mapping, and the
`generation_eval` command).

## Cluster and local workflows

Heavy indexing runs on the NSU cluster (SLURM, one sbatch wrapper per engine
family): see [runs_cluster/README.md](runs_cluster/README.md). Answering and
evaluation happen locally against exported indexes via an API LLM:
[runs_local/README.md](runs_local/README.md).

## Self-check (no GPU, no LLM calls)

```bash
python scripts/validate_repo.py   # every benchmark loads; all .py/.sh parse
python runs/test_all.py --dry-run # print every pipeline's command
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
uv pip install -e ".[wikontic]"
uv pip install -e ".[baseline]"

# The compatible-together set (RAGU, baseline, LightRAG, NanoGraphRAG, Wikontic)
uv pip install -e ".[all]"
```

> `fast-graphrag` and `hipporag` pin incompatible `openai`/`tiktoken`
> generations and must live in their OWN environments
> (`uv pip install -e ".[fast-graphrag]"`), as the cluster setup has always
> done. `uv lock` models this via `[tool.uv] conflicts`.

> **Recommendation**: Start with `uv pip install -e ".[ragu]"` — this is the engine used in `runs/ragu_run.py`, evaluation scripts (`ragu_evaluate.py`, `jsonl_llm_judge_evaluate.py`), and most of the codebase.

### System Prerequisites

Some engines pull in packages with native extensions that require a C++ compiler and Python headers:

| Engine | Native package | Install system deps (Ubuntu/Debian) |
|--------|---------------|--------------------------------------|
| `fast-graphrag` | `hnswlib` (C++ HNSW index) | `sudo apt install python3-dev build-essential` |
| `hipporag` | `torch` (CUDA-enabled) | `sudo apt install build-essential` (CUDA toolkit is optional) |
| `wikontic` | `torch` (CUDA-enabled), `transformers` (tokenizers, Rust extensions) | `sudo apt install python3-dev build-essential` (CUDA toolkit is optional) |

Without these, `uv pip install` may fail when building the native extension from source.
If you only plan to use RAGU, LightRAG, NanoGraphRAG, the baseline, or Wikontic (CPU mode), no system packages are required beyond Python itself. For Wikontic GPU mode, a CUDA toolkit is recommended.

### Engine Reference

| Engine | Run Script | Dependency | Extras Key | Default? |
|--------|------------|-----------|------------|----------|
| **RAGU** 🏆 | `runs/ragu_run.py` | `graph-ragu @ git+https://github.com/RaguTeam/RAGU.git` | `ragu` | Yes |
| **Baseline** | `runs/baseline_run.py` | RAGU + `diskcache` | `baseline` | No |
| **LightRAG** | `runs/lightrag_run.py` | `lightrag-hku`, `numpy` | `lightrag` | No |
| **NanoGraphRAG** | `runs/nano_graphrag_run.py` | `nano-graphrag`, `numpy` | `nano-graphrag` | No |
| **FastGraphRAG** | `runs/fast_graphrag_run.py` | `fast-graphrag`, `instructor`, `aiohttp` | `fast-graphrag` | No |
| **HippoRAG** | `runs/run_hippo.py` | `hipporag` (→ `torch`, `transformers`, `vllm`) | `hipporag` | No |
| **Wikontic** | `runs/wikontic_run.py` | `wikontic @ git+...` (→ `torch`, `transformers`, `qdrant-client`) | `wikontic` | No |

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
├── run_hippo.py              # → pipelines/hipporag_pipelines.py
└── wikontic_run.py           # → pipelines/wikontic_pipeline.py
```
