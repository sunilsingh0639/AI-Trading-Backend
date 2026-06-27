from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class MarketNews(Base):

    __tablename__ = "market_news"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(Text)

    description = Column(Text)

    source = Column(String(100))

    url = Column(Text, unique=True)

    published = Column(String(100))

    sentiment = Column(String(30))

    ai_status = Column(Boolean, default=False)

    created_on = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )