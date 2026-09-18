"""Tests for experimental coupon scenarios using the Rust bridge."""

import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal

from portfolio_quant.cashflow_adapter import CashflowEvent, CashflowRun
from portfolio_quant.discounting import present_value_of_known_coupons
from portfolio_quant.scenarios import calculate_coupon_scenarios


def sample_run():
    return CashflowRun(
        run_id=8,
        portfolio_date=date(2026, 9, 10),
        snapshot_ids=frozenset({101, 102}),
        events=(
            CashflowEvent(
                event_id=501,
                event_date=date(2026, 10, 10),
                event_type="COUPON",
                currency="RUB",
                gross_amount=Decimal("125.50"),
                certainty="CONTRACTUAL",
            ),
            CashflowEvent(
                event_id=502,
                event_date=date(2027, 3, 10),
                event_type="COUPON",
                currency="RUB",
                gross_amount=Decimal("100"),
                certainty="CONTRACTUAL",
            ),
            CashflowEvent(
                event_id=503,
                event_date=date(2026, 12, 10),
                event_type="COUPON",
                currency="USD",
                gross_amount=Decimal("20"),
                certainty="CONTRACTUAL",
            ),
        ),
        coupon_coverage_pct=Decimal("91.67"),
        unknown_schedule_count=25,
        horizon_days=365,
    )


class ScenarioTests(unittest.TestCase):
    def test_scenarios_match_python_reference_by_currency(self):
        run = sample_run()
        rates = ["0", "0.10", "0.11", "0.20"]

        grid = calculate_coupon_scenarios(
            run,
            annual_rates=rates,
        )

        self.assertEqual(len(grid.scenarios), len(rates))
        self.assertEqual(grid.event_count, 3)

        for scenario, rate in zip(grid.scenarios, rates):
            with self.subTest(rate=rate):
                reference = present_value_of_known_coupons(
                    run,
                    annual_discount_rate=rate,
                )

                self.assertEqual(
                    set(scenario.present_value_by_currency),
                    set(reference.present_value_by_currency),
                )

                for currency, python_value in (
                    reference.present_value_by_currency.items()
                ):
                    rust_value = (
                        scenario.present_value_by_currency[currency]
                    )

                    self.assertLessEqual(
                        abs(rust_value - python_value),
                        Decimal("0.00000001"),
                    )

    def test_higher_rate_reduces_known_coupon_value(self):
        grid = calculate_coupon_scenarios(
            sample_run(),
            annual_rates=["0.10", "0.11"],
        )

        lower, higher = grid.scenarios

        for currency in lower.present_value_by_currency:
            self.assertLess(
                higher.present_value_by_currency[currency],
                lower.present_value_by_currency[currency],
            )

    def test_incomplete_coverage_is_preserved(self):
        grid = calculate_coupon_scenarios(
            sample_run(),
            annual_rates=["0.10"],
        )

        self.assertEqual(grid.coupon_coverage_pct, Decimal("91.67"))
        self.assertEqual(grid.unknown_schedule_count, 25)
        self.assertFalse(grid.includes_principal)
        self.assertFalse(grid.complete_portfolio_valuation)

    def test_duplicate_rates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            calculate_coupon_scenarios(
                sample_run(),
                annual_rates=["0.10", Decimal("0.10")],
            )

    def test_principal_event_is_rejected(self):
        run = sample_run()
        principal = replace(
            run.events[0],
            event_type="MATURITY_REDEMPTION",
        )

        with self.assertRaisesRegex(ValueError, "only coupons"):
            calculate_coupon_scenarios(
                replace(run, events=(principal,)),
                annual_rates=["0.10"],
            )

    def test_event_outside_horizon_is_rejected(self):
        run = sample_run()
        late = replace(
            run.events[0],
            event_date=date(2027, 9, 11),
        )

        with self.assertRaisesRegex(ValueError, "outside"):
            calculate_coupon_scenarios(
                replace(run, events=(late,)),
                annual_rates=["0.10"],
            )


if __name__ == "__main__":
    unittest.main()
