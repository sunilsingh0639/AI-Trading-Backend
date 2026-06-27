from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class NewsAnalysis(Base):

    __tablename__ = "news_analysis"

    id = Column(Integer, primary_key=True, index=True)

    news_id = Column(Integer)

    stock_name = Column(String(100))

    sector = Column(String(100))

    sentiment = Column(String(30))

    confidence = Column(Integer)

    impact = Column(String(30))

    recommendation = Column(String(20))

    reason = Column(Text)

    created_on = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )