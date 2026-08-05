from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.prediction_evaluation import PredictionEvaluation
from models.prediction_history import PredictionHistory


class PredictionEvaluationRepository:
    @staticmethod
    def get_due_predictions(
        db: Session, horizon_minutes: int, limit: int
    ) -> list[PredictionHistory]:
        due_before = datetime.now(timezone.utc) - timedelta(minutes=horizon_minutes)
        return (
            db.query(PredictionHistory)
            .filter(
                PredictionHistory.status == "PENDING",
                PredictionHistory.entry_price.isnot(None),
                PredictionHistory.created_on <= due_before,
            )
            .order_by(PredictionHistory.created_on.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def save(db: Session, values: dict) -> PredictionEvaluation:
        evaluation = PredictionEvaluation(**values)
        db.add(evaluation)
        db.flush()
        return evaluation

    @staticmethod
    def get_all(db: Session, limit: int = 500) -> list[PredictionEvaluation]:
        return (
            db.query(PredictionEvaluation)
            .order_by(PredictionEvaluation.evaluated_on.desc())
            .limit(limit)
            .all()
        )
