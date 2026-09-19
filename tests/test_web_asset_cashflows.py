"""Synthetic tests for the individual cashflow API reader."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from portfolio_quant.asset_cashflows import (
    AssetCashflowAssociation,
    AssetCashflowSummary,
)
from portfolio_quant import web_asset_cashflows


class WebAssetCashflowsTests(unittest.TestCase):
    def test_exposes_metadata_without_amounts_or_quantities(self):
        inputs = SimpleNamespace(
            snapshot=SimpleNamespace(as_of_date=date(2026, 9, 10))
        )
        association = AssetCashflowAssociation(
            assets=(
                AssetCashflowSummary(
                    isin="RU000A000001",
                    security_code="TEST",
                    market_section="TQCB",
                    currency="RUB",
                    known_event_count=2,
                    next_known_event_date=date(2026, 10, 15),
                    incomplete_reasons=("MISSING_MATURITY",),
                ),
            ),
            unassigned_event_count=1,
            unassigned_schedule_count=1,
        )

        with (
            patch.object(
                web_asset_cashflows,
                "load_core_inputs",
                return_value=inputs,
            ),
            patch.object(
                web_asset_cashflows,
                "associate_asset_cashflows",
                return_value=association,
            ),
        ):
            result = web_asset_cashflows.read_asset_cashflows()

        self.assertEqual(result["as_of_date"], "2026-09-10")
        self.assertEqual(result["unassigned_event_count"], 1)
        self.assertEqual(result["unassigned_schedule_count"], 1)
        self.assertFalse(result["complete_cashflows"])
        self.assertFalse(result["performance_measure"])
        self.assertFalse(result["portfolio_risk_measure"])

        asset = result["assets"][0]
        self.assertEqual(
            set(asset),
            {
                "isin",
                "security_code",
                "market_section",
                "currency",
                "known_event_count",
                "next_known_event_date",
                "incomplete_reasons",
            },
        )
        self.assertEqual(asset["known_event_count"], 2)
        self.assertEqual(asset["next_known_event_date"], "2026-10-15")
        self.assertEqual(asset["incomplete_reasons"], ["MISSING_MATURITY"])

    def test_propagates_missing_core_inputs(self):
        with patch.object(
            web_asset_cashflows,
            "load_core_inputs",
            side_effect=RuntimeError("Missing matching CORE inputs"),
        ):
            with self.assertRaisesRegex(RuntimeError, "CORE inputs"):
                web_asset_cashflows.read_asset_cashflows()


if __name__ == "__main__":
    unittest.main()
