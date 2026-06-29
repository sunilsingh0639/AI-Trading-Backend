from sqlalchemy.orm import Session
from models.market_event_master import MarketEventMaster


class MarketEventRepository:

    @staticmethod
    def get_all_events(db: Session):

        return (
            db.query(MarketEventMaster)
            .filter(
                MarketEventMaster.is_active == True
            )
            .all()
        )