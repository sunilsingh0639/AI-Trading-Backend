class NewsImportanceService:
    """Score headline relevance so weak noise is filtered before LLM cost."""

    HIGH_PRIORITY = [
        "RBI",
        "REPO",
        "FED",
        "INFLATION",
        "GDP",
        "WAR",
        "IRAN",
        "ISRAEL",
        "OPEC",
        "CRUDE",
        "BUDGET",
        "SEBI",
        "FII",
        "DII",
        "RESULT",
        "EARNINGS",
        "MERGER",
        "ACQUISITION",
        "IPO",
        "BONUS",
        "SPLIT",
        "DIVIDEND",
        "BUYBACK",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "QUARTER",
        "PROFIT",
        "LOSS",
        "REVENUE",
    ]

    MEDIUM_PRIORITY = [
        "TARGET",
        "UPGRADE",
        "DOWNGRADE",
        "GUIDANCE",
        "EXPANSION",
        "ORDER",
        "CONTRACT",
        "PARTNERSHIP",
        "DEAL",
        "LAUNCH",
        "APPROVAL",
        "RAISE",
        "CUT",
        "HIKE",
        "STAKE",
        "INVEST",
    ]

    LOW_VALUE = [
        "OPINION",
        "EDITORIAL",
        "PODCAST",
        "WEBINAR",
        "QUIZ",
        "HOROSCOPE",
        "RECIPE",
        "MOVIE",
        "CRICKET SCORE",
        "BOLLYWOOD",
    ]

    @classmethod
    def get_score(
        cls,
        title: str,
        news_type: str | None = None,
        has_company: bool = False,
    ) -> int:
        """Return 0-100 importance. Company-linked headlines start higher."""
        normalized = (title or "").upper()
        if not normalized.strip():
            return 0

        for keyword in cls.LOW_VALUE:
            if keyword in normalized:
                return 5

        score = 25

        if has_company:
            score += 25

        if news_type == "STOCK":
            score += 15
        elif news_type in {"MACRO", "COMMODITY", "GLOBAL"}:
            score += 10
        elif news_type == "IGNORE":
            return 0

        for keyword in cls.HIGH_PRIORITY:
            if keyword in normalized:
                score += 30

        for keyword in cls.MEDIUM_PRIORITY:
            if keyword in normalized:
                score += 15

        return min(score, 100)
