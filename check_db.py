import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv() 

from sqlalchemy import create_engine, text

url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
print("Connecting to:", url.replace(os.getenv('DB_PASSWORD',''), '***'))

try:
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("DB connection: OK")
        
        # Check tables
        tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        print("Tables:", [r[0] for r in tables])
        
        # Check news count
        try:
            cnt = conn.execute(text("SELECT COUNT(*) FROM market_news")).scalar()
            pending = conn.execute(text("SELECT COUNT(*) FROM market_news WHERE ai_status=false")).scalar()
            print(f"market_news: total={cnt}, pending_analysis={pending}")
        except Exception as e:
            print("market_news error:", e)
            
        # Check analysis count
        try:
            cnt = conn.execute(text("SELECT COUNT(*) FROM news_analysis")).scalar()
            print(f"news_analysis: total={cnt}")
        except Exception as e:
            print("news_analysis error:", e)
            
        # Check predictions
        try:
            cnt = conn.execute(text("SELECT COUNT(*) FROM prediction_history")).scalar()
            print(f"prediction_history: total={cnt}")
        except Exception as e:
            print("prediction_history error:", e)
            
        # Check companies
        try:
            cnt = conn.execute(text("SELECT COUNT(*) FROM company_master WHERE is_fno=true AND is_active=true")).scalar()
            print(f"company_master (fno+active): {cnt}")
        except Exception as e:
            print("company_master error:", e)
            
except Exception as e:
    print("DB connection FAILED:", e)
