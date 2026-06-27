import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NEWS_API_KEY")

BASE_URL = "https://newsapi.org/v2/top-headlines"


def get_market_news():

    params = {
        "category": "business",
        "country": "us",
        "apiKey": API_KEY
    }

    response = requests.get(BASE_URL, params=params)

    return response.json()