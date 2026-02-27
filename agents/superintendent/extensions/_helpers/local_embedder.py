"""
Local Embedder Adapter — Ollama all-minilm via HTTP.

DIP-384 sovereignty: governance-critical embedding operations
(epitaph minting, chorus retrieval) use the local embedder.
No external API dependency for core governance operations.

Endpoint: http://host.docker.internal:11434 (Ollama)
Model: all-minilm (384-dim, 512-token context)
Latency: 12-16ms (confirmed via preflight 2026-02-27)

Context limit: all-minilm has a 512-token BERT WordPiece context window.
Input is auto-truncated to MAX_INPUT_CHARS (1000) to stay safely within
the token budget. Callers should not need to pre-truncate.
"""

import os
import json
import urllib.request
import urllib.error

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "all-minilm")
EXPECTED_DIM = 384
# 512 BERT tokens ≈ 1000-1400 chars depending on vocabulary density.
# 1000 chars tested safe across civilization_priors, mogul_memory, tps_corpus.
MAX_INPUT_CHARS = 1000


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
    """Embed a single text via local Ollama all-minilm.

    Uses adaptive truncation: tries MAX_INPUT_CHARS first, then
    progressively shorter if the text exceeds the 512-token context.
    Vocabulary-dense text (code, scholarly prose) tokenizes into more
    subwords, so char-based truncation can't guarantee token count.

    Returns a 384-dim vector or None on failure.
    Never raises — caller degrades gracefully.
    """
    if not text or not text.strip():
        return None
    # Try progressively shorter truncations
    for limit in [MAX_INPUT_CHARS, 800, 600, 400]:
        truncated = text[:limit]
        vec = _try_embed(truncated, timeout=timeout)
        if vec is not None:
            return vec
    return None


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
        models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
        return OLLAMA_MODEL in models
    except Exception:
        return False


def get_dim() -> int:
    """Return the expected embedding dimension for this adapter."""
    return EXPECTED_DIM
