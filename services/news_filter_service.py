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
        "MCX"

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
        "BUDGET"

    ]

    @staticmethod
    def classify_news(db, title: str):

        title = (title or "").upper()

        # Commodity
        for keyword in NewsFilterService.COMMODITY_KEYWORDS:

            if keyword in title:

                return "COMMODITY"

        # Macro
        for keyword in NewsFilterService.MACRO_KEYWORDS:

            if keyword in title:

                return "MACRO"

        # F&O Companies from Database
        companies = CompanyRepository.get_all_fno_companies(db)

        for company in companies:

            if company.symbol.upper() in title:

                return "STOCK"

            if company.company_name.upper() in title:

                return "STOCK"

        return "IGNORE"