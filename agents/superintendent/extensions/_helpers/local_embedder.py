"""
Local Embedder Adapter — Ollama qwen3-embedding:0.6b via HTTP.

DIP-384 sovereignty: governance-critical embedding operations
(epitaph minting, chorus retrieval) use the local embedder.
No external API dependency for core governance operations.

Endpoint: http://host.docker.internal:11434 (Ollama)
Model: qwen3-embedding:0.6b (1024-dim native, MRL-truncated to 384-dim)
Latency: 12-16ms (confirmed via preflight 2026-02-27)

Context: qwen3-embedding:0.6b has 32k token context — no adaptive
truncation needed. MAX_INPUT_CHARS is a safety ceiling, not a tight budget.
"""

import math
import os
import json
import urllib.request
import urllib.error

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "qwen3-embedding:0.6b")
EXPECTED_DIM = 384
# 32k token context. 32000 chars covers all practical document lengths.
MAX_INPUT_CHARS = 32000


def _mrl_truncate(vec: list[float], dim: int) -> list[float]:
    """Matryoshka Representation Learning truncation: slice + L2 normalize."""
    truncated = vec[:dim]
    norm = math.sqrt(sum(x * x for x in truncated))
    if norm > 0:
        return [x / norm for x in truncated]
    return truncated


def _try_embed(text: str, timeout: int = 10) -> list[float] | None:
    """Single embed attempt. Returns vector or None."""
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
            # MRL truncation for models with higher native dim (e.g. 1024D → 384D)
            if len(vec) > EXPECTED_DIM:
                return _mrl_truncate(vec, EXPECTED_DIM)
            print(
                f"[local_embedder] Unexpected dim: got {len(vec)}, "
                f"expected {EXPECTED_DIM}"
            )
        return None
    except urllib.error.HTTPError as e:
        if e.code == 400:
            return None  # Context length exceeded — caller should retry shorter
        print(f"[local_embedder] Ollama HTTP {e.code}: {e.reason}")
        return None
    except (urllib.error.URLError, Exception) as e:
        print(f"[local_embedder] Ollama embed failed: {e}")
        return None


def embed_text(text: str, timeout: int = 10) -> list[float] | None:
    """Embed a single text via local Ollama embedder.

    Truncates to MAX_INPUT_CHARS (safety ceiling — the model has
    32k token context, so this is rarely hit). Returns a 384-dim
    vector or None on failure.

    Never raises — caller degrades gracefully.
    """
    if not text or not text.strip():
        return None
    truncated = text[:MAX_INPUT_CHARS]
    return _try_embed(truncated, timeout=timeout)


def embed_batch(texts: list[str], timeout: int = 30) -> list[list[float] | None]:
    """Embed multiple texts. Returns list parallel to input.

    Individual failures return None at that position.
    Auto-truncation applied per text.
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
        # Compare full names (with tag) and base names (without tag)
        model_names = set()
        for m in data.get("models", []):
            name = m.get("name", "")
            model_names.add(name)
            model_names.add(name.split(":")[0])
        return OLLAMA_MODEL in model_names or OLLAMA_MODEL.split(":")[0] in model_names
    except Exception:
        return False


def get_dim() -> int:
    """Return the expected embedding dimension for this adapter."""
    return EXPECTED_DIM
