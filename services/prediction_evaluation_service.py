"""Prediction evaluation service.

Timestamp flow (traced explicitly):
  prediction.created_on
      → TIMESTAMP(timezone=True) in PostgreSQL
      → SQLAlchemy returns a timezone-aware datetime in UTC
      → converted to IST for market-hours check
      → passed to yfinance as UTC-aware start/end

Market hours (NSE equity):
  Monday–Friday  09:15 IST → 15:30 IST
  Weekends / holidays → MARKET_CLOSED

If the evaluation window falls entirely outside market hours the prediction
is marked MARKET_CLOSED and skipped — yfinance is never called.
If the window is partially inside market hours, we evaluate with available bars.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from repositories.prediction_evaluation_repository import PredictionEvaluationRepository
from services.market_prediction_service import IntradayPredictionService

logger = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")
_NSE_OPEN_H, _NSE_OPEN_M = 9, 15
_NSE_CLOSE_H, _NSE_CLOSE_M = 15, 30


# ---------------------------------------------------------------------------
# Market-hours helpers
# ---------------------------------------------------------------------------

def _to_ist(dt: datetime) -> datetime:
    """Convert any datetime to IST. Treats naive datetimes as UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_IST)


def _nse_open(date) -> datetime:
    """Return NSE open time for a given date as IST-aware datetime."""
    return datetime(date.year, date.month, date.day,
                    _NSE_OPEN_H, _NSE_OPEN_M, tzinfo=_IST)


def _nse_close(date) -> datetime:
    """Return NSE close time for a given date as IST-aware datetime."""
    return datetime(date.year, date.month, date.day,
                    _NSE_CLOSE_H, _NSE_CLOSE_M, tzinfo=_IST)


def _is_trading_day(date) -> bool:
    """Return True if date is Monday–Friday (basic check; no holiday calendar)."""
    return date.weekday() < 5  # 0=Mon … 4=Fri


def _market_status(dt_ist: datetime) -> str:
    """
    Return the NSE market status at a given IST datetime.
    Returns: 'OPEN' | 'MARKET_CLOSED' | 'WEEKEND'
    """
    if not _is_trading_day(dt_ist.date()):
        return "WEEKEND"
    open_t = _nse_open(dt_ist.date())
    close_t = _nse_close(dt_ist.date())
    if open_t <= dt_ist <= close_t:
        return "OPEN"
    return "MARKET_CLOSED"


def _evaluation_window_valid(start_ist: datetime, end_ist: datetime) -> bool:
    """
    Return True if any part of [start_ist, end_ist] overlaps a trading session.
    Iterates over each calendar day in the window and checks for a trading session.
    """
    # Check if start or end falls within market hours
    if _market_status(start_ist) == "OPEN":
        return True
    if _market_status(end_ist) == "OPEN":
        return True

    # Walk each day in the window and check if the NSE open falls inside it
    from datetime import date as _date
    current = start_ist.date()
    end_date = end_ist.date()
    while current <= end_date:
        if _is_trading_day(current):
            open_t = _nse_open(current)
            close_t = _nse_close(current)
            # Any overlap between [start_ist, end_ist] and [open_t, close_t]
            if start_ist <= close_t and end_ist >= open_t:
                return True
        from datetime import timedelta as _td
        current += _td(days=1)

    return False


# ---------------------------------------------------------------------------
# yfinance error classification
# ---------------------------------------------------------------------------

def _classify_yf_error(exc: Exception, bars) -> str:
    """
    Distinguish between market-closed, weekend, data gap, and real errors.
    Never labels a stock as delisted based solely on missing intraday bars.
    """
    msg = str(exc).lower() if exc else ""
    if "delisted" in msg or "no price data found" in msg:
        # yfinance says "possibly delisted" when there are simply no bars
        # in the requested window — this is NOT proof of delisting.
        return "DATA_NOT_AVAILABLE"
    if "invalid" in msg or "not found" in msg:
        return "INVALID_SYMBOL"
    if "timeout" in msg or "connection" in msg or "network" in msg:
        return "API_ERROR"
    if bars is not None and (bars is True or (hasattr(bars, "empty") and bars.empty)):
        return "DATA_NOT_AVAILABLE"
    return "API_ERROR"


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

