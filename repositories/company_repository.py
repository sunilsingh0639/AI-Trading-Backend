from sqlalchemy.orm import Session
from models.company_master import CompanyMaster


class CompanyRepository:

    @staticmethod
    def get_by_company_name(db: Session, company_name: str):

        return (
            db.query(CompanyMaster)
            .filter(
                CompanyMaster.company_name.ilike(company_name)
            )
            .first()
        )

    @staticmethod
    def get_by_symbol(db: Session, symbol: str):

        return (
            db.query(CompanyMaster)
            .filter(
                CompanyMaster.symbol == symbol
            )
            .first()
        )

    @staticmethod
    def save(db: Session, company):

        obj = CompanyMaster(

            company_name=company["company_name"],

            symbol=company["symbol"],

            exchange=company.get("exchange", "NSE"),

            sector=company.get("sector"),

            industry=company.get("industry")

        )

        db.add(obj)

        db.commit()

        db.refresh(obj)

        return obj

    @staticmethod
    def get_all_fno_companies(db: Session):

        return (
            db.query(CompanyMaster)
            .filter(
                CompanyMaster.is_fno == True,
                CompanyMaster.is_active == True
            )
            .all()
        )