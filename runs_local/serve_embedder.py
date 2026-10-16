"""Serve a sentence-transformers embedder behind an OpenAI-compatible ``/v1/embeddings``.

On the cluster the embedder of RAGU indexes (gte-multilingual-base) is served by
vLLM. vLLM does not run natively on Windows, but answering over an exported
index only needs the *query* side, so a small local server is enough. RAGU
talks to it through ``EmbedderOpenAI`` exactly as it talks to vLLM:

    python runs_local/serve_embedder.py --port 8002
    python runs/ragu_run.py ... --embed-base-url http://127.0.0.1:8002/v1 \\
        --embedding-model-name gte-multilingual-base --embedding-dim 768

Queries must be embedded by the same model that embedded the index, otherwise
vector search returns noise without any error. ``runs_local/check_embedder.py``
re-embeds texts stored in an index and compares them to the stored vectors.

Supported requests: ``POST /v1/embeddings`` with ``input`` as a string or a list
of strings and ``encoding_format`` ``float`` or ``base64`` (the OpenAI SDK asks
for ``base64`` by default), and ``GET /v1/models``.

Dependencies (a separate venv is fine): ``sentence-transformers`` and ``torch``.
For an RTX 50xx GPU install a CUDA 12.8 build of torch; on CPU any build works.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--model",
        default=os.environ.get("EMBED_MODEL", "Alibaba-NLP/gte-multilingual-base"),
        help="HF model id or local path (env EMBED_MODEL)",
    )
    parser.add_argument(
        "--served-model-name",
        default=os.environ.get("EMBED_MODEL_NAME", "gte-multilingual-base"),
        help="Name reported by /v1/models; requests may use any name (env EMBED_MODEL_NAME)",
    )
    parser.add_argument("--host", default=os.environ.get("EMBED_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("EMBED_PORT", "8002")))
    parser.add_argument(
        "--device",
        default=os.environ.get("EMBED_DEVICE", "auto"),
        help="cuda, cpu or auto (env EMBED_DEVICE)",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=8192,
        help="Truncation length in tokens; gte-multilingual-base supports 8192",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Return raw pooled vectors (vLLM normalizes embeddings by default)",
    )
    return parser.parse_args()


class EmbeddingService:
    """Thread-safe wrapper around one SentenceTransformer model."""

    def __init__(self, args: argparse.Namespace):
        import torch
        from sentence_transformers import SentenceTransformer

        device = args.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        started = time.time()
        self.model = SentenceTransformer(args.model, device=device, trust_remote_code=True)
        self.model.max_seq_length = args.max_seq_length
        # sentence-transformers >= 5.4 renamed the method
        get_dim = getattr(self.model, "get_embedding_dimension", None) or \
            self.model.get_sentence_embedding_dimension
        self.dim = get_dim()
        self.batch_size = args.batch_size
        self.normalize = not args.no_normalize
        self.name = args.served_model_name
        self._lock = threading.Lock()
        print(
            f"Loaded {args.model} on {device} in {time.time() - started:.1f}s: "
            f"dim={self.dim}, max_seq_length={self.model.max_seq_length}, "
            f"normalize={self.normalize}",
            flush=True,
        )

    def embed(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            vectors = self.model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=self.normalize,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return np.asarray(vectors, dtype=np.float32)


def make_handler(service: EmbeddingService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status: int, message: str) -> None:
            self._send(status, {"error": {"message": message, "type": "invalid_request_error"}})

        def do_GET(self) -> None:
            if self.path.rstrip("/").endswith("/models"):
                self._send(200, {"object": "list", "data": [
                    {"id": service.name, "object": "model", "owned_by": "local"},
                ]})
            elif self.path.rstrip("/").endswith("/health"):
                self._send(200, {"status": "ok"})
            else:
                self._error(404, f"Unknown path {self.path}")

        def do_POST(self) -> None:
            if not self.path.rstrip("/").endswith("/embeddings"):
                self._error(404, f"Unknown path {self.path}")
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
            except (ValueError, json.JSONDecodeError) as exc:
                self._error(400, f"Bad JSON body: {exc}")
                return

            raw = body.get("input")
            texts = [raw] if isinstance(raw, str) else raw
            if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
                self._error(400, "'input' must be a string or a list of strings")
                return
            encoding_format = body.get("encoding_format") or "float"
            if encoding_format not in ("float", "base64"):
                self._error(400, f"Unsupported encoding_format {encoding_format!r}")
                return

            vectors = service.embed(texts) if texts else np.zeros((0, service.dim), np.float32)
            data = []
            for i, vector in enumerate(vectors):
                embedding: Any = (
                    base64.b64encode(vector.tobytes()).decode()
                    if encoding_format == "base64" else vector.tolist()
                )
                data.append({"object": "embedding", "index": i, "embedding": embedding})
            self._send(200, {
                "object": "list",
                "data": data,
                "model": body.get("model", service.name),
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            })

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


def main() -> None:
    args = parse_args()
    service = EmbeddingService(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(service))
    print(f"Serving /v1/embeddings at http://{args.host}:{args.port}/v1", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
