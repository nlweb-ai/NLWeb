"""HTTP server for NLWebScorer inference.

Runs ModernBERT scorer on CPU, serves scores via HTTP.

Usage:
    python -m inference.server [--port 8090] [--checkpoint checkpoints/modernbert/best_model.pt]
    python -m inference.server --checkpoint https://example.com/models/best_model.pt

API:
    POST /score
    {
        "query": "tent",
        "items": [
            {"name": "...", "schema_json": "..."},
            ...
        ]
    }
    →
    {
        "query": "tent",
        "scores": [
            {"name": "...", "score": 85},
            ...
        ],
        "model": "ModernBERT-base",
        "elapsed_ms": 42
    }
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import torch
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.modernbert_scorer import ModernBERTScorer


def download_checkpoint(url: str) -> str:
    """Download checkpoint from URL to a temp file. Returns local path."""
    import urllib.request
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".pt"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    print(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, tmp.name)
    size_mb = os.path.getsize(tmp.name) / 1e6
    print(f"Downloaded {size_mb:.0f} MB → {tmp.name}")
    return tmp.name


class ScorerModel:
    """Lightweight scorer using just the ModernBERT regression head."""

    def __init__(self, checkpoint: str, device: str = "cpu",
                 max_length: int = 256):
        self.device = torch.device(device)
        self.max_length = max_length

        # Load from URL or local file
        if checkpoint.startswith("http://") or checkpoint.startswith("https://"):
            checkpoint = download_checkpoint(checkpoint)

        state = torch.load(checkpoint, map_location=self.device,
                           weights_only=False)
        self.config = state["config"]
        model_name = self.config.get("model_name", "answerdotai/ModernBERT-base")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = ModernBERTScorer(model_name=model_name).to(self.device)
        self.model.load_state_dict(state["model_state_dict"])
        self.model.eval()

    @torch.no_grad()
    def score(self, query: str, items: list[dict]) -> list[dict]:
        if not items:
            return []

        texts = []
        for item in items:
            desc = item.get("schema_json", item.get("name", ""))
            if len(desc) > 2000:
                desc = desc[:2000]
            texts.append(f"{query} [SEP] {desc}")

        encodings = self.tokenizer(
            texts, max_length=self.max_length, padding=True,
            truncation=True, return_tensors="pt"
        ).to(self.device)

        preds = self.model(encodings["input_ids"], encodings["attention_mask"])
        scores_100 = (preds.squeeze(-1) * 100).clamp(0, 100)

        return [
            {"name": item.get("name", ""), "score": int(s.round().item())}
            for item, s in zip(items, scores_100)
        ]


def make_handler(scorer: ScorerModel):

    class Handler(BaseHTTPRequestHandler):

        def do_POST(self):
            if self.path != "/score":
                self.send_error(404)
                return

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)

            try:
                req = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            query = req.get("query", "")
            items = req.get("items", [])

            if not query:
                self.send_error(400, "Missing 'query'")
                return

            t0 = time.time()
            results = scorer.score(query, items)
            elapsed_ms = int((time.time() - t0) * 1000)

            response = {
                "query": query,
                "scores": results,
                "model": "ModernBERT-base",
                "elapsed_ms": elapsed_ms,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_error(404)

        def log_message(self, fmt, *args):
            print(f"[{time.strftime('%H:%M:%S')}] {fmt % args}")

    return Handler


def main():
    parser = argparse.ArgumentParser(description="NLWebScorer HTTP server")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--checkpoint", type=str,
                        default="checkpoints/modernbert/best_model.pt")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args()

    print(f"Loading model from {args.checkpoint}...")
    scorer = ScorerModel(args.checkpoint, device=args.device,
                         max_length=args.max_length)
    print(f"Model loaded on {args.device}")

    server = HTTPServer(("0.0.0.0", args.port), make_handler(scorer))
    print(f"Serving on http://0.0.0.0:{args.port}")
    print(f"  POST /score  — score items against a query")
    print(f"  GET  /health — health check")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
