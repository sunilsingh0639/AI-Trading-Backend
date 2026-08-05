class NewsImportanceService:

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
        "SPLIT"
    ]

    MEDIUM_PRIORITY = [
        "TARGET",
        "UPGRADE",
        "DOWNGRADE",
        "GUIDANCE",
        "EXPANSION",
        "ORDER",
        "CONTRACT",
        "PARTNERSHIP"
    ]

    @staticmethod
    def get_score(title: str):

        title = (title or "").upper()

        score = 10

        for keyword in NewsImportanceService.HIGH_PRIORITY:

            if keyword in title:
                score += 40

        for keyword in NewsImportanceService.MEDIUM_PRIORITY:

            if keyword in title:
                score += 20

        if score > 100:
            score = 100

        return score