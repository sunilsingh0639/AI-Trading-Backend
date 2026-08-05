import unittest

from pydantic import ValidationError

from schemas import NewsAnalysisResult


class NewsAnalysisResultTests(unittest.TestCase):
    def test_normalises_llm_enums_and_empty_labels(self):
        result = NewsAnalysisResult.model_validate(
            {
                "stock_name": "",
                "sector": "",
                "sentiment": "bullish",
                "confidence": 62,
                "impact": "medium",
                "recommendation": "buy",
                "reason": "Company guidance was raised for the current year.",
            }
        )

        self.assertEqual(result.stock_name, "MARKET")
        self.assertEqual(result.sector, "MARKET")
        self.assertEqual(result.recommendation, "BUY")

    def test_rejects_invalid_confidence(self):
        with self.assertRaises(ValidationError):
            NewsAnalysisResult.model_validate(
                {
                    "sentiment": "BULLISH",
                    "confidence": 101,
                    "impact": "HIGH",
                    "recommendation": "BUY",
                    "reason": "Company guidance was raised for the current year.",
                }
            )
