from repositories.company_repository import CompanyRepository


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
        "LNG"
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
        "TARIFF"
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
        "USA"
    ]

    @staticmethod
    def classify_news(db, title: str):

        title = (title or "").upper()

        # ------------------------
        # Commodity News
        # ------------------------
        for keyword in NewsFilterService.COMMODITY_KEYWORDS:
            if keyword in title:
                return "COMMODITY"

        # ------------------------
        # Macro News
        # ------------------------
        for keyword in NewsFilterService.MACRO_KEYWORDS:
            if keyword in title:
                return "MACRO"

        # ------------------------
        # Global News
        # ------------------------
        for keyword in NewsFilterService.GLOBAL_KEYWORDS:
            if keyword in title:
                return "GLOBAL"

        # ------------------------
        # Indian F&O Companies
        # ------------------------
        companies = CompanyRepository.get_all_fno_companies(db)

        for company in companies:

            if company.company_name and company.company_name.upper() in title:
                return "STOCK"

            if company.symbol and company.symbol.upper() in title:
                return "STOCK"

        # ------------------------
        # Default
        # ------------------------

        return "GENERAL"