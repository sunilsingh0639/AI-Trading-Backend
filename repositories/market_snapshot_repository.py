from models.market_snapshot import MarketSnapshot


class MarketSnapshotRepository:

    @staticmethod
    def save(db, data):

        snapshot = MarketSnapshot(

            nifty=data.get("nifty"),

            bank_nifty=data.get("bank_nifty"),

            sensex=data.get("sensex"),

            india_vix=data.get("india_vix"),

            crude=data.get("crude"),

            gold=data.get("gold"),

            usd_inr=data.get("usd_inr")

        )

        db.add(snapshot)

        db.commit()

        db.refresh(snapshot)

        return snapshot