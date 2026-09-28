"""Google News RSS — Backup news provider."""

import os
import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?q=stock+market+india&hl=en-IN&gl=IN&ceid=IN:en"
)
_TIMEOUT = int(os.getenv("NEWS_PROVIDER_TIMEOUT_SECONDS", "10"))


def get_google_news() -> list[dict]:
    """Original function — returns raw feed entries (backward compatible)."""
    response = requests.get(GOOGLE_NEWS_URL, timeout=_TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.content)

    return [
        {
            "title": item.get("title"),
            "link": item.get("link"),
            "published": item.get("published"),
            "summary": item.get("summary", ""),
        }
        for item in feed.entries
    ]


def _fetch_for_manager() -> list[dict]:
    """Normalized fetch for the provider manager."""
    return [
        {
            "title": item.get("title"),
            "description": item.get("summary"),
            "source": "Google News",
            "url": item.get("link"),
            "published": item.get("published"),
            "sentiment": None,
            "provider": "google_news",
            "provider_article_id": None,
            "symbols": [],
            "entities": [],
            "category": None,
            "sentiment_score": None,
            "relevance_score": None,
        }
        for item in get_google_news()
    ]


# ---------------------------------------------------------------------------
# Register with provider manager
# ---------------------------------------------------------------------------
from services.news_provider_manager import register_provider  # noqa: E402

register_provider("google_news", "backup", _fetch_for_manager)
