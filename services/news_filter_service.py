from repositories.company_repository import CompanyRepository
from services.symbol_mapping_service import _SORTED_ALIASES


class NewsFilterService:

    COMMODITY_KEYWORDS = [
        "CRUDE",
        "OIL",
        "BRENT",
        "WTI",
        "GOLD",
        "SILVER",
        "COPPER",
        "NATURAL GAS",
        "MCX",
        "OPEC",
        "LNG",
    ]

    MACRO_KEYWORDS = [
        "RBI",
        "FED",
        "GDP",
        "INFLATION",
        "INTEREST RATE",
        "USD",
        "RUPEE",
        "DOLLAR",
        "FII",
        "DII",
        "SEBI",
        "BUDGET",
        "REPO",
        "CPI",
        "PPI",
        "UNEMPLOYMENT",
        "TARIFF",
    ]

    GLOBAL_KEYWORDS = [
        "NASDAQ",
        "DOW",
        "S&P",
        "NYSE",
        "CHINA",
        "JAPAN",
        "IRAN",
        "ISRAEL",
        "RUSSIA",
        "UKRAINE",
        "TRUMP",
        "USA",
    ]

    IGNORE_KEYWORDS = [
        "OPINION:",
        "EDITORIAL:",
        "PODCAST",
        "WEBINAR",
        "HOROSCOPE",
        "RECIPE",
        "MOVIE REVIEW",
        "BOLLYWOOD GOSSIP",
    ]

    @staticmethod
    def classify_news(db, title: str) -> str:
        import re
        normalized = (title or "").upper()

        for keyword in NewsFilterService.IGNORE_KEYWORDS:
            if keyword in normalized:
                return "IGNORE"

        for keyword in NewsFilterService.COMMODITY_KEYWORDS:
            if keyword in normalized:
                return "COMMODITY"

        for keyword in NewsFilterService.MACRO_KEYWORDS:
            if keyword in normalized:
                return "MACRO"

        for keyword in NewsFilterService.GLOBAL_KEYWORDS:
            if keyword in normalized:
                return "GLOBAL"

        companies = CompanyRepository.get_all_fno_companies(db)
        for company in companies:
            name = (company.company_name or "").upper()
            symbol = (company.symbol or "").upper()
            if name and re.search(r'\b' + re.escape(name) + r'\b', normalized):
                return "STOCK"
            if symbol and len(symbol) >= 3 and re.search(r'\b' + re.escape(symbol) + r'\b', normalized):
                return "STOCK"

        # Also check alias map so "RIL", "TCS", "HUL" etc. classify as STOCK
        for alias, _ in _SORTED_ALIASES:
            if len(alias) >= 3 and re.search(r'\b' + re.escape(alias) + r'\b', normalized):
                return "STOCK"

        return "GENERAL"
