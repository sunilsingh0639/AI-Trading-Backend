import logging
import os
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from services.analysis_service import AnalysisService
from services.market_snapshot_service import MarketSnapshotService
from services.prediction_evaluation_service import PredictionEvaluationService
from services.sync_service import SyncService

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Kolkata"))


def _safe_print(text: str) -> None:
    """Print to stdout, replacing unencodable characters so Windows console never crashes."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ))


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
    _safe_print("\n" + "=" * 80)
    _safe_print(f"[{datetime.now()}] Scheduler Job Started")
    _safe_print("=" * 80)

    db = SessionLocal()
    try:
        # News Sync
        try:
            _safe_print("\n[1] Syncing News...")
            sync_result = SyncService.sync_news(db)
            _safe_print(f"News Sync Result: {sync_result}")
        except Exception as e:
            db.rollback()
            _safe_print(f"News Sync Failed: {e}")
            logger.exception("Scheduled news sync failed")

        # Market Snapshot
        try:
            _safe_print("\n[2] Saving Market Snapshot...")
            snapshot = MarketSnapshotService.save_snapshot(db)
            _safe_print(f"Snapshot Saved: {snapshot.id if snapshot else None}")
        except Exception as e:
            db.rollback()
            _safe_print(f"Market Snapshot Failed: {e}")
            logger.exception("Scheduled market snapshot failed")

        # AI Analysis
        try:
            _safe_print("\n[3] Analyzing Pending News...")
            analysis_result = AnalysisService.analyze_pending_news(db)
            _safe_print(f"Analysis Result: { {k: v for k, v in analysis_result.items() if k != 'details'} }")
            for item in analysis_result.get("details", []):
                line = (
                    f"  - news_id={item.get('news_id')} status={item.get('status')} "
                    f"type={item.get('news_type')} importance={item.get('importance')} "
                    f"rec={item.get('recommendation')} signal={item.get('signal_created')} "
                    f"reason={item.get('rejection_reason') or item.get('reason')}"
                )
                _safe_print(line)
        except Exception as e:
            db.rollback()
            _safe_print(f"Analysis Failed: {e}")
            logger.exception("Scheduled news analysis failed")

        # Prediction Evaluation
        try:
            _safe_print("\n[4] Evaluating Predictions...")
            evaluation_result = PredictionEvaluationService.evaluate_due_predictions(db)
            _safe_print(f"Evaluation Result: {evaluation_result}")
        except Exception as e:
            db.rollback()
            _safe_print(f"Prediction Evaluation Failed: {e}")
            logger.exception("Scheduled prediction evaluation failed")

    finally:
        db.close()
        _safe_print(f"[{datetime.now()}] Scheduler Job Finished")
        _safe_print("=" * 80)
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
