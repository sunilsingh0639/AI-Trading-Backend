"""MarketAux — Primary financial news provider (Indian + global markets)."""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.marketaux.com/v1/news/all"
_TIMEOUT = int(os.getenv("NEWS_PROVIDER_TIMEOUT_SECONDS", "10"))

# Global macro topics that affect Indian markets
_GLOBAL_TOPICS = "general,earnings,ipo,mergers_acquisitions,financial,forex,crypto,economy_fiscal,economy_monetary"


def _get_api_key() -> str:
    key = os.getenv("MARKETAUX_API_KEY", "")
    if not key:
        raise RuntimeError("MARKETAUX_API_KEY is not configured.")
    return key


def _get_indian_symbols() -> str:
    """
    Return a comma-separated list of active Indian/F&O symbols.
    Falls back to major Indian indices/ETFs if DB is unavailable.
    """
    try:
        from database import SessionLocal
        from models.company_master import CompanyMaster
        db = SessionLocal()
        try:
            rows = db.query(CompanyMaster.symbol).filter(
                CompanyMaster.is_active == True  # noqa: E712
            ).limit(30).all()
            symbols = [r.symbol for r in rows if r.symbol]
            if symbols:
                return ",".join(symbols[:30])
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Could not load Indian symbols from DB: %s", exc)

    # Fallback: major Indian indices/ETFs available on MarketAux
    return "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,SBIN.NS,WIPRO.NS,AXISBANK.NS"


def fetch_marketaux_news() -> list[dict]:
    """Fetch latest news from MarketAux for Indian + global markets."""
    api_key = _get_api_key()

    articles = []

    # Request 1: Indian market symbols
    try:
        symbols = _get_indian_symbols()
        params = {
            "api_token": api_key,
            "symbols": symbols,
            "language": "en",
            "limit": 30,
            "sort": "published_at",
            "sort_order": "desc",
        }
        resp = requests.get(_BASE_URL, params=params, timeout=_TIMEOUT)
        if resp.status_code == 429:
            raise RuntimeError("HTTP 429 — MarketAux rate limit exceeded.")
        if resp.status_code in (401, 403):
            raise RuntimeError(f"HTTP {resp.status_code} — MarketAux authentication error.")
        resp.raise_for_status()
        articles.extend(_parse_response(resp.json()))
    except RuntimeError:
        raise
    except Exception as exc:
        logger.debug("[MARKETAUX] Symbol-based fetch failed: %s", exc)

    # Request 2: Global macro / market-moving news
    try:
        params_global = {
            "api_token": api_key,
            "topics": _GLOBAL_TOPICS,
            "language": "en",
            "limit": 20,
            "sort": "published_at",
            "sort_order": "desc",
        }
        resp2 = requests.get(_BASE_URL, params=params_global, timeout=_TIMEOUT)
        if resp2.status_code == 429:
            raise RuntimeError("HTTP 429 — MarketAux rate limit exceeded.")
        if resp2.status_code in (401, 403):
            raise RuntimeError(f"HTTP {resp2.status_code} — MarketAux authentication error.")
        resp2.raise_for_status()
        articles.extend(_parse_response(resp2.json()))
    except RuntimeError:
        raise
    except Exception as exc:
        logger.debug("[MARKETAUX] Global fetch failed: %s", exc)

    # Deduplicate by URL within this provider
    seen: set[str] = set()
    unique = []
    for a in articles:
        key = a.get("url") or a.get("title") or ""
        if key and key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


def _parse_response(data: dict) -> list[dict]:
    items = data.get("data", [])
    articles = []
    for item in items:
        entities = item.get("entities", [])
        symbols = [e.get("symbol") for e in entities if e.get("symbol")]
        entity_list = [
            {
                "name": e.get("name"),
                "symbol": e.get("symbol"),
                "country": e.get("country"),
                "industry": e.get("industry"),
                "relevance_score": e.get("relevance_score"),
                "sentiment": e.get("sentiment_score"),
            }
            for e in entities
        ]

        # Overall sentiment from first entity or item-level
        sentiment_score = None
        sentiment_label = None
        if entities:
            sentiment_score = entities[0].get("sentiment_score")
        if sentiment_score is not None:
            if sentiment_score > 0.1:
                sentiment_label = "positive"
            elif sentiment_score < -0.1:
                sentiment_label = "negative"
            else:
                sentiment_label = "neutral"

        articles.append({
            "title": item.get("title"),
            "description": item.get("description"),
            "source": item.get("source"),
            "url": item.get("url"),
            "published": item.get("published_at"),
            "sentiment": sentiment_label,
            "provider": "marketaux",
            "provider_article_id": str(item.get("uuid", "")),
            "symbols": symbols,
            "entities": entity_list,
            "category": item.get("topics", [None])[0] if item.get("topics") else None,
            "sentiment_score": sentiment_score,
            "relevance_score": None,
        })
    return articles


# ---------------------------------------------------------------------------
# Register with provider manager
# ---------------------------------------------------------------------------
from services.news_provider_manager import register_provider  # noqa: E402

register_provider("marketaux", "primary", fetch_marketaux_news)
