import feedparser

GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?q=stock+market+india&hl=en-IN&gl=IN&ceid=IN:en"
)


def get_google_news():

    feed = feedparser.parse(GOOGLE_NEWS_URL)

    news = []

    for item in feed.entries:

        news.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "published": item.get("published"),
            "summary": item.get("summary", "")
        })

    return news