from sqlalchemy.orm import Session
from models.news_analysis import NewsAnalysis


class AnalysisRepository:

    @staticmethod
    def save_analysis(db: Session, news_id, ai_result):

        analysis = NewsAnalysis(

            news_id=news_id,

            stock_name=ai_result["stock_name"],

            sector=ai_result["sector"],

            sentiment=ai_result["sentiment"],

            confidence=ai_result["confidence"],

            impact=ai_result["impact"],

            recommendation=ai_result["recommendation"],

            reason=ai_result["reason"]

        )

        db.add(analysis)

        db.commit()

        db.refresh(analysis)

        return analysis