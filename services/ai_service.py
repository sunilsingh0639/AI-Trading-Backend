import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY"),
)


class AIService:

    @staticmethod
    def analyze_news(title, description):

        prompt = f"""
You are an expert Indian Stock Market Analyst.

Analyze this news.

Title:
{title}

Description:
{description}

Return ONLY valid JSON.

Rules:
1. Confidence must be INTEGER (0-100)
2. Sentiment: Bullish, Bearish, Neutral
3. Recommendation: BUY, SELL, HOLD
4. Impact: LOW, MEDIUM, HIGH

Return JSON only:

{{
  "stock_name":"",
  "sector":"",
  "sentiment":"",
  "confidence":0,
  "impact":"",
  "recommendation":"",
  "reason":""
}}
"""

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_completion_tokens=1024
        )

        text = response.choices[0].message.content.strip()

        text = text.replace("```json", "")
        text = text.replace("```", "")

        return json.loads(text)