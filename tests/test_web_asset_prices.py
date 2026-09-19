"""Synthetic tests for the individual broker-price API reader."""

import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from portfolio_quant.core_adapter import Position
from portfolio_quant import web_asset_prices


class WebAssetPricesTests(unittest.TestCase):
    def test_exposes_dated_per_unit_broker_values(self):
        position = Position(
            isin="RU000A000001",
            security_code="TEST",
            market_section="TQCB",
            currency="RUB",
            quantity=Decimal("3"),
            market_value_ex_accrued=Decimal("2850.00"),
            accrued_interest=Decimal("45.00"),
            source_observation_id=501,
        )
        inputs = SimpleNamespace(
            snapshot=SimpleNamespace(
                as_of_date=date(2026, 9, 10),
                positions=(position,),
            )
        )

        with patch.object(
            web_asset_prices, "load_core_inputs", return_value=inputs
        ):
            result = web_asset_prices.read_asset_prices()

        self.assertEqual(result["as_of_date"], "2026-09-10")
        self.assertEqual(len(result["assets"]), 1)
        self.assertFalse(result["performance_measure"])
        self.assertFalse(result["portfolio_risk_measure"])

        asset = result["assets"][0]
        self.assertEqual(asset, {
            "isin": "RU000A000001",
            "security_code": "TEST",
            "market_section": "TQCB",
            "currency": "RUB",
            "clean_price_per_unit": "950.00",
            "accrued_interest_per_unit": "15.00",
            "dirty_price_per_unit": "965.00",
        })
        self.assertNotIn("quantity", asset)

    def test_propagates_missing_core_inputs(self):
        with patch.object(
            web_asset_prices,
            "load_core_inputs",
            side_effect=RuntimeError("Missing matching CORE inputs"),
        ):
            with self.assertRaisesRegex(RuntimeError, "CORE inputs"):
                web_asset_prices.read_asset_prices()


if __name__ == "__main__":
    unittest.main()
