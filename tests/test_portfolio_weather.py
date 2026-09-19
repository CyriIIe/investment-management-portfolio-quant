"""Offline tests for the descriptive portfolio weather."""

import unittest
from datetime import date
from decimal import Decimal

from portfolio_quant.cashflow_adapter import CashflowEvent, CashflowRun
from portfolio_quant.core_adapter import PortfolioSnapshot, Position
from portfolio_quant.core_readonly import CoreInputs
from portfolio_quant.portfolio_weather import build_portfolio_weather


def sample_inputs():
    portfolio_date = date(2026, 9, 10)

    snapshot = PortfolioSnapshot(
        as_of_date=portfolio_date,
        source_hash="synthetic-test-hash",
        positions=(
            Position(
                isin="RU000A000000",
                security_code="TEST",
                market_section="TQCB",
                currency="RUB",
                quantity=Decimal("3"),
                market_value_ex_accrued=Decimal("2850"),
                accrued_interest=Decimal("45"),
                source_observation_id=501,
            ),
        ),
    )

    cashflows = CashflowRun(
        run_id=8,
        portfolio_date=portfolio_date,
        snapshot_ids=frozenset({101}),
        events=(
            CashflowEvent(
                event_id=1,
                event_date=date(2026, 10, 15),
                event_type="COUPON",
                currency="RUB",
                gross_amount=Decimal("125.50"),
                certainty="CONTRACTUAL",
            ),
            CashflowEvent(
                event_id=2,
                event_date=date(2026, 11, 15),
                event_type="COUPON",
                currency="RUB",
                gross_amount=Decimal("125.50"),
                certainty="CONTRACTUAL",
            ),
        ),
        coupon_coverage_pct=Decimal("50.00"),
        unknown_schedule_count=1,
        horizon_days=365,
    )

    return CoreInputs(snapshot=snapshot, cashflows=cashflows)


class PortfolioWeatherTests(unittest.TestCase):
    def test_descriptive_summary(self):
        weather = build_portfolio_weather(sample_inputs())

        self.assertEqual(weather.portfolio_date, date(2026, 9, 10))
        self.assertEqual(weather.cashflow_run_id, 8)
        self.assertEqual(weather.position_count, 1)
        self.assertEqual(weather.coupon_coverage_pct, Decimal("50.00"))
        self.assertEqual(weather.unknown_schedule_count, 1)
        self.assertEqual(weather.cashflow_horizon_days, 365)
        self.assertEqual(weather.event_count, 2)
        self.assertEqual(weather.events_by_type, (("COUPON", 2),))
        self.assertEqual(weather.events_by_currency, (("RUB", 2),))
        self.assertFalse(weather.complete_cashflows)
        self.assertFalse(weather.portfolio_risk_measure)

    def test_mismatched_dates_are_rejected(self):
        inputs = sample_inputs()
        different_cashflows = CashflowRun(
            run_id=inputs.cashflows.run_id,
            portfolio_date=date(2026, 9, 11),
            snapshot_ids=inputs.cashflows.snapshot_ids,
            events=inputs.cashflows.events,
            coupon_coverage_pct=inputs.cashflows.coupon_coverage_pct,
            unknown_schedule_count=inputs.cashflows.unknown_schedule_count,
            horizon_days=inputs.cashflows.horizon_days,
        )

        with self.assertRaisesRegex(ValueError, "dates differ"):
            build_portfolio_weather(
                CoreInputs(inputs.snapshot, different_cashflows)
            )

    def test_rejects_unvalidated_input_type(self):
        with self.assertRaisesRegex(ValueError, "Expected validated CORE inputs"):
            build_portfolio_weather(None)


if __name__ == "__main__":
    unittest.main()
