import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from services.alpha_vantage_service import get_alpha_news
from services.finnhub_service import get_finnhub_news
from services.google_news_service import get_google_news
from services.news_api import get_market_news

logger = logging.getLogger(__name__)


def normalise_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url.strip())
    tracking_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}
    query = urlencode(
        [(key, value) for key, value in parse_qsl(parsed.query) if key.lower() not in tracking_keys]
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), query, ""))


def _article(title, description, source, url, published, sentiment=None):
    return {
        "title": title,
        "description": description,
        "source": source,
        "url": normalise_url(url),
        "published": str(published or ""),
        "sentiment": sentiment,
    }


def get_all_news():
    all_news = []

    try:
        payload = get_market_news()
        if payload.get("status") == "ok":
            all_news.extend(
                _article(
                    article.get("title"),
                    article.get("description"),
                    "NewsAPI",
                    article.get("url"),
                    article.get("publishedAt"),
                )
                for article in payload.get("articles", [])
            )
    except Exception as error:
        logger.warning("NewsAPI fetch failed: %s", error)

    try:
        all_news.extend(
            _article(
                item.get("title"), item.get("summary"), "Google", item.get("link"), item.get("published")
            )
            for item in get_google_news()
        )
    except Exception as error:
        logger.warning("Google News fetch failed: %s", error)

    try:
        all_news.extend(
            _article(
                item.get("title"),
                item.get("summary"),
                item.get("source") or "Alpha Vantage",
                item.get("url"),
                item.get("time_published"),
                item.get("overall_sentiment_label"),
            )
            for item in get_alpha_news()
        )
    except Exception as error:
        logger.warning("Alpha Vantage fetch failed: %s", error)

    try:
        all_news.extend(
            _article(
                item.get("headline"),
                item.get("summary"),
                item.get("source") or "Finnhub",
                item.get("url"),
                item.get("datetime"),
            )
            for item in get_finnhub_news()
        )
    except Exception as error:
        logger.warning("Finnhub fetch failed: %s", error)

    unique_news = {}
    for item in all_news:
        title = (item.get("title") or "").strip()
        key = item.get("url") or title.casefold()
        if title and key:
            unique_news.setdefault(key, item)
    return list(unique_news.values())