class PredictionEvaluationService:
    """Labels completed trades with a fixed horizon, without using future bars in signals."""

    @staticmethod
    def _exit_price_at_horizon(prediction, horizon_minutes: int) -> tuple[float | None, str]:
        """
        Return (exit_price, status_reason).

        status_reason values:
            EVALUATED          — exit price found
            MARKET_CLOSED      — evaluation window outside NSE hours
            WEEKEND            — evaluation window on weekend
            DATA_NOT_AVAILABLE — yfinance returned no bars (not delisted)
            INVALID_SYMBOL     — symbol rejected by yfinance
            API_ERROR          — network / unexpected error
        """
        if not prediction.symbol or not prediction.created_on:
            return None, "MISSING_DATA"

        # ── Timezone trace ────────────────────────────────────────────────
        # prediction.created_on is TIMESTAMP(timezone=True) → UTC-aware from PG
        created_utc: datetime = prediction.created_on
        if created_utc.tzinfo is None:
            # Defensive: treat naive as UTC
            created_utc = created_utc.replace(tzinfo=timezone.utc)

        created_ist = _to_ist(created_utc)
        horizon_end_utc = created_utc + timedelta(minutes=horizon_minutes)
        horizon_end_ist = _to_ist(horizon_end_utc)

        logger.info(
            "[EVALUATION] prediction_id=%s symbol=%s "
            "prediction_time_utc=%s prediction_time_ist=%s "
            "evaluation_start=%s evaluation_end=%s",
            prediction.id,
            prediction.symbol,
            created_utc.isoformat(),
            created_ist.isoformat(),
            created_ist.isoformat(),
            horizon_end_ist.isoformat(),
        )

        # ── Market-hours guard ────────────────────────────────────────────
        if not _evaluation_window_valid(created_ist, horizon_end_ist):
            status_start = _market_status(created_ist)
            reason = "WEEKEND" if status_start == "WEEKEND" else "MARKET_CLOSED"
            logger.info(
                "[EVALUATION] prediction_id=%s symbol=%s status=%s "
                "(window %s → %s is outside NSE trading hours)",
                prediction.id, prediction.symbol, reason,
                created_ist.strftime("%Y-%m-%d %H:%M IST"),
                horizon_end_ist.strftime("%H:%M IST"),
            )
            return None, reason

        # ── yfinance fetch ────────────────────────────────────────────────
        ticker = IntradayPredictionService.normalise_symbol(prediction.symbol)
        bars = None
        fetch_exc = None
        try:
            bars = yf.download(
                ticker,
                start=created_utc - timedelta(minutes=5),
                end=horizon_end_utc + timedelta(minutes=15),
                interval="5m",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception as exc:
            fetch_exc = exc
            logger.debug(
                "[EVALUATION] yfinance error for %s (prediction %s): %s",
                ticker, prediction.id, exc,
            )

        if fetch_exc is not None or bars is None or (hasattr(bars, "empty") and bars.empty):
            reason = _classify_yf_error(fetch_exc, bars)
            logger.info(
                "[EVALUATION] prediction_id=%s symbol=%s status=%s",
                prediction.id, prediction.symbol, reason,
            )
            return None, reason

        # Flatten MultiIndex columns if present
        if isinstance(bars.columns, pd.MultiIndex):
            bars.columns = [col[0] for col in bars.columns]
        if "Close" not in bars.columns:
            return None, "DATA_NOT_AVAILABLE"

        close = pd.to_numeric(bars["Close"], errors="coerce").dropna()
        if close.empty:
            return None, "DATA_NOT_AVAILABLE"

        # Find the first bar at or after the horizon end
        target_ts = pd.Timestamp(horizon_end_utc)
        try:
            after = close.loc[close.index >= target_ts]
        except TypeError:
            after = close.loc[close.index.tz_localize(None) >= target_ts.tz_localize(None)]

        if after.empty:
            # Horizon not yet reached — use last available bar if within session
            last_bar_ist = _to_ist(close.index[-1].to_pydatetime())
            if _market_status(last_bar_ist) == "OPEN":
                exit_price = float(close.iloc[-1])
                logger.info(
                    "[EVALUATION] prediction_id=%s symbol=%s status=EVALUATED "
                    "(partial — used last available bar at %s) exit_price=%.2f",
                    prediction.id, prediction.symbol,
                    last_bar_ist.strftime("%H:%M IST"), exit_price,
                )
                return exit_price, "EVALUATED"
            return None, "DATA_NOT_AVAILABLE"

        exit_price = float(after.iloc[0])
        logger.info(
            "[EVALUATION] prediction_id=%s symbol=%s status=EVALUATED exit_price=%.2f",
            prediction.id, prediction.symbol, exit_price,
        )
        return exit_price, "EVALUATED"

    @classmethod
    def evaluate_due_predictions(cls, db, horizon_minutes: int | None = None) -> dict:
        horizon = horizon_minutes or int(os.getenv("EVALUATION_HORIZON_MINUTES", "30"))
        batch_size = int(os.getenv("EVALUATION_BATCH_SIZE", "20"))
        predictions = PredictionEvaluationRepository.get_due_predictions(db, horizon, batch_size)

        evaluated = 0
        unavailable = 0
        market_closed = 0
        weekend = 0
        failed = 0

        for prediction in predictions:
            try:
                exit_price, reason = cls._exit_price_at_horizon(prediction, horizon)

                if reason == "MARKET_CLOSED":
                    market_closed += 1
                    # Leave status as PENDING so it is retried next session
                    continue

                if reason == "WEEKEND":
                    weekend += 1
                    continue

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
                logger.exception(
                    "Could not persist evaluation for prediction %s", prediction.id
                )

        return {
            "due": len(predictions),
            "evaluated": evaluated,
            "marketClosed": market_closed,
            "weekend": weekend,
            "dataUnavailable": unavailable,
            "failed": failed,
            "horizonMinutes": horizon,
        }

    @staticmethod
    def performance_summary(db) -> dict:
        from models.prediction_history import PredictionHistory
        from sqlalchemy import func as sqlfunc

        evaluations = PredictionEvaluationRepository.get_all(db)
        total = len(evaluations)
        if total == 0:
            return {
                "totalEvaluated": 0,
                "correct": 0,
                "hitRatePercent": None,
                "averageReturnPercent": 0.0,
                "totalProfitLossPercent": 0.0,
                "byDirection": {},
                "byConfidenceBand": {},
                "bySymbol": {},
                "note": "No evaluated predictions yet.",
            }

        # Build a lookup: prediction_id → PredictionHistory row
        pred_ids = [e.prediction_id for e in evaluations]
        predictions = (
            db.query(PredictionHistory)
            .filter(PredictionHistory.id.in_(pred_ids))
            .all()
        )
        pred_map: dict[int, PredictionHistory] = {p.id: p for p in predictions}

        correct = sum(1 for e in evaluations if e.is_correct)
        total_return = sum(e.realised_return_pct for e in evaluations)
        avg_return = total_return / total

        wins = [e.realised_return_pct for e in evaluations if e.is_correct]
        losses = [e.realised_return_pct for e in evaluations if not e.is_correct]

        # ── By direction (BUY / SELL) ────────────────────────────────────
        by_direction: dict[str, dict] = {}
        for ev in evaluations:
            pred = pred_map.get(ev.prediction_id)
            direction = (pred.recommendation if pred else "UNKNOWN") or "UNKNOWN"
            bucket = by_direction.setdefault(direction, {"total": 0, "correct": 0, "returns": []})
            bucket["total"] += 1
            if ev.is_correct:
                bucket["correct"] += 1
            bucket["returns"].append(ev.realised_return_pct)
        by_direction_summary = {
            d: {
                "total": v["total"],
                "correct": v["correct"],
                "hitRate": round(v["correct"] / v["total"] * 100, 1) if v["total"] else None,
                "avgReturn": round(sum(v["returns"]) / len(v["returns"]), 4) if v["returns"] else 0.0,
            }
            for d, v in by_direction.items()
        }

        # ── By confidence band ───────────────────────────────────────────
        def _conf_band(pred) -> str:
            if pred is None or pred.confidence is None:
                return "unknown"
            c = float(pred.confidence)
            if c >= 80:
                return "80-100"
            if c >= 70:
                return "70-79"
            if c >= 60:
                return "60-69"
            return "<60"

        by_conf: dict[str, dict] = {}
        for ev in evaluations:
            band = _conf_band(pred_map.get(ev.prediction_id))
            bucket = by_conf.setdefault(band, {"total": 0, "correct": 0, "returns": []})
            bucket["total"] += 1
            if ev.is_correct:
                bucket["correct"] += 1
            bucket["returns"].append(ev.realised_return_pct)
        by_conf_summary = {
            b: {
                "total": v["total"],
                "correct": v["correct"],
                "hitRate": round(v["correct"] / v["total"] * 100, 1) if v["total"] else None,
                "avgReturn": round(sum(v["returns"]) / len(v["returns"]), 4) if v["returns"] else 0.0,
            }
            for b, v in by_conf.items()
        }

        # ── By symbol (top 20) ───────────────────────────────────────────
        by_sym: dict[str, dict] = {}
        for ev in evaluations:
            sym = ev.symbol or "UNKNOWN"
            bucket = by_sym.setdefault(sym, {"total": 0, "correct": 0, "returns": []})
            bucket["total"] += 1
            if ev.is_correct:
                bucket["correct"] += 1
            bucket["returns"].append(ev.realised_return_pct)
        by_sym_summary = {
            s: {
                "total": v["total"],
                "correct": v["correct"],
                "hitRate": round(v["correct"] / v["total"] * 100, 1) if v["total"] else None,
                "avgReturn": round(sum(v["returns"]) / len(v["returns"]), 4) if v["returns"] else 0.0,
            }
            for s, v in sorted(by_sym.items(), key=lambda x: -x[1]["total"])[:20]
        }

        return {
            "totalEvaluated": total,
            "correct": correct,
            "incorrect": total - correct,
            "hitRatePercent": round(correct / total * 100, 2) if total else None,
            "averageReturnPercent": round(avg_return, 4),
            "averageWinPercent": round(sum(wins) / len(wins), 4) if wins else 0.0,
            "averageLossPercent": round(sum(losses) / len(losses), 4) if losses else 0.0,
            "totalProfitLossPercent": round(total_return, 4),
            "byDirection": by_direction_summary,
            "byConfidenceBand": by_conf_summary,
            "bySymbol": by_sym_summary,
            "note": "Measured realised outcomes only. Does not include PENDING or MARKET_CLOSED predictions.",
        }
