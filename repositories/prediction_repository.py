import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.prediction_history import PredictionHistory


class PredictionRepository:

    @staticmethod
    def save_prediction(
        db: Session,
        news_id: int,
        ai_result: dict,
    ):
        trade_plan = ai_result.get("trade_plan") or {}
        prediction = PredictionHistory(
            news_id=news_id,
            company=ai_result.get("stock_name"),
            symbol=ai_result.get("symbol"),
            sector=ai_result.get("sector"),
            recommendation=trade_plan.get("recommendation", ai_result.get("recommendation")),
            confidence=float(trade_plan.get("confidence", ai_result.get("confidence", 0))),
            impact=ai_result.get("impact"),
            reason=trade_plan.get("reason", ai_result.get("reason")),
            entry_price=trade_plan.get("entry_price"),
            target_price=trade_plan.get("target_price"),
            stop_loss=trade_plan.get("stop_loss"),
            risk_reward_ratio=trade_plan.get("risk_reward_ratio"),
            expected_holding_minutes=trade_plan.get("expected_holding_minutes"),
            probability=trade_plan.get("probability"),
            market_context=json.dumps(trade_plan.get("market_context", {}), default=str),
            supporting_indicators=json.dumps(
                trade_plan.get("indicators", {}), default=str
            ),
            status="PENDING",
        )

        db.add(prediction)
        db.flush()

        return prediction

    @staticmethod
    def get_today_predictions(db):
        last_24_hours = datetime.utcnow() - timedelta(days=1)

        return (
            db.query(PredictionHistory)
            .filter(PredictionHistory.created_on >= last_24_hours)
            .order_by(PredictionHistory.created_on.desc())
            .all()
        )
