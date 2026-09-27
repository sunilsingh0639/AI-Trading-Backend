from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf


class MarketDataError(RuntimeError):
    """Raised when a tradeable intraday data series is unavailable."""


class IntradayPredictionService:
    """A deterministic technical confirmation layer for intraday trade signals.

    This intentionally emits HOLD for mixed or weak evidence. It is not an accuracy
    guarantee and it never converts an LLM confidence value into a trade by itself.
    """

    _INDEX_SYMBOLS = {
        "NIFTY": "^NSEI",
        "NIFTY50": "^NSEI",
        "NIFTY 50": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "BANK NIFTY": "^NSEBANK",
        "SENSEX": "^BSESN",
    }

    @classmethod
    def normalise_symbol(cls, symbol: str) -> str:
        cleaned = symbol.strip().upper()
        if not cleaned:
            raise ValueError("A symbol is required.")
        if cleaned in cls._INDEX_SYMBOLS:
            return cls._INDEX_SYMBOLS[cleaned]
        if cleaned.startswith("^") or cleaned.endswith(".NS") or cleaned.endswith(".BO"):
            return cleaned
        return f"{cleaned}.NS"

    @classmethod
    def get_prediction(
        cls, symbol: str, market_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        ticker = cls.normalise_symbol(symbol)
        try:
            bars = yf.download(
                ticker,
                period="5d",
                interval="5m",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception as error:
            raise MarketDataError(f"Could not load intraday data for {symbol}.") from error

        return cls.build_prediction(bars, symbol=symbol, market_context=market_context)

    @staticmethod
    def _empty_prediction(symbol: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": symbol.upper(),
            "recommendation": "HOLD",
            "tradeable": False,
            "confidence": 0,
            "technical_score": 50,
            "entry_price": None,
            "target_price": None,
            "stop_loss": None,
            "risk_reward_ratio": None,
            "indicators": {},
            "reason": reason,
        }

    @classmethod
    def build_prediction(
        cls,
        bars: pd.DataFrame,
        symbol: str,
        market_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a signal from supplied OHLCV bars; separated for deterministic tests."""
        if bars is None or bars.empty:
            raise MarketDataError(f"No intraday data is available for {symbol}.")

        frame = bars.copy()
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = [column[0] for column in frame.columns]

        required_columns = {"Close", "High", "Low", "Volume"}
        if not required_columns.issubset(frame.columns):
            raise MarketDataError(f"Incomplete intraday OHLCV data for {symbol}.")

        frame = frame[["Close", "High", "Low", "Volume"]].apply(
            pd.to_numeric, errors="coerce"
        ).dropna()
        if len(frame) < 35:
            return cls._empty_prediction(symbol, "Insufficient intraday history for a safe signal.")

        close = frame["Close"]
        high = frame["High"]
        low = frame["Low"]
        volume = frame["Volume"].clip(lower=0)

        ema_fast = close.ewm(span=9, adjust=False).mean()
        ema_slow = close.ewm(span=21, adjust=False).mean()
        delta = close.diff()
        gains = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        losses = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        relative_strength = gains / losses.where(losses != 0)
        rsi = 100 - (100 / (1 + relative_strength))
        rsi = rsi.mask((losses == 0) & (gains > 0), 100.0)
        rsi = rsi.mask((gains == 0) & (losses > 0), 0.0).fillna(50.0)

        previous_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
        ).max(axis=1)
        atr = true_range.ewm(alpha=1 / 14, adjust=False).mean()

        latest = float(close.iloc[-1])
        latest_atr = float(atr.iloc[-1])
        if latest <= 0 or latest_atr <= 0:
            return cls._empty_prediction(symbol, "Invalid latest price data for a safe signal.")

        latest_session = frame.loc[frame.index.date == frame.index[-1].date()]
        session_volume = latest_session["Volume"].clip(lower=0)
        if session_volume.sum() > 0:
            typical_price = (
                latest_session["High"] + latest_session["Low"] + latest_session["Close"]
            ) / 3
            vwap = float((typical_price * session_volume).cumsum().iloc[-1] / session_volume.cumsum().iloc[-1])
        else:
            vwap = latest

        volume_baseline = float(volume.iloc[-21:-1].mean())
        volume_ratio = float(volume.iloc[-1] / volume_baseline) if volume_baseline > 0 else 1.0
        momentum = float(close.iloc[-1] / close.iloc[-7] - 1)

        score = 50.0
        reasons: list[str] = []
        bullish_trend = bool(ema_fast.iloc[-1] > ema_slow.iloc[-1])
        if bullish_trend:
            score += 18
            reasons.append("EMA trend is upward")
        else:
            score -= 18
            reasons.append("EMA trend is downward")

        latest_rsi = float(rsi.iloc[-1])
        if 55 <= latest_rsi <= 75:
            score += 12
            reasons.append("RSI supports upward momentum")
        elif 25 <= latest_rsi <= 45:
            score -= 12
            reasons.append("RSI supports downward momentum")
        elif latest_rsi > 78 or latest_rsi < 22:
            score = 50 + (score - 50) * 0.65
            reasons.append("RSI is extended, so conviction is reduced")

        if momentum >= 0.003:
            score += 10
            reasons.append("Recent price momentum is positive")
        elif momentum <= -0.003:
            score -= 10
            reasons.append("Recent price momentum is negative")

        price_above_vwap = latest >= vwap
        if volume_ratio >= 1.2 and price_above_vwap == bullish_trend:
            score += 7 if bullish_trend else -7
            reasons.append("Volume confirms the prevailing trend")
        elif volume_ratio < 0.65:
            score = 50 + (score - 50) * 0.8
            reasons.append("Volume is weak, so conviction is reduced")

        vix = (market_context or {}).get("vix")
        try:
            if vix is not None and float(vix) >= 20:
                score = 50 + (score - 50) * 0.7
                reasons.append("High India VIX reduces position conviction")
        except (TypeError, ValueError):
            pass

        score = max(0.0, min(100.0, score))
        recommendation = "HOLD"
        if score >= 75:
            recommendation = "BUY"
        elif score <= 25:
            recommendation = "SELL"

        tradeable = recommendation != "HOLD"
        confidence = int(min(85, round(50 + abs(score - 50) * 0.8))) if tradeable else int(
            round(50 - abs(score - 50) * 0.25)
        )

        entry_price = target_price = stop_loss = risk_reward_ratio = None
        if recommendation == "BUY":
            entry_price = latest
            stop_loss = latest - latest_atr
            target_price = latest + (latest_atr * 1.5)
            risk_reward_ratio = 1.5
        elif recommendation == "SELL":
            entry_price = latest
            stop_loss = latest + latest_atr
            target_price = latest - (latest_atr * 1.5)
            risk_reward_ratio = 1.5
        else:
            reasons.append("Evidence is mixed; no intraday position is opened")

        return {
            "symbol": symbol.upper(),
            "recommendation": recommendation,
            "tradeable": tradeable,
            "confidence": confidence,
            "technical_score": round(score, 1),
            "entry_price": round(entry_price, 2) if entry_price is not None else None,
            "target_price": round(target_price, 2) if target_price is not None else None,
            "stop_loss": round(stop_loss, 2) if stop_loss is not None else None,
            "risk_reward_ratio": risk_reward_ratio,
            "expected_holding_minutes": 30,
            "probability": round(confidence / 100, 3) if tradeable else 0.0,
            "indicators": {
                "ema_9": round(float(ema_fast.iloc[-1]), 2),
                "ema_21": round(float(ema_slow.iloc[-1]), 2),
                "rsi_14": round(latest_rsi, 2),
                "atr_14": round(latest_atr, 2),
                "vwap": round(vwap, 2),
                "volume_ratio": round(volume_ratio, 2),
                "momentum_30m_pct": round(momentum * 100, 3),
            },
            "reason": "; ".join(reasons),
            "as_of": frame.index[-1].isoformat(),
        }
