from repositories.market_snapshot_repository import MarketSnapshotRepository
from datetime import datetime
from zoneinfo import ZoneInfo


class ContextService:

    @staticmethod
    def get_market_context(db):

        snapshot = MarketSnapshotRepository.get_latest(db)

        now = datetime.now(ZoneInfo("Asia/Kolkata"))

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

            "nifty": snapshot.nifty if snapshot else None,

            "bank_nifty": snapshot.bank_nifty if snapshot else None,

            "sensex": snapshot.sensex if snapshot else None,

            "vix": snapshot.india_vix if snapshot else None,

            "crude": snapshot.crude if snapshot else None,

            "gold": snapshot.gold if snapshot else None,

            "usd_inr": snapshot.usd_inr if snapshot else None

        }
