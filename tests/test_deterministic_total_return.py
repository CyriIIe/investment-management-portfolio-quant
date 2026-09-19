"""Hand-checkable synthetic tests for deterministic bond returns."""

import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal

from portfolio_quant.deterministic_total_return import (
    BondCase,
    BondFlow,
    calculate_total_return,
)


def sample_bond():
    return BondCase(
        valuation_date=date(2026, 1, 1),
        horizon_date=date(2027, 1, 1),
        currency="RUB",
        dirty_price=Decimal("100"),
        remaining_principal=Decimal("100"),
        flows=(
            BondFlow(date(2027, 1, 1), "COUPON", Decimal("5")),
            BondFlow(date(2028, 1, 1), "COUPON", Decimal("5")),
            BondFlow(date(2028, 1, 1), "PRINCIPAL", Decimal("100")),
        ),
        fixed_coupon_verified=True,
        complete_schedule_verified=True,
        primary_board_verified=True,
    )


class DeterministicTotalReturnTests(unittest.TestCase):
    def test_three_hand_checkable_flat_yield_scenarios(self):
        results = calculate_total_return(
            sample_bond(),
            annual_market_yields=("0", "0.05", "0.10"),
        )

        self.assertEqual(len(results), 3)
        self.assertEqual(
            [r.received_before_or_on_horizon for r in results],
            [Decimal("5")] * 3,
        )
        self.assertEqual(results[0].theoretical_terminal_price,
                         Decimal("105"))
        self.assertEqual(results[0].terminal_wealth, Decimal("110"))
        self.assertEqual(results[0].total_return, Decimal("0.10"))

        self.assertEqual(results[1].theoretical_terminal_price,
                         Decimal("100"))
        self.assertEqual(results[1].total_return, Decimal("0.05"))

        expected_terminal = Decimal("105") / Decimal("1.10")
        tolerance = Decimal("1e-24")
        self.assertLessEqual(
            abs(results[2].theoretical_terminal_price - expected_terminal),
            tolerance,
        )
        expected_return = (
            Decimal("5") + expected_terminal - Decimal("100")
        ) / Decimal("100")
        self.assertLessEqual(
            abs(results[2].total_return - expected_return),
            tolerance,
        )

    def test_incomplete_schedule_is_refused(self):
        with self.assertRaisesRegex(ValueError, "not verified"):
            calculate_total_return(
                replace(sample_bond(), complete_schedule_verified=False),
                annual_market_yields=("0.05",),
            )

    def test_primary_board_not_verified_is_refused(self):
        with self.assertRaisesRegex(ValueError, "not verified"):
            calculate_total_return(
                replace(sample_bond(), primary_board_verified=False),
                annual_market_yields=("0.05",),
            )

    def test_missing_principal_is_refused(self):
        bond = sample_bond()
        with self.assertRaisesRegex(ValueError, "Principal schedule"):
            calculate_total_return(
                replace(bond, flows=bond.flows[:2]),
                annual_market_yields=("0.05",),
            )

    def test_conditional_offer_is_refused(self):
        bond = sample_bond()
        with self.assertRaisesRegex(ValueError, "conditional"):
            calculate_total_return(
                replace(
                    bond,
                    flows=bond.flows + (
                        BondFlow(
                            date(2027, 6, 1),
                            "OFFER_REDEMPTION",
                            Decimal("100"),
                        ),
                    ),
                ),
                annual_market_yields=("0.05",),
            )

    def test_duplicate_scenarios_are_refused(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            calculate_total_return(
                sample_bond(),
                annual_market_yields=("0.05", Decimal("0.05")),
            )


if __name__ == "__main__":
    unittest.main()
