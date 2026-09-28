import logging
from typing import Any

from config import PipelineConfig
from repositories.analysis_repository import AnalysisRepository
from repositories.company_repository import CompanyRepository
from repositories.news_repository import NewsRepository
from services.ai_service import AIService
from services.context_service import ContextService
from services.market_prediction_service import IntradayPredictionService, MarketDataError
from services.news_filter_service import NewsFilterService
from services.news_importance_service import NewsImportanceService
from services.pipeline_debug_service import PipelineDebugService
from services.prediction_service import PredictionService
from services.symbol_mapping_service import resolve_symbol

logger = logging.getLogger(__name__)


class AnalysisService:
    """Orchestrate news → AI → prediction → trading signal with full traceability."""

    @staticmethod
    def _build_news_only_plan(
        result: dict[str, Any],
        symbol: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Fallback trade plan when technical data is unavailable."""
        recommendation = result["recommendation"]
        confidence = min(75, result["confidence"])

        entry_price = None
        target_price = None
        stop_loss = None

        try:
            import yfinance as yf

            ticker = IntradayPredictionService.normalise_symbol(symbol)
            bars = yf.download(
                ticker,
                period="1d",
                interval="5m",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if bars is not None and not bars.empty:
                close_col = bars["Close"]
                if hasattr(close_col, "columns"):
                    close_col = close_col.iloc[:, 0]
                entry_price = float(close_col.iloc[-1])
        except Exception as error:
            logger.warning("Could not fetch price for news-only plan %s: %s", symbol, error)

        if entry_price and entry_price > 0:
            target_pct = PipelineConfig.DEFAULT_TARGET_PCT / 100
            stop_pct = PipelineConfig.DEFAULT_STOP_PCT / 100
            if recommendation == "BUY":
                target_price = round(entry_price * (1 + target_pct), 2)
                stop_loss = round(entry_price * (1 - stop_pct), 2)
            elif recommendation == "SELL":
                target_price = round(entry_price * (1 - target_pct), 2)
                stop_loss = round(entry_price * (1 + stop_pct), 2)

        return {
            "symbol": symbol.upper(),
            "recommendation": recommendation,
            "tradeable": True,
            "confidence": confidence,
            "technical_score": None,
            "entry_price": entry_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "risk_reward_ratio": PipelineConfig.DEFAULT_RISK_REWARD_RATIO,
            "expected_holding_minutes": PipelineConfig.DEFAULT_HOLDING_MINUTES,
            "probability": round(confidence / 100, 3),
            "indicators": {},
            "market_context": context,
            "reason": f"News-driven signal: {result['reason']}",
            "source": "news_only",
        }

    @classmethod
    def _build_trade_plan(
        cls,
        result: dict[str, Any],
        symbol: str | None,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Build a trade plan and return (plan, rejection_reasons)."""
        rejections: list[str] = []

        if not symbol:
            rejections.append("No tradable symbol identified for this headline")
            return None, rejections

        recommendation = result.get("recommendation", "HOLD")
        confidence = int(result.get("confidence", 0))

        if recommendation == "HOLD":
            rejections.append(f"AI recommendation is HOLD: {result.get('reason', 'insufficient evidence')}")
            return None, rejections

        if confidence < PipelineConfig.MIN_SIGNAL_CONFIDENCE:
            rejections.append(
                f"AI confidence {confidence} is below threshold "
                f"{PipelineConfig.MIN_SIGNAL_CONFIDENCE}"
            )
            return None, rejections

        if not context or context.get("session") is None:
            rejections.append("Market context is unavailable")
            return None, rejections

        technical: dict[str, Any] | None = None
        technical_error: str | None = None
        try:
            technical = IntradayPredictionService.get_prediction(symbol, context)
        except (MarketDataError, ValueError) as error:
            technical_error = str(error)
            logger.warning("Technical data unavailable for %s: %s", symbol, error)

        if technical and technical.get("tradeable"):
            if technical["recommendation"] != recommendation:
                if PipelineConfig.REQUIRE_TECHNICAL_ALIGNMENT:
                    if technical.get("confidence", 0) >= PipelineConfig.TECHNICAL_CONTRADICTION_THRESHOLD:
                        rejections.append(
                            f"Technical signal {technical['recommendation']} contradicts "
                            f"news signal {recommendation} "
                            f"(technical confidence {technical.get('confidence')})"
                        )
                        return None, rejections
                else:
                    # Soft penalty: reduce combined confidence but still allow signal.
                    confidence = max(
                        PipelineConfig.MIN_SIGNAL_CONFIDENCE,
                        confidence - 10,
                    )
                    logger.info(
                        "Technical %s differs from news %s for %s; proceeding with reduced confidence %s",
                        technical["recommendation"],
                        recommendation,
                        symbol,
                        confidence,
                    )

            combined_confidence = min(
                85,
                round((confidence * 0.4) + (technical.get("confidence", confidence) * 0.6)),
            )
            plan = dict(technical)
            plan["confidence"] = combined_confidence
            plan["probability"] = round(combined_confidence / 100, 3)
            plan["expected_holding_minutes"] = PipelineConfig.DEFAULT_HOLDING_MINUTES
            plan["market_context"] = context
            plan["reason"] = (
                f"News: {result['reason']} | Technical: {technical.get('reason', 'N/A')}"
            )
            plan["source"] = "news_and_technical"
            return plan, rejections

        if technical and not technical.get("tradeable"):
            # Technical says HOLD but news is directional — use news-only plan with penalty.
            logger.info(
                "Technical not tradeable for %s (%s); using news-only plan",
                symbol,
                technical.get("reason"),
            )
            plan = cls._build_news_only_plan(result, symbol, context)
            plan["confidence"] = max(
                PipelineConfig.MIN_SIGNAL_CONFIDENCE,
                min(plan["confidence"], confidence - 5),
            )
            plan["probability"] = round(plan["confidence"] / 100, 3)
            plan["reason"] = (
                f"News: {result['reason']} | Technical neutral: {technical.get('reason', 'mixed evidence')}"
            )
            return plan, rejections

        if technical_error:
            logger.info("Falling back to news-only plan for %s: %s", symbol, technical_error)

        plan = cls._build_news_only_plan(result, symbol, context)
        return plan, rejections

    @classmethod
    def analyze_pending_news(cls, db, batch_size: int | None = None):
        limit = batch_size or PipelineConfig.ANALYSIS_BATCH_SIZE
        pending_news = NewsRepository.get_pending_news(db, limit=limit)

        processed = 0
        failed = 0
        signals_created = 0
        skipped_low_impact = 0
        hold_predictions = 0
        rejected_signals = 0
        details: list[dict[str, Any]] = []

        for news in pending_news:
            company_name = None
            try:
                PipelineDebugService.log_stage(news.id, "NEWS", news.title)

                news_type = NewsFilterService.classify_news(db, news.title)
                PipelineDebugService.log_stage(
                    news.id, "CLASSIFICATION", news.title, {"news_type": news_type}
                )

                # ── Symbol resolution (multi-strategy) ──────────────────
                # Pull any provider-supplied symbols/entities stored on the
                # news row (populated by aggregator for Benzinga/MarketAux/
                # Finnhub/Alpha Vantage articles).
                provider_symbols: list[str] = []
                provider_entities: list[str] = []
                if hasattr(news, "symbols") and news.symbols:
                    try:
                        import json as _json
                        raw = news.symbols
                        parsed = _json.loads(raw) if isinstance(raw, str) else raw
                        if isinstance(parsed, list):
                            provider_symbols = [str(s) for s in parsed if s]
                    except Exception:
                        pass

                mapping = resolve_symbol(
                    db,
                    title=news.title,
                    description=news.description or "",
                    provider_symbols=provider_symbols,
                    provider_entities=provider_entities,
                )

                # Build company object compatible with downstream code
                company = None
                if mapping.status == "SUCCESS":
                    company = CompanyRepository.get_by_symbol(db, mapping.nse_symbol)
                company_name = mapping.company_name

                importance = NewsImportanceService.get_score(
                    news.title,
                    news_type=news_type,
                    has_company=mapping.status == "SUCCESS",
                )
                PipelineDebugService.log_stage(
                    news.id,
                    "IMPORTANCE",
                    news.title,
                    {"importance_score": importance, "company": company_name},
                )

                if news_type == "IGNORE" or importance < PipelineConfig.MIN_IMPORTANCE_SCORE:
                    skip_reason = (
                        "Classified as IGNORE"
                        if news_type == "IGNORE"
                        else f"Importance score {importance} below threshold "
                        f"{PipelineConfig.MIN_IMPORTANCE_SCORE}"
                    )
                    PipelineDebugService.log_skip(
                        news.id,
                        news.title,
                        news_type,
                        importance,
                        company_name,
                        skip_reason,
                    )
                    AnalysisRepository.save_skip_record(
                        db,
                        news.id,
                        news_type=news_type,
                        importance_score=importance,
                        reason=skip_reason,
                        stock_name=company_name or "N/A",
                    )
                    NewsRepository.update_ai_status(db, news)
                    db.commit()
                    processed += 1
                    skipped_low_impact += 1
                    details.append(
                        {
                            "news_id": news.id,
                            "status": "SKIPPED",
                            "news_type": news_type,
                            "importance": importance,
                            "company": company_name,
                            "reason": skip_reason,
                        }
                    )
                    continue

                known_company = None
                if company:
                    known_company = {
                        "stock_name": company.company_name,
                        "symbol": company.symbol,
                        "sector": company.sector,
                    }

                context = ContextService.get_market_context(db)
                PipelineDebugService.log_stage(
                    news.id, "CONTEXT", news.title, {"context": context}
                )

                result = AIService.analyze_news(
                    news.title,
                    news.description or "",
                    context,
                    known_company=known_company,
                )
                PipelineDebugService.log_stage(
                    news.id,
                    "AI_RESPONSE",
                    news.title,
                    {
                        "recommendation": result.get("recommendation"),
                        "confidence": result.get("confidence"),
                        "symbol": result.get("symbol"),
                        "reason": result.get("reason"),
                    },
                )

                # ── Override AI symbol with reliably resolved mapping ────
                if mapping.status == "SUCCESS":
                    result["stock_name"] = mapping.company_name
                    result["symbol"] = mapping.nse_symbol
                    result["sector"] = mapping.sector or result.get("sector", "MARKET")
                elif mapping.status == "CONTEXT_ONLY":
                    # Global/macro — keep AI result but clear symbol so no
                    # direct stock signal is generated
                    result["symbol"] = None
                elif company:
                    # Fallback: original find_in_title result (should rarely
                    # reach here now, but kept for safety)
                    result["stock_name"] = company.company_name
                    result["symbol"] = company.symbol
                    result["sector"] = company.sector or result.get("sector", "MARKET")
                else:
                    # No mapping at all — validate AI symbol against DB before
                    # trusting it (AI can hallucinate symbols)
                    ai_sym = result.get("symbol")
                    if ai_sym:
                        validated = resolve_symbol(
                            db,
                            title=news.title,
                            description=news.description or "",
                            ai_symbol=ai_sym,
                        )
                        if validated.status == "SUCCESS":
                            result["stock_name"] = validated.company_name
                            result["symbol"] = validated.nse_symbol
                            result["sector"] = validated.sector or result.get("sector", "MARKET")
                        else:
                            result["symbol"] = None

                PipelineDebugService.log_stage(
                    news.id,
                    "VALIDATION",
                    news.title,
                    {
                        "final_symbol": result.get("symbol"),
                        "final_recommendation": result.get("recommendation"),
                        "final_confidence": result.get("confidence"),
                    },
                )

                trade_plan, rejection_reasons = cls._build_trade_plan(
                    result, result.get("symbol"), context
                )

                signal_status = "ANALYZED"
                rejection_reason = None

                if trade_plan:
                    result["trade_plan"] = trade_plan
                    signal_status = "SIGNAL_CREATED"
                elif result.get("recommendation") == "HOLD":
                    hold_predictions += 1
                    rejection_reason = rejection_reasons[0] if rejection_reasons else "AI returned HOLD"
                else:
                    rejected_signals += 1
                    rejection_reason = "; ".join(rejection_reasons) or "Signal requirements not met"
                    PipelineDebugService.log_signal_rejection(
                        news.id,
                        news.title,
                        news_type,
                        importance,
                        company_name,
                        result.get("recommendation", "HOLD"),
                        int(result.get("confidence", 0)),
                        rejection_reasons or [rejection_reason],
                    )

                AnalysisRepository.save_analysis(
                    db,
                    news.id,
                    result,
                    news_type=news_type,
                    importance_score=importance,
                    signal_status=signal_status,
                    rejection_reason=rejection_reason,
                )
                PipelineDebugService.log_stage(
                    news.id, "PREDICTION_SAVED", news.title, {"signal_status": signal_status}
                )

                if trade_plan:
                    PredictionService.save_prediction(db, news.id, result)
                    signals_created += 1
                    PipelineDebugService.log_signal_created(
                        news.id,
                        news.title,
                        result.get("symbol", ""),
                        trade_plan.get("recommendation", ""),
                        float(trade_plan.get("confidence", 0)),
                        trade_plan.get("entry_price"),
                        trade_plan.get("target_price"),
                        trade_plan.get("stop_loss"),
                    )

                NewsRepository.update_ai_status(db, news)
                db.commit()
                processed += 1

                details.append(
                    {
                        "news_id": news.id,
                        "status": signal_status,
                        "news_type": news_type,
                        "importance": importance,
                        "company": company_name,
                        "recommendation": result.get("recommendation"),
                        "confidence": result.get("confidence"),
                        "signal_created": trade_plan is not None,
                        "rejection_reason": rejection_reason,
                    }
                )

            except Exception:
                db.rollback()
                failed += 1
                logger.exception("Could not analyse news id %s", news.id)
                details.append(
                    {
                        "news_id": news.id,
                        "status": "FAILED",
                        "company": company_name,
                        "reason": "Exception during analysis",
                    }
                )

        return {
            "processed": processed,
            "failed": failed,
            "signalsCreated": signals_created,
            "skippedLowImpact": skipped_low_impact,
            "holdPredictions": hold_predictions,
            "rejectedSignals": rejected_signals,
            "minImportanceScore": PipelineConfig.MIN_IMPORTANCE_SCORE,
            "minSignalConfidence": PipelineConfig.MIN_SIGNAL_CONFIDENCE,
            "details": details,
        }
