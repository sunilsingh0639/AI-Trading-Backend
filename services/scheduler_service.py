from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal

from services.sync_service import SyncService
from services.analysis_service import AnalysisService
from services.market_snapshot_service import MarketSnapshotService

scheduler = BackgroundScheduler()


def scheduled_job():

    db = SessionLocal()

    try:

        print("=" * 100)
        print("Scheduler Started")
        print("=" * 100)

        # 1. Sync News
        sync_result = SyncService.sync_news(db)
        print("News Sync :", sync_result)

        # 2. Save Market Snapshot
        snapshot = MarketSnapshotService.save_snapshot(db)
        print("Market Snapshot Saved :", snapshot.id)

        # 3. AI Analysis
        analysis_result = AnalysisService.analyze_pending_news(db)
        print("AI Analysis :", analysis_result)

        print("=" * 100)
        print("Scheduler Completed")
        print("=" * 100)

    except Exception as e:

        print("Scheduler Error :", e)

    finally:

        db.close()


def start_scheduler():

    scheduler.add_job(
        scheduled_job,
        "interval",
        minutes=3,
        id="news_scheduler",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )

    scheduler.start()

    print("Scheduler Running Every 3 Minutes")