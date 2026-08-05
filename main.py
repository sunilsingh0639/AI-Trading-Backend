from contextlib import asynccontextmanager
import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from schemas import CompanyCreate

# Import every model before schema creation so a fresh deployment has all tables.
import models.company_master
import models.market_event_master
import models.market_news
import models.market_snapshot
import models.news_analysis
import models.prediction_evaluation
import models.prediction_history
from services.ai_service import AIService
from services.alpha_vantage_service import get_alpha_news
from services.analysis_service import AnalysisService
from services.aggregator_service import get_all_news
from services.company_service import CompanyService
from services.finnhub_service import get_finnhub_news
from services.google_news_service import get_google_news
from services.market_prediction_service import IntradayPredictionService, MarketDataError
from services.market_snapshot_service import MarketSnapshotService
from services.news_api import get_market_news
from services.prediction_evaluation_service import PredictionEvaluationService
from services.prediction_service import PredictionService
from services.scheduler_service import start_scheduler, stop_scheduler
from services.sync_service import SyncService
from services.context_service import ContextService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="AI Trading Backend", version="1.0.0", lifespan=lifespan)

cors_origins = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", "*").split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "AI Trading Backend Running", "version": app.version}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database is unavailable.") from error
    return {"status": "ok"}


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
def finnhub_news(symbol: str = Query("AAPL", min_length=1, max_length=20)):
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
        "Reliance signs INR 18,000 crore green hydrogen project",
        "Reliance announced a major green hydrogen investment.",
        context={"session": "TEST"},
    )


@app.post("/analyze-news")
def analyze_news(db: Session = Depends(get_db)):
    return AnalysisService.analyze_pending_news(db)


@app.post("/company", status_code=status.HTTP_201_CREATED)
def add_company(company: CompanyCreate, db: Session = Depends(get_db)):
    return CompanyService.save_company(db, company.model_dump())


@app.post("/market-snapshot")
def market_snapshot(db: Session = Depends(get_db)):
    try:
        return MarketSnapshotService.save_snapshot(db)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/predictions/intraday/{symbol}")
def get_intraday_prediction(symbol: str, db: Session = Depends(get_db)):
    try:
        return IntradayPredictionService.get_prediction(
            symbol, ContextService.get_market_context(db)
        )
    except (MarketDataError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/predictions/today")
def get_today_predictions(db: Session = Depends(get_db)):
    return PredictionService.get_today_predictions(db)


@app.post("/predictions/evaluate")
def evaluate_predictions(db: Session = Depends(get_db)):
    return PredictionEvaluationService.evaluate_due_predictions(db)


@app.get("/predictions/performance")
def prediction_performance(db: Session = Depends(get_db)):
    return PredictionEvaluationService.performance_summary(db)
