"""End-to-end pipeline test: inject Indian market news and run full analysis."""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from repositories.news_repository import NewsRepository
from models.market_news import MarketNews

db = SessionLocal()

# Inject test news items about Indian companies
test_news = [
    {
        "title": "Reliance Industries Q2 FY26 net profit rises 12 percent to Rs 19,323 crore",
        "description": "Reliance Industries reported a 12 percent year-on-year increase in net profit for Q2 FY26, beating analyst estimates. Revenue from operations grew 8 percent.",
        "source": "TEST",
        "url": "https://test.example.com/reliance-q2-fy26-results",
        "published": "2026-09-21T09:00:00",
        "sentiment": None,
    },
    {
        "title": "TCS wins $1.2 billion multi-year deal from European banking consortium",
        "description": "Tata Consultancy Services has secured a major IT transformation contract worth $1.2 billion from a European banking consortium, boosting its order book.",
        "source": "TEST",
        "url": "https://test.example.com/tcs-deal-win",
        "published": "2026-09-21T09:15:00",
        "sentiment": None,
    },
    {
        "title": "HDFC Bank Q2 net interest income grows 10 percent, asset quality improves",
        "description": "HDFC Bank reported strong Q2 results with net interest income growing 10 percent and gross NPA ratio improving to 1.2 percent.",
        "source": "TEST",
        "url": "https://test.example.com/hdfc-bank-q2",
        "published": "2026-09-21T09:30:00",
        "sentiment": None,
    },
]

added = 0
for news in test_news:
    existing = db.query(MarketNews).filter(MarketNews.url == news["url"]).first()
    if not existing:
        obj = MarketNews(**news)
        db.add(obj)
        added += 1
db.commit()
print(f"Injected {added} test news items")

# Now run the full pipeline
print("\n" + "="*60)
print("RUNNING FULL ANALYSIS PIPELINE")
print("="*60)

from services.market_snapshot_service import MarketSnapshotService
from services.sync_service import SyncService
from services.analysis_service import AnalysisService
from services.context_service import ContextService

print("\n[1] Market Snapshot...")
try:
    snap = MarketSnapshotService.save_snapshot(db)
    print(f"  nifty={snap.nifty:.2f} bank_nifty={snap.bank_nifty:.2f} vix={snap.india_vix:.2f}")
except Exception as e:
    print(f"  FAILED: {e}")

print("\n[2] Market Context...")
ctx = ContextService.get_market_context(db)
print(f"  session={ctx['session']} nifty={ctx['nifty']} vix={ctx['vix']}")

print("\n[3] News Analysis (batch of 5)...")
result = AnalysisService.analyze_pending_news(db, batch_size=5)
print(f"  processed={result['processed']} failed={result['failed']} signals={result['signalsCreated']}")
print(f"  skipped_low_impact={result['skippedLowImpact']} hold={result['holdPredictions']} rejected={result['rejectedSignals']}")
print("\n  Details:")
for d in result.get('details', []):
    print(f"    news_id={d.get('news_id')} status={d.get('status')} type={d.get('news_type')} "
          f"importance={d.get('importance')} company={d.get('company')} "
          f"rec={d.get('recommendation')} conf={d.get('confidence')} "
          f"signal={d.get('signal_created')}")
    if d.get('rejection_reason'):
        print(f"      rejection: {d.get('rejection_reason')}")

print("\n[4] Checking saved predictions...")
from repositories.prediction_repository import PredictionRepository
predictions = PredictionRepository.get_today_predictions(db)
print(f"  Total predictions today: {len(predictions)}")
for p in predictions:
    print(f"    id={p.id} symbol={p.symbol} rec={p.recommendation} conf={p.confidence} "
          f"entry={p.entry_price} target={p.target_price} stop={p.stop_loss}")

db.close()
print("\nPipeline test complete.")
