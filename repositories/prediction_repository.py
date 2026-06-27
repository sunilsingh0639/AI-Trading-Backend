from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.prediction_history import PredictionHistory


class PredictionRepository:

    @staticmethod
    def get_today_predictions(db: Session):

        last_24_hours = datetime.utcnow() - timedelta(days=1)

        return (
            db.query(PredictionHistory)
            .filter(
                PredictionHistory.created_on >= last_24_hours
            )
            .order_by(
                PredictionHistory.created_on.desc()
            )
            .all()
        )