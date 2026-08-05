import logging
import os
from typing import Any

from repositories.analysis_repository import AnalysisRepository
from repositories.company_repository import CompanyRepository
from repositories.news_repository import NewsRepository
from services.ai_service import AIService
from services.context_service import ContextService
from services.market_prediction_service import IntradayPredictionService, MarketDataError
from services.news_filter_service import NewsFilterService
from services.news_importance_service import NewsImportanceService
from services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


class AnalysisService:
    @staticmethod
    def _build_trade_plan(
        result: dict[str, Any], symbol: str | None, context: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Require independent technical confirmation before persisting a trade."""
        if not symbol or result["recommendation"] == "HOLD":
            return None

        try:
            technical = IntradayPredictionService.get_prediction(symbol, context)
        except (MarketDataError, ValueError) as error:
            logger.warning("Technical confirmation unavailable for %s: %s", symbol, error)
            return None

        if not technical["tradeable"]:
            return None
        if technical["recommendation"] != result["recommendation"]:
            logger.info(
                "Rejected %s news signal because technical signal is %s",
                symbol,
                technical["recommendation"],
            )
            return None

        # A news headline and price action must agree. Cap confidence so a model score
        # is never displayed as a claim of near-certain market accuracy.
        technical["confidence"] = min(
            85,
            round((result["confidence"] * 0.4) + (technical["confidence"] * 0.6)),
        )
        technical["reason"] = (
            f"News: {result['reason']} | Technical: {technical['reason']}"
        )
        return technical

    @classmethod
    def analyze_pending_news(cls, db, batch_size: int | None = None):
        limit = batch_size or int(os.getenv("ANALYSIS_BATCH_SIZE", "10"))
        pending_news = NewsRepository.get_pending_news(db, limit=limit)

        processed = 0
        failed = 0
        signals_created = 0
        skipped_low_impact = 0

        for news in pending_news:
            try:
                news_type = NewsFilterService.classify_news(db, news.title)
                importance = NewsImportanceService.get_score(news.title)

                if news_type == "IGNORE" or importance < 50:
                    NewsRepository.update_ai_status(db, news)
                    db.commit()
                    processed += 1
                    skipped_low_impact += 1
                    continue

                company = CompanyRepository.find_in_title(db, news.title)
                known_company = None
                if company:
                    known_company = {
                        "stock_name": company.company_name,
                        "symbol": company.symbol,
                        "sector": company.sector,
                    }

                context = ContextService.get_market_context(db)
                result = AIService.analyze_news(
                    news.title,
                    news.description or "",
                    context,
                    known_company=known_company,
                )

                # Company master is the source of truth for a symbol, preventing an LLM
                # hallucination from becoming a live market-data request or stored trade.
                if company:
                    result["stock_name"] = company.company_name
                    result["symbol"] = company.symbol
                    result["sector"] = company.sector or result["sector"]

                trade_plan = cls._build_trade_plan(result, result.get("symbol"), context)
                if trade_plan:
                    result["trade_plan"] = trade_plan

                AnalysisRepository.save_analysis(db, news.id, result)
                if trade_plan:
                    PredictionService.save_prediction(db, news.id, result)
                    signals_created += 1

                NewsRepository.update_ai_status(db, news)
                db.commit()
                processed += 1

            except Exception:
                db.rollback()
                failed += 1
                logger.exception("Could not analyse news id %s", news.id)

        return {
            "processed": processed,
            "failed": failed,
            "signalsCreated": signals_created,
            "skippedLowImpact": skipped_low_impact,
        }
