"""Offline tests using exclusively fictional portfolio positions."""

import unittest
from datetime import date
from decimal import Decimal

from portfolio_quant.core_adapter import Position, PortfolioSnapshot
from portfolio_quant.portfolio_allocation import (
    build_portfolio_allocation,
)


def position(isin, currency, value, accrued="0"):
    return Position(
        isin=isin,
        security_code=None,
        market_section="TQCB",
        currency=currency,
        quantity=Decimal("1"),
        market_value_ex_accrued=Decimal(value),
        accrued_interest=Decimal(accrued),
        source_observation_id=1,
    )


def snapshot(*positions):
    return PortfolioSnapshot(
        as_of_date=date(2026, 9, 10),
        source_hash="fictional-test",
        positions=positions,
    )


class PortfolioAllocationTests(unittest.TestCase):
    def test_weights_include_accrued_interest(self):
        result = build_portfolio_allocation(snapshot(
            position("RU000A000001", "RUB", "70", "10"),
            position("RU000A000002", "RUB", "20", "0"),
        ))
        group = result.currencies[0]

        self.assertEqual(group.currency, "RUB")
        self.assertTrue(group.weights_available)
        self.assertEqual(
            [asset.weight_pct for asset in group.assets],
            [Decimal("80"), Decimal("20")],
        )
        self.assertFalse(result.includes_cash)
        self.assertTrue(result.includes_accrued_interest)
        self.assertFalse(result.performance_measure)
        self.assertFalse(result.portfolio_risk_measure)

    def test_currencies_are_never_combined(self):
        result = build_portfolio_allocation(snapshot(
            position("RU000A000001", "RUB", "100"),
            position("RU000A000002", "USD", "100"),
        ))

        self.assertEqual(
            [group.currency for group in result.currencies],
            ["RUB", "USD"],
        )
        for group in result.currencies:
            self.assertEqual(group.assets[0].weight_pct, Decimal("100"))

    def test_zero_total_has_no_fabricated_weights(self):
        result = build_portfolio_allocation(snapshot(
            position("RU000A000001", "RUB", "0"),
            position("RU000A000002", "RUB", "0"),
        ))
        group = result.currencies[0]

        self.assertFalse(group.weights_available)
        self.assertTrue(
            all(asset.weight_pct is None for asset in group.assets)
        )

    def test_rejects_unexpected_input(self):
        with self.assertRaisesRegex(ValueError, "CORE snapshot"):
            build_portfolio_allocation(None)


if __name__ == "__main__":
    unittest.main()
