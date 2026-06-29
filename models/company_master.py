from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class CompanyMaster(Base):

    __tablename__ = "company_master"

    id = Column(Integer, primary_key=True, index=True)

    company_name = Column(String(200), unique=True, nullable=False)

    symbol = Column(String(50), unique=True, nullable=False)

    exchange = Column(String(20), default="NSE")

    sector = Column(String(100))

    industry = Column(String(100))

    created_on = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    is_fno = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)