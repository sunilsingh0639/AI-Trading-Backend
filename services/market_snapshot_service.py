import yfinance as yf

from repositories.market_snapshot_repository import (
    MarketSnapshotRepository
)


class MarketSnapshotService:

    @staticmethod
    def save_snapshot(db):

        data = {

            "nifty": yf.Ticker("^NSEI").fast_info.get("lastPrice"),

            "bank_nifty": yf.Ticker("^NSEBANK").fast_info.get("lastPrice"),

            "sensex": yf.Ticker("^BSESN").fast_info.get("lastPrice"),

            "india_vix": yf.Ticker("^INDIAVIX").fast_info.get("lastPrice"),

            "crude": yf.Ticker("CL=F").fast_info.get("lastPrice"),

            "gold": yf.Ticker("GC=F").fast_info.get("lastPrice"),

            "usd_inr": yf.Ticker("INR=X").fast_info.get("lastPrice")

        }

        return MarketSnapshotRepository.save(
            db,
            data
        )