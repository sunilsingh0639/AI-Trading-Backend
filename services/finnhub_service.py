import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FINNHUB_API_KEY")

BASE_URL = "https://finnhub.io/api/v1/company-news"


def get_finnhub_news(symbol="AAPL"):

    today = datetime.now()

    from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    to_date = today.strftime("%Y-%m-%d")

    params = {
        "symbol": symbol,
        "from": from_date,
        "to": to_date,
        "token": API_KEY
    }

    response = requests.get(BASE_URL, params=params)

    data = response.json()

    news = []

    for item in data:

        news.append({
            "headline": item.get("headline"),
            "summary": item.get("summary"),
            "source": item.get("source"),
            "url": item.get("url"),
            "datetime": item.get("datetime"),
            "image": item.get("image")
        })

    return news