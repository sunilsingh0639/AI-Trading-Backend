from repositories.news_repository import NewsRepository
from repositories.analysis_repository import AnalysisRepository
from services.ai_service import AIService
from services.prediction_service import PredictionService
import traceback


class AnalysisService:

    @staticmethod
    def analyze_pending_news(db):

        pending_news = NewsRepository.get_pending_news(db)

        # Testing ke liye sirf 5 news process karo
        # Baad me is line ko remove kar dena
        pending_news = pending_news[:5]

        processed = 0
        failed = 0

        for news in pending_news:

            try:

                print("=" * 80)
                print("Analyzing News ID:", news.id)
                print("Title:", news.title)

                result = AIService.analyze_news(
                    news.title,
                    news.description or ""
                )

                print("AI Result:", result)

                AnalysisRepository.save_analysis(
                    db,
                    news.id,
                    result
                )
                # Prediction History me bhi save karo
                PredictionService.save_prediction(
                       db,
                       news.id,
                       result
                )
                NewsRepository.update_ai_status(
                    db,
                    news
                )

                processed += 1

            except Exception as e:

                print("=" * 80)
                print("News ID :", news.id)
                print("Title :", news.title)
                print("ERROR :", str(e))
                traceback.print_exc()
                print("=" * 80)

                db.rollback()

                failed += 1

        return {
            "processed": processed,
            "failed": failed
        }
        