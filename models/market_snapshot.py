from sqlalchemy import Column, Integer, Float, TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class MarketSnapshot(Base):

    __tablename__ = "market_snapshot"

    id = Column(Integer, primary_key=True, index=True)

    nifty = Column(Float)

    bank_nifty = Column(Float)

    sensex = Column(Float)

    india_vix = Column(Float)

    crude = Column(Float)

    gold = Column(Float)

    usd_inr = Column(Float)

    created_on = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )