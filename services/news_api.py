"""NewsAPI — Backup news provider."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://newsapi.org/v2/top-headlines"
_TIMEOUT = int(os.getenv("NEWS_PROVIDER_TIMEOUT_SECONDS", "10"))


def get_market_news() -> dict:
    """Original function — returns raw NewsAPI response dict (backward compatible)."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise RuntimeError("NEWS_API_KEY is not configured.")

    response = requests.get(
        BASE_URL,
        params={
            "category": "business",
            "country": os.getenv("NEWS_API_COUNTRY", "in"),
            "apiKey": api_key,
        },
        timeout=_TIMEOUT,
    )

    if response.status_code == 429:
        raise RuntimeError("HTTP 429 — NewsAPI rate limit exceeded.")
    if response.status_code in (401, 403):
        raise RuntimeError(f"HTTP {response.status_code} — NewsAPI authentication error.")
    response.raise_for_status()
    return response.json()


def _fetch_for_manager() -> list[dict]:
    """Normalized fetch for the provider manager."""
    payload = get_market_news()
    if payload.get("status") != "ok":
        raise RuntimeError(f"NewsAPI returned status: {payload.get('status')}")

    return [
        {
            "title": a.get("title"),
            "description": a.get("description"),
            "source": a.get("source", {}).get("name") or "NewsAPI",
            "url": a.get("url"),
            "published": a.get("publishedAt"),
            "sentiment": None,
            "provider": "newsapi",
            "provider_article_id": None,
            "symbols": [],
            "entities": [],
            "category": None,
            "sentiment_score": None,
            "relevance_score": None,
        }
        for a in payload.get("articles", [])
    ]


# ---------------------------------------------------------------------------
# Register with provider manager
# ---------------------------------------------------------------------------
from services.news_provider_manager import register_provider  # noqa: E402

register_provider("newsapi", "backup", _fetch_for_manager)
