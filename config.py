"""Centralised pipeline configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class PipelineConfig:
    """Thresholds and toggles for the news → prediction → signal pipeline."""

    # Minimum importance score (0-100) before a headline is sent to the LLM.
    MIN_IMPORTANCE_SCORE: int = _int("MIN_IMPORTANCE_SCORE", 35)

    # Minimum combined confidence required to persist a trading signal.
    MIN_SIGNAL_CONFIDENCE: int = _int("MIN_SIGNAL_CONFIDENCE", 55)

    # When True, a strong technical contradiction can block signal creation.
    REQUIRE_TECHNICAL_ALIGNMENT: bool = os.getenv(
        "REQUIRE_TECHNICAL_ALIGNMENT", "false"
    ).lower() in {"1", "true", "yes"}

    # Technical score must differ from neutral by at least this much to count as a
    # "strong" contradiction that blocks a signal when alignment is required.
    TECHNICAL_CONTRADICTION_THRESHOLD: int = _int("TECHNICAL_CONTRADICTION_THRESHOLD", 70)

    # Default expected holding horizon in minutes when no technical plan exists.
    DEFAULT_HOLDING_MINUTES: int = _int("DEFAULT_HOLDING_MINUTES", 30)

    # Default risk-reward ratio for news-only signals without ATR data.
    DEFAULT_RISK_REWARD_RATIO: float = _float("DEFAULT_RISK_REWARD_RATIO", 1.5)

    # Percentage used for target/stop when ATR is unavailable.
    DEFAULT_TARGET_PCT: float = _float("DEFAULT_TARGET_PCT", 1.5)
    DEFAULT_STOP_PCT: float = _float("DEFAULT_STOP_PCT", 1.0)

    # Batch sizes
    ANALYSIS_BATCH_SIZE: int = _int("ANALYSIS_BATCH_SIZE", 10)
    EVALUATION_BATCH_SIZE: int = _int("EVALUATION_BATCH_SIZE", 20)
    EVALUATION_HORIZON_MINUTES: int = _int("EVALUATION_HORIZON_MINUTES", 30)

    # News provider settings
    NEWS_PROVIDER_TIMEOUT_SECONDS: int = _int("NEWS_PROVIDER_TIMEOUT_SECONDS", 10)
    NEWS_PROVIDER_FAILURE_THRESHOLD: int = _int("NEWS_PROVIDER_FAILURE_THRESHOLD", 3)
    NEWS_PROVIDER_COOLDOWN_SECONDS: int = _int("NEWS_PROVIDER_COOLDOWN_SECONDS", 60)
