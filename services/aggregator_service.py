from services.news_api import get_market_news
from services.alpha_vantage_service import get_alpha_news
from services.google_news_service import get_google_news
from services.finnhub_service import get_finnhub_news


def get_all_news():

    all_news = []

    # -------------------------
    # NewsAPI
    # -------------------------
    try:

        news_api = get_market_news()

        if news_api.get("status") == "ok":

            for article in news_api.get("articles", []):

                all_news.append({

                    "title": article.get("title"),

                    "description": article.get("description"),

                    "source": "NewsAPI",

                    "url": article.get("url"),

                    "published": str(article.get("publishedAt") or ""),

                    "sentiment": None

                })

    except Exception as e:

        print("NewsAPI Error :", e)

    # -------------------------
    # Google RSS
    # -------------------------
    try:

        google = get_google_news()

        for item in google:

            all_news.append({

                "title": item.get("title"),

                "description": item.get("summary"),

                "source": "Google",

                "url": item.get("link"),

                "published": str(item.get("published") or ""),

                "sentiment": None

            })

    except Exception as e:

        print("Google Error :", e)

    # -------------------------
    # Alpha Vantage
    # -------------------------
    try:

        alpha = get_alpha_news()

        for item in alpha:

            all_news.append({

                "title": item.get("title"),

                "description": item.get("summary"),

                "source": "Alpha Vantage",

                "url": item.get("url"),

                "published": str(item.get("time_published") or ""),

                "sentiment": item.get("overall_sentiment_label")

            })

    except Exception as e:

        print("Alpha Error :", e)

    # -------------------------
    # Finnhub
    # -------------------------
    try:

        finnhub = get_finnhub_news()

        for item in finnhub:

            all_news.append({

                "title": item.get("headline"),

                "description": item.get("summary"),

                "source": item.get("source"),

                "url": item.get("url"),

                "published": str(item.get("datetime") or ""),

                "sentiment": None

            })

    except Exception as e:

        print("Finnhub Error :", e)

    # -------------------------
    # Remove Duplicate by Title
    # -------------------------

    unique_news = {}

    for item in all_news:

        title = item.get("title")

        if title:
            unique_news[title] = item

    return list(unique_news.values())