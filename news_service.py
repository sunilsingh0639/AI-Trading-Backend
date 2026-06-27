import feedparser

def get_news():

    feed = feedparser.parse(
        "https://feeds.feedburner.com/ndtvprofit-latest"
    )

    result = []

    for item in feed.entries:

        result.append({
            "title": item.title,
            "summary": item.summary
        })

    return result