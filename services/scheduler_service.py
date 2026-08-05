import logging
import os
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from services.analysis_service import AnalysisService
from services.market_snapshot_service import MarketSnapshotService
from services.prediction_evaluation_service import PredictionEvaluationService
from services.sync_service import SyncService

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Kolkata"))


# def scheduled_job():
#     db = SessionLocal()
#     try:
#         try:
#             logger.info("News sync result: %s", SyncService.sync_news(db))
#         except Exception:
#             db.rollback()
#             logger.exception("Scheduled news sync failed")

#         try:
#             snapshot = MarketSnapshotService.save_snapshot(db)
#             logger.info("Saved market snapshot %s", snapshot.id)
#         except Exception:
#             db.rollback()
#             logger.exception("Scheduled market snapshot failed")

#         try:
#             logger.info("News analysis result: %s", AnalysisService.analyze_pending_news(db))
#         except Exception:
#             db.rollback()
#             logger.exception("Scheduled news analysis failed")

#         try:
#             logger.info(
#                 "Prediction evaluation result: %s",
#                 PredictionEvaluationService.evaluate_due_predictions(db),
#             )
#         except Exception:
#             db.rollback()
#             logger.exception("Scheduled prediction evaluation failed")
#     finally:
#         db.close()

from datetime import datetime

def scheduled_job():
    print("\n" + "=" * 80)
    print(f"[{datetime.now()}] Scheduler Job Started")
    print("=" * 80)

    db = SessionLocal()
    try:
        # News Sync
        try:
            print("\n[1] Syncing News...")
            sync_result = SyncService.sync_news(db)
            print("News Sync Result:", sync_result)
        except Exception as e:
            db.rollback()
            print("News Sync Failed:", str(e))
            logger.exception("Scheduled news sync failed")

        # Market Snapshot
        try:
            print("\n[2] Saving Market Snapshot...")
            snapshot = MarketSnapshotService.save_snapshot(db)
            print("Snapshot Saved:", snapshot.id if snapshot else None)
        except Exception as e:
            db.rollback()
            print("Market Snapshot Failed:", str(e))
            logger.exception("Scheduled market snapshot failed")

        # AI Analysis
        try:
            print("\n[3] Analyzing Pending News...")
            analysis_result = AnalysisService.analyze_pending_news(db)
            print("Analysis Result:", analysis_result)
        except Exception as e:
            db.rollback()
            print("Analysis Failed:", str(e))
            logger.exception("Scheduled news analysis failed")

        # Prediction Evaluation
        try:
            print("\n[4] Evaluating Predictions...")
            evaluation_result = PredictionEvaluationService.evaluate_due_predictions(db)
            print("Evaluation Result:", evaluation_result)
        except Exception as e:
            db.rollback()
            print("Prediction Evaluation Failed:", str(e))
            logger.exception("Scheduled prediction evaluation failed")

    finally:
        db.close()
        print(f"[{datetime.now()}] Scheduler Job Finished")
        print("=" * 80)
def start_scheduler():
    if os.getenv("SCHEDULER_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        logger.info("Scheduler is disabled by SCHEDULER_ENABLED.")
        return
    if scheduler.running:
        return

    scheduler.add_job(
        scheduled_job,
        "interval",
        minutes=int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "3")),
        id="news_scheduler",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler started.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
