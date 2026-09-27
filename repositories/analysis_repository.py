import json

from sqlalchemy.orm import Session

from models.news_analysis import NewsAnalysis


class AnalysisRepository:

    @staticmethod
    def save_analysis(
        db: Session,
        news_id,
        ai_result,
        *,
        news_type: str | None = None,
        importance_score: int | None = None,
        signal_status: str | None = None,
        rejection_reason: str | None = None,
    ):
        analysis = NewsAnalysis(
            news_id=news_id,
            stock_name=ai_result["stock_name"],
            sector=ai_result["sector"],
            sentiment=ai_result["sentiment"],
            confidence=ai_result["confidence"],
            impact=ai_result["impact"],
            recommendation=ai_result["recommendation"],
            reason=ai_result["reason"],
            news_type=news_type,
            importance_score=importance_score,
            signal_status=signal_status,
            rejection_reason=rejection_reason,
        )

        db.add(analysis)
        db.flush()

        return analysis

    @staticmethod
    def save_skip_record(
        db: Session,
        news_id: int,
        *,
        news_type: str,
        importance_score: int,
        reason: str,
        stock_name: str = "N/A",
    ):
        """Persist an explicit skip so no headline disappears silently."""
        analysis = NewsAnalysis(
            news_id=news_id,
            stock_name=stock_name,
            sector="N/A",
            sentiment="NEUTRAL",
            confidence=0,
            impact="LOW",
            recommendation="HOLD",
            reason=reason,
            news_type=news_type,
            importance_score=importance_score,
            signal_status="SKIPPED",
            rejection_reason=reason,
        )
        db.add(analysis)
        db.flush()
        return analysis
