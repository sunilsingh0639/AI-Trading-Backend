from __future__ import annotations

from datetime import timedelta
import logging
import os

import pandas as pd
import yfinance as yf

from repositories.prediction_evaluation_repository import PredictionEvaluationRepository
from services.market_prediction_service import IntradayPredictionService

logger = logging.getLogger(__name__)


class PredictionEvaluationService:
    """Labels completed trades with a fixed horizon, without using future bars in signals."""

    @staticmethod
    def _exit_price_at_horizon(prediction, horizon_minutes: int) -> float | None:
        if not prediction.symbol or not prediction.created_on:
            return None

        start = prediction.created_on
        target = start + timedelta(minutes=horizon_minutes)
        try:
            bars = yf.download(
                IntradayPredictionService.normalise_symbol(prediction.symbol),
                start=start - timedelta(minutes=5),
                end=target + timedelta(minutes=15),
                interval="5m",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception as error:
            logger.warning("Could not evaluate prediction %s: %s", prediction.id, error)
            return None

        if bars is None or bars.empty:
            return None
        if isinstance(bars.columns, pd.MultiIndex):
            bars.columns = [column[0] for column in bars.columns]
        if "Close" not in bars.columns:
            return None

        close = pd.to_numeric(bars["Close"], errors="coerce").dropna()
        if close.empty:
            return None

        target_timestamp = pd.Timestamp(target)
        try:
            at_or_after_horizon = close.loc[close.index >= target_timestamp]
        except TypeError:
            # yfinance may return naive indexes for an instrument; compare as naive only
            # after retaining the same wall-clock evaluation horizon.
            at_or_after_horizon = close.loc[
                close.index.tz_localize(None) >= target_timestamp.tz_localize(None)
            ]
        if at_or_after_horizon.empty:
            return None
        return float(at_or_after_horizon.iloc[0])

    @classmethod
    def evaluate_due_predictions(cls, db, horizon_minutes: int | None = None) -> dict:
        horizon = horizon_minutes or int(os.getenv("EVALUATION_HORIZON_MINUTES", "30"))
        batch_size = int(os.getenv("EVALUATION_BATCH_SIZE", "20"))
        predictions = PredictionEvaluationRepository.get_due_predictions(db, horizon, batch_size)
        evaluated = 0
        unavailable = 0
        failed = 0

        for prediction in predictions:
            try:
                exit_price = cls._exit_price_at_horizon(prediction, horizon)
                if exit_price is None:
                    unavailable += 1
                    continue

                entry_price = float(prediction.entry_price)
                if prediction.recommendation == "BUY":
                    realised_return = ((exit_price / entry_price) - 1) * 100
                elif prediction.recommendation == "SELL":
                    realised_return = ((entry_price / exit_price) - 1) * 100
                else:
                    prediction.status = "REJECTED"
                    db.commit()
                    continue

                PredictionEvaluationRepository.save(
                    db,
                    {
                        "prediction_id": prediction.id,
                        "symbol": prediction.symbol,
                        "horizon_minutes": horizon,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "realised_return_pct": realised_return,
                        "is_correct": realised_return > 0,
                    },
                )
                prediction.status = "EVALUATED"
                db.commit()
                evaluated += 1
            except Exception:
                db.rollback()
                failed += 1
                logger.exception("Could not persist evaluation for prediction %s", prediction.id)

        return {
            "due": len(predictions),
            "evaluated": evaluated,
            "dataUnavailable": unavailable,
            "failed": failed,
            "horizonMinutes": horizon,
        }

    @staticmethod
    def performance_summary(db) -> dict:
        evaluations = PredictionEvaluationRepository.get_all(db)
        total = len(evaluations)
        correct = sum(1 for row in evaluations if row.is_correct)
        false_positives = sum(
            1 for row in evaluations if not row.is_correct and row.realised_return_pct <= 0
        )
        false_negatives = 0  # Requires tracking missed opportunities separately
        average_return = (
            sum(row.realised_return_pct for row in evaluations) / total if total else 0.0
        )
        total_profit_pct = sum(row.realised_return_pct for row in evaluations)
        return {
            "totalEvaluated": total,
            "correct": correct,
            "hitRatePercent": round((correct / total) * 100, 2) if total else None,
            "averageReturnPercent": round(average_return, 4),
            "totalProfitLossPercent": round(total_profit_pct, 4),
            "falsePositives": false_positives,
            "falseNegatives": false_negatives,
            "note": "Measured realised outcomes, not a future-performance guarantee.",
        }
