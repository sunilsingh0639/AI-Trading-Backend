from repositories.news_repository import NewsRepository
from repositories.analysis_repository import AnalysisRepository
from services.ai_service import AIService
from services.prediction_service import PredictionService
from services.news_filter_service import NewsFilterService
from services.context_service import ContextService
import traceback


class AnalysisService:

    @staticmethod
    def analyze_pending_news(db):

        pending_news = NewsRepository.get_pending_news(db)

        # Testing ke liye sirf 5 news
        pending_news = pending_news[:5]

        processed = 0
        failed = 0

        required_keys = [
            "stock_name",
            "sector",
            "confidence",
            "impact",
            "recommendation",
            "reason"
        ]

        for news in pending_news:

            try:

                print("=" * 100)
                print("Analyzing News ID :", news.id)
                print("Title :", news.title)

                # ------------------------------
                # News Classification
                # ------------------------------
                news_type = NewsFilterService.classify_news(
                    db,
                    news.title
                )

                print("News Type :", news_type)

                # Ignore unwanted news
                if news_type == "IGNORE":

                 print("Skipping News :", news.title)
                 NewsRepository.update_ai_status(db, news)
                 continue
                # ------------------------------
                # Market Context
                # ------------------------------
                context = ContextService.get_market_context(db)

                print("Market Context :", context)

                # ------------------------------
                # AI Analysis
                # ------------------------------
                result = AIService.analyze_news(
                    news.title,
                    news.description or "",
                    context
                )

                print("AI Result :", result)

                # ------------------------------
                # Validate AI Response
                # ------------------------------
                if not isinstance(result, dict):
                    raise Exception("AI response is not JSON")

                for key in required_keys:

                    if key not in result:
                        raise Exception(
                            f"Missing AI field : {key}"
                        )

                # ------------------------------
                # Save Analysis
                # ------------------------------
                AnalysisRepository.save_analysis(
                    db,
                    news.id,
                    result
                )

                # ------------------------------
                # Save Prediction
                # ------------------------------
                PredictionService.save_prediction(
                    db,
                    news.id,
                    result
                )

                # ------------------------------
                # Mark News Processed
                # ------------------------------
                NewsRepository.update_ai_status(
                    db,
                    news
                )

                processed += 1

                print("Prediction Saved Successfully")

            except Exception as e:

                db.rollback()

                failed += 1

                print("=" * 100)
                print("News ID :", news.id)
                print("Title :", news.title)
                print("ERROR :", str(e))
                traceback.print_exc()
                print("=" * 100)

        print(f"Processed : {processed}")
        print(f"Failed : {failed}")

        return {
            "processed": processed,
            "failed": failed
        }