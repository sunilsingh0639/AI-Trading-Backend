"""Reset test news and run full pipeline with improved prompt."""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models.market_news import MarketNews

db = SessionLocal()

# Reset the test news items
test_urls = [
    "https://test.example.com/reliance-q2-fy26-results",
    "https://test.example.com/tcs-deal-win",
    "https://test.example.com/hdfc-bank-q2",
]
for url in test_urls:
    news = db.query(MarketNews).filter(MarketNews.url == url).first()
    if news:
        news.ai_status = False
db.commit()
print("Reset 3 test news items to pending")

# Run analysis
from services.market_snapshot_service import MarketSnapshotService
from services.analysis_service import AnalysisService
from services.context_service import ContextService

print("\n[1] Market Snapshot...")
snap = MarketSnapshotService.save_snapshot(db)
print(f"  nifty={snap.nifty:.2f} vix={snap.india_vix:.2f}")

print("\n[2] Analysis Pipeline (3 items)...")
result = AnalysisService.analyze_pending_news(db, batch_size=3)
print(f"  processed={result['processed']} failed={result['failed']} signals={result['signalsCreated']}")
print(f"  skipped={result['skippedLowImpact']} hold={result['holdPredictions']} rejected={result['rejectedSignals']}")

print("\n  Details:")
for d in result.get('details', []):
    print(f"    news_id={d.get('news_id')} status={d.get('status')} type={d.get('news_type')} "
          f"importance={d.get('importance')} company={d.get('company')} "
          f"rec={d.get('recommendation')} conf={d.get('confidence')} signal={d.get('signal_created')}")
    if d.get('rejection_reason'):
        print(f"      rejection: {d.get('rejection_reason')}")

print("\n[3] Saved predictions...")
from repositories.prediction_repository import PredictionRepository
predictions = PredictionRepository.get_today_predictions(db)
print(f"  Total predictions today: {len(predictions)}")
for p in predictions:
    print(f"    id={p.id} symbol={p.symbol} rec={p.recommendation} conf={p.confidence:.0f} "
          f"entry={p.entry_price} target={p.target_price} stop={p.stop_loss} rr={p.risk_reward_ratio}")
    print(f"    reason: {p.reason[:120] if p.reason else None}")

db.close()
