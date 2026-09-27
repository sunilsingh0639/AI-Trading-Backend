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

            industry=company.get("industry"),

            is_fno=company.get("is_fno", False),

            is_active=company.get("is_active", True)

        )

        db.add(obj)

        db.commit()

        db.refresh(obj)

        return obj

    @staticmethod
    def find_in_title(db: Session, title: str):
        """Return the most specific active F&O company mentioned in a headline."""
        import re
        normalized_title = (title or "").upper()
        companies = CompanyRepository.get_all_fno_companies(db)

        for company in sorted(
            companies,
            key=lambda item: len(item.company_name or ""),
            reverse=True,
        ):
            name = (company.company_name or "").upper()
            symbol = (company.symbol or "").upper()
            # Use word-boundary matching to avoid false positives like HAL in "Half"
            if name and re.search(r'\b' + re.escape(name) + r'\b', normalized_title):
                return company
            if symbol and len(symbol) >= 3 and re.search(r'\b' + re.escape(symbol) + r'\b', normalized_title):
                return company
        return None

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
