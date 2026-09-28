"""Benzinga — Primary financial news provider.

The /api/v2/news endpoint returns XML (not JSON) for this API key tier.
We parse XML natively; JSON is kept as a fallback in case the endpoint
ever returns it.
"""

import logging
import os
import xml.etree.ElementTree as ET

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

    # Build URL manually — requests percent-encodes ":" in params dicts,
    # turning sort=created:desc into sort=created%3Adesc which Benzinga rejects.
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

    body = response.text.strip()
    if not body:
        raise RuntimeError("Benzinga returned an empty response body.")

    content_type = response.headers.get("Content-Type", "").lower()

    # XML response (actual format returned by this API key tier)
    if "xml" in content_type or body.startswith("<"):
        return _parse_xml(body)

    # JSON fallback
    return _parse_json(response.json())


# ---------------------------------------------------------------------------
# XML parser
# ---------------------------------------------------------------------------

def _text(element, tag: str) -> str | None:
    """Return stripped text of a child element, or None if absent/empty."""
    child = element.find(tag)
    if child is None:
        return None
    return (child.text or "").strip() or None


def _parse_xml(body: str) -> list[dict]:
    """
    Parse Benzinga XML response.

    Expected structure:
        <result is_array="true">
            <item>
                <id>62014119</id>
                <title>...</title>
                <body>...</body>
                <teaser>...</teaser>
                <author>...</author>
                <created>Mon, 28 Sep 2026 12:00:00 -0400</created>
                <updated>...</updated>
                <url>...</url>
                <stocks>
                    <item><name>RELIANCE</name><exchange>NSE</exchange></item>
                </stocks>
                <channels>
                    <item><name>Markets</name></item>
                </channels>
            </item>
        </result>
    """
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        preview = body[:120].replace("\n", " ")
        raise RuntimeError(f"Benzinga XML parse error: {exc} | preview: {preview}") from exc

    # Root may be <result> containing <item> children, or directly a list of <item>
    items = root.findall("item")
    if not items:
        # Some responses wrap items one level deeper
        items = root.findall(".//item")

    articles = []
    for item in items:
        # Stocks / symbols
        symbols: list[str] = []
        entities: list[dict] = []
        stocks_el = item.find("stocks")
        if stocks_el is not None:
            for stock in stocks_el.findall("item"):
                name = _text(stock, "name")
                exchange = _text(stock, "exchange")
                if name:
                    symbols.append(name)
                    entities.append({"name": name, "type": exchange or "equity"})

        # Category from first channel
        category: str | None = None
        channels_el = item.find("channels")
        if channels_el is not None:
            first_channel = channels_el.find("item")
            if first_channel is not None:
                category = _text(first_channel, "name")

        articles.append({
            "title": _text(item, "title"),
            "description": _text(item, "body") or _text(item, "teaser"),
            "source": _text(item, "author") or "Benzinga",
            "url": _text(item, "url"),
            "published": _text(item, "created") or _text(item, "updated"),
            "sentiment": None,
            "provider": "benzinga",
            "provider_article_id": _text(item, "id") or "",
            "symbols": symbols,
            "entities": entities,
            "category": category,
            "sentiment_score": None,
            "relevance_score": None,
        })

    logger.info("[NEWS][BENZINGA] Parsed %d articles from XML response", len(articles))
    return articles


# ---------------------------------------------------------------------------
# JSON parser (fallback)
# ---------------------------------------------------------------------------

def _parse_json(data) -> list[dict]:
    items = data if isinstance(data, list) else data.get("data", data.get("news", []))
    articles = []
    for item in items:
        symbols = [s.get("name") for s in item.get("stocks", []) if s.get("name")]
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
            "category": (
                item.get("channels", [{}])[0].get("name")
                if item.get("channels") else None
            ),
            "sentiment_score": None,
            "relevance_score": None,
        })
    return articles


# ---------------------------------------------------------------------------
# Register with provider manager
# ---------------------------------------------------------------------------
from services.news_provider_manager import register_provider  # noqa: E402

register_provider("benzinga", "primary", fetch_benzinga_news)
