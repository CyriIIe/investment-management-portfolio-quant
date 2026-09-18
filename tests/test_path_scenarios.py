"""Tests for validated known-coupon path scenarios."""

import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal

from portfolio_quant.cashflow_adapter import CashflowEvent, CashflowRun
from portfolio_quant.path_discounting import discount_coupon_on_path
from portfolio_quant.path_scenarios import calculate_known_coupon_paths
from portfolio_quant.rate_paths import RatePathSimulation


TOLERANCE = Decimal("0.00000001")


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


def sample_simulation():
    return RatePathSimulation(
        seed=42,
        initial_rate=Decimal("0.10"),
        monthly_volatility=Decimal("0.005"),
        months=12,
        paths=(
            (Decimal("0.10"),) * 13,
            (Decimal("0"),) * 6 + (Decimal("0.20"),) * 7,
            (Decimal("0.10"),) * 12 + (Decimal("0.90"),),
        ),
    )


class KnownCouponPathTests(unittest.TestCase):
    def test_matches_python_reference_without_mixing_currencies(self):
        run = sample_run()
        simulation = sample_simulation()

        result = calculate_known_coupon_paths(run, simulation)

        self.assertEqual(result.path_count, 3)
        self.assertEqual(result.event_count, 3)

        for index, path in enumerate(simulation.paths):
            with self.subTest(path=index):
                actual = result.paths[index].present_value_by_currency

                self.assertEqual(set(actual), {"RUB", "USD"})

                for currency in ("RUB", "USD"):
                    expected = sum(
                        (
                            discount_coupon_on_path(
                                event.gross_amount,
                                (event.event_date - run.portfolio_date).days,
                                path,
                            )
                            for event in run.events
                            if event.currency == currency
                        ),
                        Decimal("0"),
                    )

                    self.assertLessEqual(
                        abs(actual[currency] - expected),
                        TOLERANCE,
                    )

    def test_incomplete_coverage_and_scope_are_preserved(self):
        result = calculate_known_coupon_paths(
            sample_run(), sample_simulation()
        )

        self.assertEqual(result.portfolio_date, "2026-09-10")
        self.assertEqual(result.cashflow_run_id, 8)
        self.assertEqual(result.seed, 42)
        self.assertEqual(result.coupon_coverage_pct, Decimal("91.67"))
        self.assertEqual(result.unknown_schedule_count, 25)
        self.assertFalse(result.includes_principal)
        self.assertFalse(result.complete_portfolio_valuation)
        self.assertFalse(result.calibrated_to_market)
        self.assertFalse(result.portfolio_risk_measure)

    def test_principal_is_rejected(self):
        run = sample_run()
        principal = replace(
            run.events[0],
            event_type="MATURITY_REDEMPTION",
        )

        with self.assertRaisesRegex(ValueError, "only coupons"):
            calculate_known_coupon_paths(
                replace(run, events=(principal,)),
                sample_simulation(),
            )

    def test_noncontractual_coupon_is_rejected(self):
        run = sample_run()
        conditional = replace(
            run.events[0],
            certainty="CONDITIONAL",
        )

        with self.assertRaisesRegex(ValueError, "only contractual"):
            calculate_known_coupon_paths(
                replace(run, events=(conditional,)),
                sample_simulation(),
            )

    def test_event_outside_horizon_is_rejected(self):
        run = sample_run()
        late = replace(
            run.events[0],
            event_date=date(2027, 9, 11),
        )

        with self.assertRaisesRegex(ValueError, "outside"):
            calculate_known_coupon_paths(
                replace(run, events=(late,)),
                sample_simulation(),
            )

    def test_nonexperimental_simulation_is_rejected(self):
        simulation = replace(
            sample_simulation(),
            calibrated_to_market=True,
        )

        with self.assertRaisesRegex(ValueError, "experimental"):
            calculate_known_coupon_paths(
                sample_run(), simulation
            )

    def test_unsupported_month_count_is_rejected(self):
        simulation = replace(sample_simulation(), months=13)

        with self.assertRaisesRegex(ValueError, "12 monthly"):
            calculate_known_coupon_paths(
                sample_run(), simulation
            )


if __name__ == "__main__":
    unittest.main()
