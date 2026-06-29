from sqlalchemy import Column, Integer, String, Boolean
from database import Base


class MarketEventMaster(Base):

    __tablename__ = "market_event_master"

    id = Column(Integer, primary_key=True)

    keyword = Column(String(100))

    affected_sector = Column(String(100))

    impact = Column(String(20))

    priority = Column(Integer, default=1)

    is_active = Column(Boolean, default=True)