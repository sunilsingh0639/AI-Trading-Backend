import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

BASE_URL = "https://www.alphavantage.co/query"


def get_alpha_news():

    params = {
        "function": "NEWS_SENTIMENT",
        "topics": "financial_markets",
        "sort": "LATEST",
        "limit": 20,
        "apikey": API_KEY
    }

    response = requests.get(BASE_URL, params=params)

    data = response.json()

    news = []

    for item in data.get("feed", []):

        news.append({
            "title": item.get("title"),
            "summary": item.get("summary"),
            "source": item.get("source"),
            "url": item.get("url"),
            "time_published": item.get("time_published"),
            "overall_sentiment_score": item.get("overall_sentiment_score"),
            "overall_sentiment_label": item.get("overall_sentiment_label")
        })

    return news