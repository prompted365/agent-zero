"""
Tricameral Router Configuration — env-var-driven config for the model orchestrator.

All values read from environment with sensible defaults. This is operational
infrastructure, not user-facing — Docker env vars are the right surface.

Lane A: narrative priors (Aesop/Prophet, FAISS recall)
Lane B: empirical recall (RuVector, user memory)
Lane C: governance priors (Councils + triggers + constraints) [Phase 2]

Env vars support both TRICAM_ and BICAM_ prefixes for backwards compatibility.
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
class LaneCConfig:
    """Configuration for the Lane C governance coherence gate."""
    enabled: bool = False
    incompatibility_lock_threshold: float = 0.40
    min_activated_councils: int = 2
    min_amplitude: float = 0.10


@dataclass(frozen=True)
class TricameralConfig:
    """Top-level configuration for the tricameral router."""
    enabled: bool = False
    model_a: LaneModelConfig = field(default_factory=lambda: LaneModelConfig(
        provider="openrouter", name="qwen/qwen3.5-plus-02-15",
    ))
    model_b: LaneModelConfig = field(default_factory=lambda: LaneModelConfig(
        provider="openrouter", name="qwen/qwen3.5-plus-02-15",
    ))
    router: RouterModelConfig = field(default_factory=lambda: RouterModelConfig(
        provider="ollama", name="gemma3:270m",
        api_base="http://ollama:11434",
    ))
    circuit_breaker: CircuitBreakerConfig = field(
        default_factory=CircuitBreakerConfig,
    )
    lane_c: LaneCConfig = field(default_factory=LaneCConfig)


def _env(key: str, default: str = "") -> str:
    """Read env var with TRICAM_ prefix, falling back to BICAM_ for compat."""
    return os.environ.get(f"TRICAM_{key}", os.environ.get(f"BICAM_{key}", default))


def load_config() -> TricameralConfig:
    """Load tricameral router config from environment variables."""
    return TricameralConfig(
        enabled=_bool(_env("ENABLED", "false")),
        model_a=LaneModelConfig(
            provider=_env("MODEL_A_PROVIDER", "openrouter"),
            name=_env("MODEL_A_NAME", "qwen/qwen3.5-plus-02-15"),
            api_key=_env("MODEL_A_API_KEY"),
            api_base=_env("MODEL_A_API_BASE"),
        ),
        model_b=LaneModelConfig(
            provider=_env("MODEL_B_PROVIDER", "openrouter"),
            name=_env("MODEL_B_NAME", "qwen/qwen3.5-plus-02-15"),
            api_key=_env("MODEL_B_API_KEY"),
            api_base=_env("MODEL_B_API_BASE"),
        ),
        router=RouterModelConfig(
            provider=_env("ROUTER_PROVIDER", "ollama"),
            name=_env("ROUTER_NAME", "gemma3:270m"),
            api_base=_env("ROUTER_API_BASE", "http://ollama:11434"),
        ),
        circuit_breaker=CircuitBreakerConfig(
            max_pending=int(_env("CIRCUIT_BREAKER_MAX_PENDING", "3")),
            dedup_window=int(_env("CIRCUIT_BREAKER_DEDUP_WINDOW", "5")),
        ),
        lane_c=LaneCConfig(
            enabled=_bool(_env("LANE_C_ENABLED", "false")),
            incompatibility_lock_threshold=float(
                _env("LANE_C_LOCK_THRESHOLD", "0.40")
            ),
            min_activated_councils=int(
                _env("LANE_C_MIN_COUNCILS", "2")
            ),
            min_amplitude=float(
                _env("LANE_C_MIN_AMPLITUDE", "0.10")
            ),
        ),
    )


# Backwards compatibility alias
BicameralConfig = TricameralConfig


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

LANE_C_PATTERNS = [
    r"governance",
    r"council",
    r"tension cluster",
    r"pole[_ ]?a|pole[_ ]?b",
    r"incompatib",
    r"coherence gate",
    r"coordination trigger",
    r"conformity trap",
    r"perception lock",
]

META_PATTERNS = [
    r"ecotone",
    r"integration.*valid",
    r"integration auditor",
]
