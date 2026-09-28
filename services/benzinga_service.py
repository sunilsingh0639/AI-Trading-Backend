"""Benzinga — Primary financial news provider."""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.benzinga.com/api/v2/news"
_TIMEOUT = int(os.getenv("NEWS_PROVIDER_TIMEOUT_SECONDS", "10"))


def _get_api_key() -> str:
    key = os.getenv("BENZINGA_API_KEY", "")
    if not key:
        raise RuntimeError("BENZINGA_API_KEY is not configured.")
    return key


def fetch_benzinga_news() -> list[dict]:
    """Fetch latest financial news from Benzinga. Returns normalized article list."""
    api_key = _get_api_key()

    # Build URL manually so the colon in "created:desc" is NOT percent-encoded.
    # requests encodes ":" → "%3A" in params dicts, which Benzinga rejects.
    # Postman sends: sort=created:desc  (raw colon — this is what works).
    url = (
        f"{_BASE_URL}"
        f"?token={api_key}"
        f"&pageSize=50"
        f"&displayOutput=full"
        f"&sort=created:desc"
    )

    response = requests.get(url, timeout=_TIMEOUT)

    if response.status_code == 429:
        raise RuntimeError("HTTP 429 — Benzinga rate limit exceeded.")
    if response.status_code in (401, 403):
        raise RuntimeError(f"HTTP {response.status_code} — Benzinga authentication error.")
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    body = response.text.strip()

    if not body:
        raise RuntimeError("Benzinga returned an empty response body.")

    if "xml" in content_type.lower() or body.startswith("<"):
        preview = body[:120].replace("\n", " ")
        raise RuntimeError(f"Benzinga returned non-JSON content: {preview}")

    data = response.json()

    # Benzinga returns a list directly or wrapped in a key
    items = data if isinstance(data, list) else data.get("data", data.get("news", []))

    articles = []
    for item in items:
        # Extract symbols
        symbols = [s.get("name") for s in item.get("stocks", []) if s.get("name")]

        # Extract entities
        entities = [
            {"name": e.get("name"), "type": e.get("type")}
            for e in item.get("stocks", [])
            if e.get("name")
        ]

        articles.append({
            "title": item.get("title"),
            "description": item.get("body") or item.get("teaser"),
            "source": item.get("author") or "Benzinga",
            "url": item.get("url"),
            "published": item.get("created") or item.get("updated"),
            "sentiment": None,
            "provider": "benzinga",
            "provider_article_id": str(item.get("id", "")),
            "symbols": symbols,
            "entities": entities,
            "category": item.get("channels", [{}])[0].get("name") if item.get("channels") else None,
            "sentiment_score": None,
            "relevance_score": None,
        })

    return articles


# ---------------------------------------------------------------------------
# Register with provider manager
# ---------------------------------------------------------------------------
from services.news_provider_manager import register_provider  # noqa: E402

register_provider("benzinga", "primary", fetch_benzinga_news)
