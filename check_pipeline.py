import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal

print("="*60)
print("STEP 1: Database session")
db = SessionLocal()
print("  OK")

print("\nSTEP 2: Market snapshot")
try:
    from services.market_snapshot_service import MarketSnapshotService
    snap = MarketSnapshotService.save_snapshot(db)
    print(f"  OK - nifty={snap.nifty}, vix={snap.india_vix}")
except Exception as e:
    print(f"  FAILED: {e}")

print("\nSTEP 3: Market context")
try:
    from services.context_service import ContextService
    ctx = ContextService.get_market_context(db)
    print(f"  OK - {ctx}")
except Exception as e:
    print(f"  FAILED: {e}")

print("\nSTEP 4: News sync")
try:
    from services.sync_service import SyncService
    result = SyncService.sync_news(db)
    print(f"  OK - {result}")
except Exception as e:
    print(f"  FAILED: {e}")

print("\nSTEP 5: Pending news count")
try:
    from repositories.news_repository import NewsRepository
    pending = NewsRepository.get_pending_news(db, limit=3)
    print(f"  Found {len(pending)} pending news items")
    for n in pending:
        print(f"    id={n.id} title={n.title[:60]}")
except Exception as e:
    print(f"  FAILED: {e}")

print("\nSTEP 6: AI service test")
try:
    from services.ai_service import AIService
    result = AIService.analyze_news(
        "Reliance Industries Q3 profit beats estimates by 15 percent",
        "Reliance Industries reported strong Q3 results with net profit up 15 percent.",
        {"session": "NSE_OPEN", "nifty": 24500, "vix": 14},
    )
    print(f"  OK - {result}")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")

print("\nSTEP 7: Full analysis pipeline (1 item)")
try:
    from services.analysis_service import AnalysisService
    result = AnalysisService.analyze_pending_news(db, batch_size=1)
    print(f"  Result: processed={result['processed']} failed={result['failed']} signals={result['signalsCreated']}")
    for d in result.get('details', []):
        print(f"    {d}")
except Exception as e:
    import traceback
    print(f"  FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()

db.close()
print("\nDone.")
