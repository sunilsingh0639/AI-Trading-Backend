"""Alpha Vantage — Secondary news provider (NEWS_SENTIMENT function)."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"
_TIMEOUT = int(os.getenv("NEWS_PROVIDER_TIMEOUT_SECONDS", "10"))


def get_alpha_news() -> list[dict]:
    if not API_KEY:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY is not configured.")

    params = {
        "function": "NEWS_SENTIMENT",
        "topics": "financial_markets",
        "sort": "LATEST",
        "limit": 20,
        "apikey": API_KEY,
    }

    response = requests.get(BASE_URL, params=params, timeout=_TIMEOUT)

    if response.status_code == 429:
        raise RuntimeError("HTTP 429 — Alpha Vantage rate limit exceeded.")
    if response.status_code in (401, 403):
        raise RuntimeError(f"HTTP {response.status_code} — Alpha Vantage authentication error.")
    response.raise_for_status()

    data = response.json()

    # Alpha Vantage returns {"Information": "..."} when rate-limited
    if "Information" in data and "feed" not in data:
        raise RuntimeError(f"Alpha Vantage API limit: {data['Information']}")

    news = []
    for item in data.get("feed", []):
        news.append({
            "title": item.get("title"),
            "description": item.get("summary"),
            "source": item.get("source"),
            "url": item.get("url"),
            "published": item.get("time_published"),
            "sentiment": item.get("overall_sentiment_label"),
            "provider": "alpha_vantage",
            "provider_article_id": None,
            "symbols": [
                t.get("ticker") for t in item.get("ticker_sentiment", []) if t.get("ticker")
            ],
            "entities": [],
            "category": None,
            "sentiment_score": item.get("overall_sentiment_score"),
            "relevance_score": None,
            # Legacy fields kept for backward compatibility
            "summary": item.get("summary"),
            "time_published": item.get("time_published"),
            "overall_sentiment_score": item.get("overall_sentiment_score"),
            "overall_sentiment_label": item.get("overall_sentiment_label"),
        })

    return news


# ---------------------------------------------------------------------------
# Register with provider manager
# ---------------------------------------------------------------------------
from services.news_provider_manager import register_provider  # noqa: E402

register_provider("alpha_vantage", "secondary", get_alpha_news)
