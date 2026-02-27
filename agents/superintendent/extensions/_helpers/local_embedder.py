"""
Local Embedder Adapter — Ollama all-minilm via HTTP.

DIP-384 sovereignty: governance-critical embedding operations
(epitaph minting, chorus retrieval) use the local embedder.
No external API dependency for core governance operations.

Endpoint: http://host.docker.internal:11434 (Ollama)
Model: all-minilm (384-dim)
Latency: 12-16ms (confirmed via preflight 2026-02-27)
"""

import os
import json
import urllib.request
import urllib.error

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "all-minilm")
EXPECTED_DIM = 384


def embed_text(text: str, timeout: int = 10) -> list[float] | None:
    """Embed a single text via local Ollama all-minilm.

    Returns a 384-dim vector or None on failure.
    Never raises — caller degrades gracefully.
    """
    try:
        payload = json.dumps({"model": OLLAMA_MODEL, "input": text}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embed",
            data=payload,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())

        embeddings = result.get("embeddings")
        if embeddings and len(embeddings) > 0:
            vec = embeddings[0]
            if len(vec) == EXPECTED_DIM:
                return vec
            print(
                f"[local_embedder] Unexpected dim: got {len(vec)}, "
                f"expected {EXPECTED_DIM}"
            )
            return None
        return None
    except (urllib.error.URLError, Exception) as e:
        print(f"[local_embedder] Ollama embed failed: {e}")
        return None


def embed_batch(texts: list[str], timeout: int = 30) -> list[list[float] | None]:
    """Embed multiple texts. Returns list parallel to input.

    Individual failures return None at that position.
    """
    results = []
    for text in texts:
        results.append(embed_text(text, timeout=timeout))
    return results


def is_available(timeout: int = 3) -> bool:
    """Check if Ollama is reachable and has the embedding model."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
        return OLLAMA_MODEL in models
    except Exception:
        return False


def get_dim() -> int:
    """Return the expected embedding dimension for this adapter."""
    return EXPECTED_DIM
