import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://newsapi.org/v2/top-headlines"


def get_market_news():
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise RuntimeError("NEWS_API_KEY is not configured.")

    response = requests.get(
        BASE_URL,
        params={
            "category": "business",
            "country": os.getenv("NEWS_API_COUNTRY", "in"),
            "apiKey": api_key,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()
