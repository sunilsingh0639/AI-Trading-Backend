import yfinance as yf
import logging

from repositories.market_snapshot_repository import (
    MarketSnapshotRepository
)


class MarketSnapshotService:

    _QUOTES = {
        "nifty": "^NSEI",
        "bank_nifty": "^NSEBANK",
        "sensex": "^BSESN",
        "india_vix": "^INDIAVIX",
        "crude": "CL=F",
        "gold": "GC=F",
        "usd_inr": "INR=X",
    }

    logger = logging.getLogger(__name__)

    @classmethod
    def _last_price(cls, ticker: str) -> float | None:
        try:
            value = yf.Ticker(ticker).fast_info.get("lastPrice")
            return float(value) if value is not None else None
        except Exception as error:
            cls.logger.warning("Could not fetch quote for %s: %s", ticker, error)
            return None

    @classmethod
    def save_snapshot(cls, db):
        data = {field: cls._last_price(ticker) for field, ticker in cls._QUOTES.items()}
        if not any(value is not None for value in data.values()):
            raise RuntimeError("No market snapshot quotes are currently available.")

        return MarketSnapshotRepository.save(
            db,
            data
        )
