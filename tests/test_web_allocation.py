"""Offline tests for the portfolio allocation API reader."""

import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from portfolio_quant.core_adapter import Position, PortfolioSnapshot
from portfolio_quant import web_allocation


def fictional_snapshot():
    return PortfolioSnapshot(
        as_of_date=date(2026, 9, 10),
        source_hash="fictional-test",
        positions=(
            Position(
                isin="RU000A000001",
                security_code=None,
                market_section="TQCB",
                currency="RUB",
                quantity=Decimal("2"),
                market_value_ex_accrued=Decimal("70"),
                accrued_interest=Decimal("10"),
                source_observation_id=1,
            ),
            Position(
                isin="RU000A000002",
                security_code=None,
                market_section="TQCB",
                currency="RUB",
                quantity=Decimal("1"),
                market_value_ex_accrued=Decimal("20"),
                accrued_interest=Decimal("0"),
                source_observation_id=2,
            ),
        ),
    )


class WebAllocationTests(unittest.TestCase):
    def test_returns_weights_without_quantities_or_amounts(self):
        inputs = SimpleNamespace(snapshot=fictional_snapshot())
        with patch.object(
            web_allocation, "load_core_inputs", return_value=inputs
        ):
            result = web_allocation.read_allocation()

        self.assertEqual(result["as_of_date"], "2026-09-10")
        self.assertEqual(len(result["currencies"]), 1)
        group = result["currencies"][0]
        self.assertEqual(group["currency"], "RUB")
        self.assertTrue(group["weights_available"])
        self.assertEqual(
            [asset["weight_pct"] for asset in group["assets"]],
            ["80", "20"],
        )
        self.assertFalse(result["includes_cash"])
        self.assertTrue(result["includes_accrued_interest"])
        self.assertFalse(result["portfolio_risk_measure"])
        self.assertFalse(result["performance_measure"])
        for asset in group["assets"]:
            self.assertEqual(
                set(asset),
                {"isin", "security_code", "market_section", "weight_pct"},
            )

    def test_propagates_missing_core_inputs(self):
        with patch.object(
            web_allocation,
            "load_core_inputs",
            side_effect=RuntimeError("Missing matching CORE inputs"),
        ):
            with self.assertRaisesRegex(RuntimeError, "CORE inputs"):
                web_allocation.read_allocation()


if __name__ == "__main__":
    unittest.main()
