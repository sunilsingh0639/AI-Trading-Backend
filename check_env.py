import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

print("GROQ_API_KEY:", "SET" if os.getenv("GROQ_API_KEY") else "MISSING")
print("GROQ_MODEL:", os.getenv("GROQ_MODEL", "NOT SET - default=openai/gpt-oss-120b"))
print("NEWS_API_KEY:", "SET" if os.getenv("NEWS_API_KEY") else "MISSING")
print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY", "MISSING"))
print("DB_HOST:", os.getenv("DB_HOST", "MISSING"))
print("DB_NAME:", os.getenv("DB_NAME", "MISSING"))

# Test Groq API
from openai import OpenAI
key = os.getenv("GROQ_API_KEY")
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key, timeout=15)
try:
    models = client.models.list()
    ids = [m.id for m in models.data]
    print("Groq models available:", ids[:5])
except Exception as e:
    print("Groq API error:", e)

# Test with default model name
try:
    r = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "say hi"}],
        max_tokens=10,
    )
    print("Default model works:", r.choices[0].message.content)
except Exception as e:
    print("Default model 'openai/gpt-oss-120b' FAILED:", e)

# Test with llama
try:
    r = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "say hi"}],
        max_tokens=10,
    )
    print("llama-3.1-8b-instant works:", r.choices[0].message.content)
except Exception as e:
    print("llama-3.1-8b-instant FAILED:", e)
