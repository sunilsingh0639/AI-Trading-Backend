from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.prediction_history import PredictionHistory


class PredictionRepository:

    @staticmethod
    def save_prediction(
        db: Session,
        news_id: int,
        ai_result: dict
    ):

        prediction = PredictionHistory(

            news_id=news_id,

            company=ai_result.get("stock_name"),

            symbol=ai_result.get("symbol"),

            sector=ai_result.get("sector"),

            recommendation=ai_result.get("recommendation"),

            confidence=float(ai_result.get("confidence", 0)),

            impact=ai_result.get("impact"),

            reason=ai_result.get("reason"),

            entry_price=None,

            target_price=None,

            stop_loss=None,

            status="PENDING"

        )

        db.add(prediction)

        db.commit()

        db.refresh(prediction)

        return prediction

    @staticmethod
    def get_today_predictions(db):

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