import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from repositories.news_repository import NewsRepository
from repositories.company_repository import CompanyRepository
from services.news_filter_service import NewsFilterService

db = SessionLocal()

# Check pending news
pending = NewsRepository.get_pending_news(db, limit=10)
print(f"Pending news ({len(pending)} items):")
for n in pending:
    news_type = NewsFilterService.classify_news(db, n.title)
    company = CompanyRepository.find_in_title(db, n.title)
    print(f"  id={n.id} type={news_type} company={company.symbol if company else None}")
    print(f"    title: {n.title}")

# Check total pending
from models.market_news import MarketNews
total_pending = db.query(MarketNews).filter(MarketNews.ai_status == False).count()
print(f"\nTotal pending: {total_pending}")

# Test with a known company headline
test_titles = [
    "Reliance Industries Q3 profit beats estimates",
    "TCS wins $500 million deal from US bank",
    "HDFC Bank reports strong quarterly results",
    "Infosys raises revenue guidance for FY25",
    "Castrol India dividend announced",
]
print("\nCompany matching tests:")
for title in test_titles:
    company = CompanyRepository.find_in_title(db, title)
    news_type = NewsFilterService.classify_news(db, title)
    print(f"  '{title[:50]}' -> company={company.symbol if company else None} type={news_type}")

db.close()
