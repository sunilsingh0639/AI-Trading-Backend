import unittest
from unittest.mock import patch

from config import PipelineConfig
from services.analysis_service import AnalysisService
from services.news_importance_service import NewsImportanceService


class NewsImportanceServiceTests(unittest.TestCase):
    def test_company_headline_gets_higher_score(self):
        without_company = NewsImportanceService.get_score(
            "Reliance signs green hydrogen deal", news_type="GENERAL", has_company=False
        )
        with_company = NewsImportanceService.get_score(
            "Reliance signs green hydrogen deal", news_type="STOCK", has_company=True
        )
        self.assertGreater(with_company, without_company)
        self.assertGreaterEqual(with_company, PipelineConfig.MIN_IMPORTANCE_SCORE)

    def test_earnings_keyword_boosts_score(self):
        score = NewsImportanceService.get_score(
            "TCS Q3 earnings beat estimates", news_type="STOCK", has_company=True
        )
        self.assertGreaterEqual(score, 70)

    def test_low_value_content_scores_near_zero(self):
        score = NewsImportanceService.get_score("Weekly horoscope for investors")
        self.assertLessEqual(score, 10)


class AnalysisServiceTradePlanTests(unittest.TestCase):
    def test_hold_recommendation_is_rejected_with_reason(self):
        result = {
            "recommendation": "HOLD",
            "confidence": 80,
            "reason": "Insufficient evidence for a directional trade.",
        }
        plan, rejections = AnalysisService._build_trade_plan(result, "RELIANCE", {"session": "NSE_OPEN"})
        self.assertIsNone(plan)
        self.assertTrue(any("HOLD" in reason for reason in rejections))

    def test_low_confidence_is_rejected(self):
        result = {
            "recommendation": "BUY",
            "confidence": 30,
            "reason": "Mild positive sentiment only.",
        }
        plan, rejections = AnalysisService._build_trade_plan(result, "RELIANCE", {"session": "NSE_OPEN"})
        self.assertIsNone(plan)
        self.assertTrue(any("confidence" in reason.lower() for reason in rejections))

    @patch("services.analysis_service.IntradayPredictionService.get_prediction")
    def test_buy_with_technical_confirmation_creates_plan(self, mock_get_prediction):
        mock_get_prediction.return_value = {
            "symbol": "RELIANCE",
            "recommendation": "BUY",
            "tradeable": True,
            "confidence": 78,
            "entry_price": 2500.0,
            "target_price": 2530.0,
            "stop_loss": 2480.0,
            "risk_reward_ratio": 1.5,
            "indicators": {"rsi_14": 62},
            "reason": "EMA trend is upward",
        }
        result = {
            "recommendation": "BUY",
            "confidence": 70,
            "reason": "Strong order win announced.",
        }
        plan, rejections = AnalysisService._build_trade_plan(
            result, "RELIANCE", {"session": "NSE_OPEN", "vix": 14}
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["recommendation"], "BUY")
        self.assertEqual(rejections, [])
        self.assertIn("expected_holding_minutes", plan)

    @patch("services.analysis_service.IntradayPredictionService.get_prediction")
    @patch("yfinance.download")
    def test_news_only_fallback_when_technical_unavailable(
        self, mock_download, mock_get_prediction
    ):
        from services.market_prediction_service import MarketDataError

        mock_get_prediction.side_effect = MarketDataError("No data")

        import pandas as pd

        mock_download.return_value = pd.DataFrame({"Close": [100.0, 101.0, 102.0]})

        result = {
            "recommendation": "SELL",
            "confidence": 65,
            "reason": "Profit warning issued.",
        }
        plan, rejections = AnalysisService._build_trade_plan(
            result, "INFY", {"session": "NSE_OPEN"}
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["source"], "news_only")
        self.assertEqual(rejections, [])


if __name__ == "__main__":
    unittest.main()
