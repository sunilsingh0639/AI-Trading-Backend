from sqlalchemy import Column, Integer, String, Float, TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class PredictionHistory(Base):

    __tablename__ = "prediction_history"

    id = Column(Integer, primary_key=True, index=True)

    news_id = Column(Integer)

    company = Column(String(200))

    symbol = Column(String(50))

    sector = Column(String(100))

    recommendation = Column(String(20))

    confidence = Column(Float)

    impact = Column(String(30))

    reason = Column(String)

    entry_price = Column(Float, nullable=True)

    target_price = Column(Float, nullable=True)

    stop_loss = Column(Float, nullable=True)

    status = Column(String(20), default="PENDING")

    created_on = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )