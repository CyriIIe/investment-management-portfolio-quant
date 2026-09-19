"""Offline tests for descriptive portfolio changes."""

import unittest
from datetime import date
from decimal import Decimal

from portfolio_quant.core_adapter import PortfolioSnapshot, Position
from portfolio_quant.portfolio_changes import compare_portfolio_snapshots


def position(
    isin: str,
    *,
    quantity: str = "3",
    value: str = "2850",
    accrued: str = "45",
    source_id: int = 1,
) -> Position:
    return Position(
        isin=isin,
        security_code=None,
        market_section="TQCB",
        currency="RUB",
        quantity=Decimal(quantity),
        market_value_ex_accrued=Decimal(value),
        accrued_interest=Decimal(accrued),
        source_observation_id=source_id,
    )


def snapshot(day: int, *positions: Position) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        as_of_date=date(2026, 9, day),
        source_hash="synthetic-test-hash",
        positions=positions,
    )


class PortfolioChangesTests(unittest.TestCase):
    def test_addition_and_removal_are_distinct(self):
        result = compare_portfolio_snapshots(
            snapshot(9, position("RU000A000001")),
            snapshot(10, position("RU000A000002")),
        )
        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.removed_count, 1)
        self.assertFalse(result.performance_measure)
        self.assertFalse(result.portfolio_risk_measure)

    def test_quantity_change_is_not_called_performance(self):
        result = compare_portfolio_snapshots(
            snapshot(9, position("RU000A000001")),
            snapshot(10, position("RU000A000001", quantity="4")),
        )
        self.assertEqual(result.quantity_changed_count, 1)
        self.assertEqual(
            result.value_changed_at_constant_quantity_count, 0
        )
        self.assertFalse(result.performance_measure)

    def test_value_accrued_and_source_are_distinguished(self):
        result = compare_portfolio_snapshots(
            snapshot(
                9,
                position("RU000A000001"),
                position("RU000A000002"),
                position("RU000A000003"),
            ),
            snapshot(
                10,
                position("RU000A000001", value="2800"),
                position("RU000A000002", accrued="47"),
                position("RU000A000003", source_id=2),
            ),
        )
        self.assertEqual(
            result.value_changed_at_constant_quantity_count, 1
        )
        self.assertEqual(
            result.accrued_changed_at_constant_quantity_count, 1
        )
        self.assertEqual(result.source_only_changed_count, 1)

    def test_dates_must_be_chronological(self):
        with self.assertRaisesRegex(ValueError, "chronological"):
            compare_portfolio_snapshots(
                snapshot(10, position("RU000A000001")),
                snapshot(9, position("RU000A000001")),
            )


if __name__ == "__main__":
    unittest.main()
