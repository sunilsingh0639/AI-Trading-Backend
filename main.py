from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from migrate import run_migrations
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
    migration_result = run_migrations()
    if any(migration_result.values()):
        logger.info("Applied schema migrations: %s", migration_result)
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
def finnhub_news(symbol: str = Query(None, min_length=1, max_length=20)):
    try:
        return get_finnhub_news(symbol or None)
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


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


@app.get("/ai-health")
def ai_health():
    """Check AI service connectivity without exposing secrets."""
    import os
    from openai import OpenAI
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail={"status": "AI_CONFIG_ERROR", "message": "GROQ_API_KEY is not configured."})
    try:
        client = OpenAI(
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=key,
            timeout=15.0,
        )
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": 'Return JSON: {"status": "ok"}'}],
            max_tokens=20,
            temperature=0,
        )
        return {
            "status": "ok",
            "model": model,
            "provider": "groq",
            "response_preview": (r.choices[0].message.content or "")[:50],
        }
    except Exception as error:
        error_str = str(error)
        if "401" in error_str or "authentication" in error_str.lower():
            category = "AI_AUTH_ERROR"
        elif "404" in error_str or "not found" in error_str.lower():
            category = "AI_CONFIG_ERROR"
        elif "timeout" in error_str.lower():
            category = "AI_TIMEOUT"
        elif "429" in error_str:
            category = "AI_RATE_LIMIT"
        else:
            category = "AI_PROVIDER_ERROR"
        raise HTTPException(status_code=503, detail={"status": category, "message": "AI service check failed."})


@app.post("/api/analysis/run")
def run_analysis_now(db: Session = Depends(get_db)):
    """Manually trigger one complete analysis cycle immediately."""
    from services.scheduler_service import scheduled_job
    from services.sync_service import SyncService
    from services.market_snapshot_service import MarketSnapshotService
    from services.prediction_evaluation_service import PredictionEvaluationService

    correlation_id = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("ANL-%Y%m%d-%H%M%S")
    started_at = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    errors = []

    # Step 1: Market snapshot
    try:
        MarketSnapshotService.save_snapshot(db)
    except Exception as e:
        errors.append(f"market_snapshot: {e}")
        logger.warning("Manual trigger: market snapshot failed: %s", e)

    # Step 2: News sync
    sync_result = {}
    try:
        sync_result = SyncService.sync_news(db)
    except Exception as e:
        errors.append(f"news_sync: {e}")
        logger.warning("Manual trigger: news sync failed: %s", e)

    # Step 3: Analysis
    analysis_result = {}
    try:
        analysis_result = AnalysisService.analyze_pending_news(db)
    except Exception as e:
        errors.append(f"analysis: {e}")
        logger.warning("Manual trigger: analysis failed: %s", e)

    # Step 4: Evaluation
    eval_result = {}
    try:
        eval_result = PredictionEvaluationService.evaluate_due_predictions(db)
    except Exception as e:
        errors.append(f"evaluation: {e}")
        logger.warning("Manual trigger: evaluation failed: %s", e)

    completed_at = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    return {
        "correlation_id": correlation_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "sync": sync_result,
        "analysis": {k: v for k, v in analysis_result.items() if k != "details"},
        "analysis_details": analysis_result.get("details", []),
        "evaluation": eval_result,
        "errors": errors,
        "status": "completed" if not errors else "completed_with_errors",
    }


@app.get("/api/analysis/latest")
def get_latest_analysis(db: Session = Depends(get_db)):
    """Return the most recent analysis records."""
    from models.news_analysis import NewsAnalysis
    from models.prediction_history import PredictionHistory

    analyses = (
        db.query(NewsAnalysis)
        .order_by(NewsAnalysis.created_on.desc())
        .limit(20)
        .all()
    )
    predictions = (
        db.query(PredictionHistory)
        .order_by(PredictionHistory.created_on.desc())
        .limit(10)
        .all()
    )
    return {
        "analyses": [
            {
                "id": a.id,
                "news_id": a.news_id,
                "stock_name": a.stock_name,
                "sector": a.sector,
                "sentiment": a.sentiment,
                "confidence": a.confidence,
                "impact": a.impact,
                "recommendation": a.recommendation,
                "reason": a.reason,
                "news_type": a.news_type,
                "importance_score": a.importance_score,
                "signal_status": a.signal_status,
                "rejection_reason": a.rejection_reason,
                "created_on": a.created_on.isoformat() if a.created_on else None,
            }
            for a in analyses
        ],
        "predictions": [
            {
                "id": p.id,
                "symbol": p.symbol,
                "company": p.company,
                "recommendation": p.recommendation,
                "confidence": p.confidence,
                "entry_price": p.entry_price,
                "target_price": p.target_price,
                "stop_loss": p.stop_loss,
                "risk_reward_ratio": p.risk_reward_ratio,
                "reason": p.reason,
                "status": p.status,
                "created_on": p.created_on.isoformat() if p.created_on else None,
            }
            for p in predictions
        ],
    }


@app.get("/api/news/providers/status")
def news_providers_status():
    """Return operational health of all news providers. Never exposes API keys."""
    from services.news_provider_manager import get_all_provider_health
    return {"providers": get_all_provider_health()}


@app.get("/api/status")
def system_status(db: Session = Depends(get_db)):
    """Overall system status for frontend display."""
    from models.news_analysis import NewsAnalysis
    from models.prediction_history import PredictionHistory
    from models.market_snapshot import MarketSnapshot
    from services.scheduler_service import scheduler

    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))

    # DB health
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # Latest analysis
    latest_analysis = (
        db.query(NewsAnalysis)
        .order_by(NewsAnalysis.created_on.desc())
        .first()
    )
    # Latest prediction
    latest_prediction = (
        db.query(PredictionHistory)
        .order_by(PredictionHistory.created_on.desc())
        .first()
    )
    # Latest snapshot
    latest_snapshot = (
        db.query(MarketSnapshot)
        .order_by(MarketSnapshot.created_on.desc())
        .first()
    )

    # Scheduler next run
    next_run = None
    try:
        job = scheduler.get_job("news_scheduler")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()
    except Exception:
        pass

    return {
        "timestamp_ist": now_ist.isoformat(),
        "database": "ok" if db_ok else "unavailable",
        "scheduler_running": scheduler.running,
        "scheduler_next_run_ist": next_run,
        "market_data": {
            "last_snapshot": latest_snapshot.created_on.isoformat() if latest_snapshot and latest_snapshot.created_on else None,
            "nifty": latest_snapshot.nifty if latest_snapshot else None,
            "vix": latest_snapshot.india_vix if latest_snapshot else None,
        },
        "analysis": {
            "last_analysis": latest_analysis.created_on.isoformat() if latest_analysis and latest_analysis.created_on else None,
            "last_recommendation": latest_analysis.recommendation if latest_analysis else None,
            "last_confidence": latest_analysis.confidence if latest_analysis else None,
        },
        "predictions": {
            "last_signal": latest_prediction.created_on.isoformat() if latest_prediction and latest_prediction.created_on else None,
            "last_symbol": latest_prediction.symbol if latest_prediction else None,
            "last_recommendation": latest_prediction.recommendation if latest_prediction else None,
        },
    }
