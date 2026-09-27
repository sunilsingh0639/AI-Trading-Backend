"""Structured debug logging for the news → prediction → signal pipeline."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("pipeline.debug")


class PipelineDebugService:
    """Emit a traceable record at every pipeline stage."""

    STAGES = (
        "NEWS",
        "CLASSIFICATION",
        "IMPORTANCE",
        "CONTEXT",
        "PROMPT",
        "AI_RESPONSE",
        "VALIDATION",
        "PREDICTION_SAVED",
        "SIGNAL_SAVED",
        "SIGNAL_REJECTED",
        "SKIPPED",
        "EVALUATION",
    )

    @classmethod
    def log_stage(
        cls,
        news_id: int | None,
        stage: str,
        title: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "news_id": news_id,
            "stage": stage,
            "title": (title or "")[:120],
            **(data or {}),
        }
        logger.info("[PIPELINE] %s", json.dumps(payload, default=str, ensure_ascii=True))

    @classmethod
    def log_skip(
        cls,
        news_id: int,
        title: str,
        news_type: str,
        importance: int,
        company: str | None,
        reason: str,
        expected_signal: str | None = None,
    ) -> None:
        cls.log_stage(
            news_id,
            "SKIPPED",
            title,
            {
                "news_type": news_type,
                "importance_score": importance,
                "affected_company": company,
                "reason": reason,
                "expected_signal": expected_signal,
            },
        )

    @classmethod
    def log_signal_rejection(
        cls,
        news_id: int,
        title: str,
        news_type: str,
        importance: int,
        company: str | None,
        ai_recommendation: str,
        ai_confidence: int,
        reasons: list[str],
    ) -> None:
        cls.log_stage(
            news_id,
            "SIGNAL_REJECTED",
            title,
            {
                "news_type": news_type,
                "importance_score": importance,
                "affected_company": company,
                "ai_recommendation": ai_recommendation,
                "ai_confidence": ai_confidence,
                "rejection_reasons": reasons,
            },
        )

    @classmethod
    def log_signal_created(
        cls,
        news_id: int,
        title: str,
        symbol: str,
        recommendation: str,
        confidence: float,
        entry_price: float | None,
        target_price: float | None,
        stop_loss: float | None,
    ) -> None:
        cls.log_stage(
            news_id,
            "SIGNAL_SAVED",
            title,
            {
                "symbol": symbol,
                "recommendation": recommendation,
                "confidence": confidence,
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_loss": stop_loss,
            },
        )
