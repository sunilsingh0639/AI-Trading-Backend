from repositories.market_snapshot_repository import MarketSnapshotRepository
from datetime import datetime


class ContextService:

    @staticmethod
    def get_market_context(db):

        snapshot = MarketSnapshotRepository.get_latest(db)

        now = datetime.now()

        hour = now.hour
        minute = now.minute

        session = "CLOSED"

        if (hour > 9 or (hour == 9 and minute >= 15)) and \
           (hour < 15 or (hour == 15 and minute <= 30)):

            session = "NSE_OPEN"

        elif hour >= 15:

            session = "POST_MARKET"

        return {

            "session": session,

            "nifty": snapshot.nifty,

            "bank_nifty": snapshot.bank_nifty,

            "sensex": snapshot.sensex,

            "vix": snapshot.india_vix,

            "crude": snapshot.crude,

            "gold": snapshot.gold,

            "usd_inr": snapshot.usd_inr

        }