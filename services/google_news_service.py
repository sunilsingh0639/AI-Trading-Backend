import feedparser
import requests

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?q=stock+market+india&hl=en-IN&gl=IN&ceid=IN:en"
)


def get_google_news():
    response = requests.get(GOOGLE_NEWS_URL, timeout=15)
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
