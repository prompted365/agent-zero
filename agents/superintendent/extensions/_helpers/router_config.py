"""
Bicameral Router Configuration — env-var-driven config for the model orchestrator.

All values read from environment with sensible defaults. This is operational
infrastructure, not user-facing — Docker env vars are the right surface.
"""

import os
from dataclasses import dataclass, field


def _bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes")


@dataclass(frozen=True)
class LaneModelConfig:
    """Configuration for a single utility model lane."""
    provider: str
    name: str
    api_key: str = ""
    api_base: str = ""


@dataclass(frozen=True)
class RouterModelConfig:
    """Configuration for the Gemma 3 circuit-breaker router."""
    provider: str
    name: str
    api_base: str


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Thresholds for circuit-breaker decisions."""
    max_pending: int = 3
    dedup_window: int = 5


@dataclass(frozen=True)
class BicameralConfig:
    """Top-level configuration for the bicameral router."""
    enabled: bool = False
    model_a: LaneModelConfig = field(default_factory=lambda: LaneModelConfig(
        provider="openrouter", name="google/gemini-3-flash-preview",
    ))
    model_b: LaneModelConfig = field(default_factory=lambda: LaneModelConfig(
        provider="openrouter", name="google/gemini-3-flash-preview",
    ))
    router: RouterModelConfig = field(default_factory=lambda: RouterModelConfig(
        provider="ollama", name="gemma3:270m",
        api_base="http://ollama:11434",
    ))
    circuit_breaker: CircuitBreakerConfig = field(
        default_factory=CircuitBreakerConfig,
    )


def load_config() -> BicameralConfig:
    """Load bicameral router config from environment variables."""
    return BicameralConfig(
        enabled=_bool(os.environ.get("BICAM_ENABLED", "false")),
        model_a=LaneModelConfig(
            provider=os.environ.get("BICAM_MODEL_A_PROVIDER", "openrouter"),
            name=os.environ.get("BICAM_MODEL_A_NAME", "google/gemini-3-flash-preview"),
            api_key=os.environ.get("BICAM_MODEL_A_API_KEY", ""),
            api_base=os.environ.get("BICAM_MODEL_A_API_BASE", ""),
        ),
        model_b=LaneModelConfig(
            provider=os.environ.get("BICAM_MODEL_B_PROVIDER", "openrouter"),
            name=os.environ.get("BICAM_MODEL_B_NAME", "google/gemini-3-flash-preview"),
            api_key=os.environ.get("BICAM_MODEL_B_API_KEY", ""),
            api_base=os.environ.get("BICAM_MODEL_B_API_BASE", ""),
        ),
        router=RouterModelConfig(
            provider=os.environ.get("BICAM_ROUTER_PROVIDER", "ollama"),
            name=os.environ.get("BICAM_ROUTER_NAME", "gemma3:270m"),
            api_base=os.environ.get("BICAM_ROUTER_API_BASE", "http://ollama:11434"),
        ),
        circuit_breaker=CircuitBreakerConfig(
            max_pending=int(os.environ.get("BICAM_CIRCUIT_BREAKER_MAX_PENDING", "3")),
            dedup_window=int(os.environ.get("BICAM_CIRCUIT_BREAKER_DEDUP_WINDOW", "5")),
        ),
    )


# --- Lane assignment patterns ---
# Deterministic regex-based fingerprinting of caller by system prompt content.
# Checked in order — first match wins.

LANE_A_PATTERNS = [
    r"memori",         # matches memorize, memorizing, memories, memory
    r"fragments",
    r"solution",
    r"recall",
    r"search query",   # recall prompt: "search query for search engine"
    r"worth memoriz",  # memories_sum: "worth memorizing"
]

LANE_B_PATTERNS = [
    r"entity extraction",
    r"ghost_chorus",
    r"ambient context",
    r"coaching",
    r"epitaph",
    r"invariant",
    r"structural pattern",
]

META_PATTERNS = [
    r"ecotone",
    r"integration.*valid",
    r"integration auditor",
]
