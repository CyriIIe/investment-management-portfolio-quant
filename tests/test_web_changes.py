"""Offline tests for aggregate historical portfolio changes."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from portfolio_quant import web_changes
from portfolio_quant.portfolio_changes import PortfolioChanges


class WebChangesTests(unittest.TestCase):
    def test_returns_aggregate_changes_only(self):
        current = SimpleNamespace(as_of_date=date(2026, 9, 10))
        previous = object()
        comparison = PortfolioChanges(
            previous_date="2026-09-09",
            current_date="2026-09-10",
            previous_position_count=11,
            current_position_count=12,
            added_count=1,
            removed_count=0,
            quantity_changed_count=0,
            value_changed_at_constant_quantity_count=9,
            accrued_changed_at_constant_quantity_count=10,
            source_only_changed_count=0,
            unchanged_count=0,
        )

        with (
            patch.object(
                web_changes, "load_core_inputs",
                return_value=SimpleNamespace(snapshot=current),
            ) as load,
            patch.object(
                web_changes, "load_previous_historical_snapshot",
                return_value=previous,
            ) as previous_reader,
            patch.object(
                web_changes, "compare_portfolio_snapshots",
                return_value=comparison,
            ) as compare,
        ):
            result = web_changes.read_changes()

        load.assert_called_once_with()
        previous_reader.assert_called_once_with(date(2026, 9, 10))
        compare.assert_called_once_with(previous, current)
        self.assertEqual(result["added_count"], 1)
        self.assertEqual(result["previous_position_count"], 11)
        self.assertEqual(result["current_position_count"], 12)
        self.assertFalse(result["performance_measure"])
        self.assertFalse(result["portfolio_risk_measure"])

        for private_field in (
            "positions", "isin", "quantity", "market_value",
            "gross_amount", "cashflows",
        ):
            self.assertNotIn(private_field, result)

    def test_missing_previous_snapshot_is_not_silently_ignored(self):
        current = SimpleNamespace(as_of_date=date(2026, 9, 10))

        with (
            patch.object(
                web_changes, "load_core_inputs",
                return_value=SimpleNamespace(snapshot=current),
            ),
            patch.object(
                web_changes,
                "load_previous_historical_snapshot",
                side_effect=ValueError("No preceding CORE snapshot"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "No preceding"):
                web_changes.read_changes()


if __name__ == "__main__":
    unittest.main()
