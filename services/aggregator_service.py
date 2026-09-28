"""
News aggregator — orchestrates all providers via the provider manager.

Imports provider modules to trigger their register_provider() calls,
then delegates parallel execution to news_provider_manager.
"""

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import provider modules — each registers itself with the provider manager
# ---------------------------------------------------------------------------
import services.benzinga_service       # noqa: F401  primary
import services.marketaux_service      # noqa: F401  primary
import services.alpha_vantage_service  # noqa: F401  secondary
import services.finnhub_service        # noqa: F401  secondary
import services.news_api               # noqa: F401  backup
import services.google_news_service    # noqa: F401  backup

from services.news_provider_manager import fetch_all_providers


# ---------------------------------------------------------------------------
# URL normalisation (unchanged — downstream code depends on this)
# ---------------------------------------------------------------------------
def normalise_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url.strip())
    tracking_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in tracking_keys]
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), query, ""))


# ---------------------------------------------------------------------------
# Legacy helper kept for backward compatibility (used by old aggregator callers)
# ---------------------------------------------------------------------------
def _article(title, description, source, url, published, sentiment=None):
    return {
        "title": title,
        "description": description,
        "source": source,
        "url": normalise_url(url),
        "published": str(published or ""),
        "sentiment": sentiment,
    }


# ---------------------------------------------------------------------------
# get_all_news — public API (backward compatible return type: list[dict])
# ---------------------------------------------------------------------------
def get_all_news() -> list[dict]:
    """Return deduplicated news from all providers. Never raises."""
    articles, _ = _fetch_and_deduplicate()
    return articles


# ---------------------------------------------------------------------------
# get_all_news_with_stats — extended API used by sync_service
# ---------------------------------------------------------------------------
def get_all_news_with_stats() -> tuple[list[dict], dict]:
    """Return (deduplicated_articles, provider_summary)."""
    return _fetch_and_deduplicate()


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------
def _fetch_and_deduplicate() -> tuple[list[dict], dict]:
    raw_articles, provider_summary = fetch_all_providers()

    # Normalise URLs and map to the shape sync_service / downstream expects
    normalised: list[dict] = []
    for item in raw_articles:
        norm_url = normalise_url(item.get("url"))
        normalised.append({
            # Fields sync_service / NewsRepository use
            "title": (item.get("title") or "").strip() or None,
            "description": item.get("description"),
            "source": item.get("source") or item.get("provider", "unknown"),
            "url": norm_url,
            "published": str(item.get("published") or ""),
            "sentiment": item.get("sentiment"),
            # Extended fields (ignored by existing downstream, available for future use)
            "provider": item.get("provider"),
            "provider_article_id": item.get("provider_article_id"),
            "symbols": item.get("symbols", []),
            "entities": item.get("entities", []),
            "category": item.get("category"),
            "sentiment_score": item.get("sentiment_score"),
            "relevance_score": item.get("relevance_score"),
        })

    # Deduplication: URL → title fallback
    unique: dict[str, dict] = {}
    for item in normalised:
        title = item.get("title") or ""
        key = item.get("url") or title.casefold()
        if title and key:
            unique.setdefault(key, item)

    deduped = list(unique.values())

    logger.info(
        "[NEWS][AGGREGATOR] Total fetched: %d | After deduplication: %d",
        len(normalised), len(deduped),
    )

    return deduped, provider_summary
