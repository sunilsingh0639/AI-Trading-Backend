from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db

import models.market_news
import models.news_analysis

from services.news_api import get_market_news
from services.alpha_vantage_service import get_alpha_news
from services.google_news_service import get_google_news
from services.finnhub_service import get_finnhub_news
from services.aggregator_service import get_all_news
from services.sync_service import SyncService
from services.ai_service import AIService
from services.analysis_service import AnalysisService
from services.scheduler_service import start_scheduler
import models.company_master
import models.prediction_history
import models.market_snapshot
from services.company_service import CompanyService
from services.market_snapshot_service import MarketSnapshotService
from services.prediction_service import PredictionService
# FastAPI app
app = FastAPI()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)
start_scheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "AI Trading Backend Running"}


@app.get("/market-news")
def market_news():
    return get_market_news()


@app.get("/alpha-news")
def alpha_news():
    return get_alpha_news()


@app.get("/google-news")
def google_news():
    return get_google_news()


@app.get("/finnhub-news")
def finnhub_news(symbol: str = Query("AAPL")):
    return get_finnhub_news(symbol)


@app.get("/all-news")
def all_news():
    return get_all_news()


@app.post("/sync-news")
def sync_news(db: Session = Depends(get_db)):
    return SyncService.sync_news(db)


@app.get("/ai-test")
def ai_test():
    return AIService.analyze_news(
        "Reliance signs ₹18000 crore green hydrogen project",
        "Reliance announced one of India's largest green hydrogen investments."
    )


@app.post("/analyze-news")
def analyze_news(db: Session = Depends(get_db)):
    return AnalysisService.analyze_pending_news(db)

@app.post("/company")
def add_company(
    company: dict,
    db: Session = Depends(get_db)
):
    return CompanyService.save_company(
        db,
        company
    )

@app.post("/market-snapshot")
def market_snapshot(
    db: Session = Depends(get_db)
):
    return MarketSnapshotService.save_snapshot(db)

@app.get("/predictions/today")
def get_today_predictions(
    db: Session = Depends(get_db)
):
    return PredictionService.get_today_predictions(db)