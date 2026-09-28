"""Finnhub — Secondary news provider.

Uses general market news endpoint (no default symbol like AAPL).
For symbol-specific news, uses active Indian/F&O symbols from DB.
"""

import os
import logging
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("FINNHUB_API_KEY")
_GENERAL_NEWS_URL = "https://finnhub.io/api/v1/news"
_COMPANY_NEWS_URL = "https://finnhub.io/api/v1/company-news"
_TIMEOUT = int(os.getenv("NEWS_PROVIDER_TIMEOUT_SECONDS", "10"))


def get_finnhub_news(symbol: str | None = None) -> list[dict]:
    """
    Fetch news from Finnhub.

    - If symbol is explicitly provided, fetch company-specific news.
    - Otherwise fetch general market/financial news (no AAPL default).
    """
    if not API_KEY:
        raise RuntimeError("FINNHUB_API_KEY is not configured.")

    if symbol:
        return _fetch_company_news(symbol)
    return _fetch_general_news()


def _fetch_general_news() -> list[dict]:
    """Fetch general financial/market news from Finnhub."""
    params = {"category": "general", "token": API_KEY}
    response = requests.get(_GENERAL_NEWS_URL, params=params, timeout=_TIMEOUT)

    if response.status_code == 429:
        raise RuntimeError("HTTP 429 — Finnhub rate limit exceeded.")
    if response.status_code in (401, 403):
        raise RuntimeError(f"HTTP {response.status_code} — Finnhub authentication error.")
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Finnhub returned unexpected response: {type(data).__name__}")

    return [_normalize(item) for item in data]


def _fetch_company_news(symbol: str) -> list[dict]:
    today = datetime.now()
    from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    params = {"symbol": symbol, "from": from_date, "to": to_date, "token": API_KEY}
    response = requests.get(_COMPANY_NEWS_URL, params=params, timeout=_TIMEOUT)

    if response.status_code == 429:
        raise RuntimeError("HTTP 429 — Finnhub rate limit exceeded.")
    if response.status_code in (401, 403):
        raise RuntimeError(f"HTTP {response.status_code} — Finnhub authentication error.")
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Finnhub returned unexpected response: {type(data).__name__}")

    return [_normalize(item, symbol=symbol) for item in data]


def _normalize(item: dict, symbol: str | None = None) -> dict:
    ts = item.get("datetime")
    published = datetime.fromtimestamp(ts).isoformat() if isinstance(ts, (int, float)) and ts else str(ts or "")
    return {
        "title": item.get("headline"),
        "description": item.get("summary"),
        "source": item.get("source") or "Finnhub",
        "url": item.get("url"),
        "published": published,
        "sentiment": None,
        "provider": "finnhub",
        "provider_article_id": str(item.get("id", "")),
        "symbols": [symbol] if symbol else [],
        "entities": [],
        "category": item.get("category"),
        "sentiment_score": None,
        "relevance_score": None,
        # Legacy fields
        "headline": item.get("headline"),
        "summary": item.get("summary"),
        "datetime": item.get("datetime"),
        "image": item.get("image"),
    }


# ---------------------------------------------------------------------------
# Register with provider manager
# ---------------------------------------------------------------------------
from services.news_provider_manager import register_provider  # noqa: E402

register_provider("finnhub", "secondary", get_finnhub_news)
