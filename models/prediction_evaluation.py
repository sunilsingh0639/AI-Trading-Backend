from sqlalchemy import Boolean, Column, Float, Integer, String, TIMESTAMP
from sqlalchemy.sql import func

from database import Base


class PredictionEvaluation(Base):
    """Immutable realised outcome for an intraday trade signal."""

    __tablename__ = "prediction_evaluation"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, unique=True, nullable=False, index=True)
    symbol = Column(String(50), nullable=False)
    horizon_minutes = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    realised_return_pct = Column(Float, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    evaluated_on = Column(TIMESTAMP(timezone=True), server_default=func.now())
    data_source = Column(String(50), default="yfinance")
