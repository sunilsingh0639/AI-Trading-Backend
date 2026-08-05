import unittest

import numpy as np
import pandas as pd

from services.market_prediction_service import IntradayPredictionService


def make_bars(direction: float) -> pd.DataFrame:
    index = pd.date_range("2026-07-21 09:15", periods=70, freq="5min")
    close = 100 + np.arange(len(index)) * direction
    return pd.DataFrame(
        {
            "Close": close,
            "High": close + 0.35,
            "Low": close - 0.35,
            # The latest bar has a volume breakout so trend, momentum, and liquidity align.
            "Volume": [1_000] * 50 + [2_000] * 19 + [4_000],
        },
        index=index,
    )


class IntradayPredictionServiceTests(unittest.TestCase):
    def test_uptrend_creates_buy_with_risk_levels(self):
        result = IntradayPredictionService.build_prediction(make_bars(0.12), "RELIANCE")

        self.assertEqual(result["recommendation"], "BUY")
        self.assertTrue(result["tradeable"])
        self.assertGreater(result["target_price"], result["entry_price"])
        self.assertLess(result["stop_loss"], result["entry_price"])

    def test_downtrend_creates_sell_with_risk_levels(self):
        result = IntradayPredictionService.build_prediction(make_bars(-0.12), "RELIANCE")

        self.assertEqual(result["recommendation"], "SELL")
        self.assertTrue(result["tradeable"])
        self.assertLess(result["target_price"], result["entry_price"])
        self.assertGreater(result["stop_loss"], result["entry_price"])

    def test_short_history_returns_hold(self):
        result = IntradayPredictionService.build_prediction(make_bars(0.12).iloc[:20], "RELIANCE")

        self.assertEqual(result["recommendation"], "HOLD")
        self.assertFalse(result["tradeable"])

    def test_symbol_normalisation(self):
        self.assertEqual(IntradayPredictionService.normalise_symbol("reliance"), "RELIANCE.NS")
        self.assertEqual(IntradayPredictionService.normalise_symbol("NIFTY"), "^NSEI")
