import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

key = os.getenv("GROQ_API_KEY")
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key, timeout=20)

test_models = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "groq/compound",
    "groq/compound-mini",
    "qwen/qwen3.8-27b",
]

prompt = 'You are a JSON API. Return ONLY this JSON object, nothing else:\n{"stock_name": "RELIANCE", "symbol": "RELIANCE", "sector": "Energy", "sentiment": "BULLISH", "confidence": 70, "impact": "HIGH", "recommendation": "BUY", "reason": "Strong earnings beat"}'

for model in test_models:
    print(f"\nTesting {model}...")
    # Without json_object
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0,
        )
        content = r.choices[0].message.content
        print(f"  Plain response: {content[:100]}")
    except Exception as e:
        print(f"  Plain FAILED: {e}")

    # With json_object
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = r.choices[0].message.content
        print(f"  JSON mode response: {content[:100]}")
    except Exception as e:
        print(f"  JSON mode FAILED: {e}")
