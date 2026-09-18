import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal

from portfolio_quant.cashflow_adapter import CashflowEvent, CashflowRun
from portfolio_quant.discounting import present_value_of_known_coupons


def sample_run():
    return CashflowRun(
        run_id=8,
        portfolio_date=date(2026, 9, 10),
        snapshot_ids=frozenset({101, 102}),
        events=(
            CashflowEvent(
                event_id=501,
                event_date=date(2027, 9, 10),
                event_type="COUPON",
                currency="RUB",
                gross_amount=Decimal("100"),
                certainty="CONTRACTUAL",
            ),
        ),
        coupon_coverage_pct=Decimal("91.67"),
        unknown_schedule_count=25,
        horizon_days=365,
    )


class DiscountingTests(unittest.TestCase):
    def test_zero_rate_preserves_known_coupon_amount(self):
        result = present_value_of_known_coupons(
            sample_run(),
            annual_discount_rate="0",
        )
        self.assertEqual(
            result.present_value_by_currency["RUB"],
            Decimal("100"),
        )

    def test_higher_rate_reduces_present_value(self):
        run = sample_run()
        low = present_value_of_known_coupons(
            run, annual_discount_rate="0.10"
        )
        high = present_value_of_known_coupons(
            run, annual_discount_rate="0.20"
        )
        self.assertLess(
            high.present_value_by_currency["RUB"],
            low.present_value_by_currency["RUB"],
        )

    def test_incomplete_coverage_is_preserved(self):
        result = present_value_of_known_coupons(
            sample_run(),
            annual_discount_rate="0.10",
        )
        self.assertEqual(result.coupon_coverage_pct, Decimal("91.67"))
        self.assertEqual(result.unknown_schedule_count, 25)
        self.assertFalse(result.includes_principal)
        self.assertFalse(result.complete_portfolio_valuation)

    def test_principal_event_is_rejected(self):
        run = sample_run()
        principal = replace(
            run.events[0],
            event_type="MATURITY_REDEMPTION",
        )
        with self.assertRaisesRegex(ValueError, "coupon events only"):
            present_value_of_known_coupons(
                replace(run, events=(principal,)),
                annual_discount_rate="0.10",
            )

    def test_event_outside_horizon_is_rejected(self):
        run = sample_run()
        late = replace(run.events[0], event_date=date(2027, 9, 11))
        with self.assertRaisesRegex(ValueError, "outside"):
            present_value_of_known_coupons(
                replace(run, events=(late,)),
                annual_discount_rate="0.10",
            )

    def test_currencies_remain_separate(self):
        run = sample_run()
        usd_coupon = replace(
            run.events[0],
            event_id=502,
            currency="USD",
            gross_amount=Decimal("20"),
        )
        result = present_value_of_known_coupons(
            replace(run, events=run.events + (usd_coupon,)),
            annual_discount_rate="0",
        )
        self.assertEqual(
            result.present_value_by_currency,
            {"RUB": Decimal("100"), "USD": Decimal("20")},
        )

    def test_invalid_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            present_value_of_known_coupons(
                sample_run(),
                annual_discount_rate="-0.01",
            )


if __name__ == "__main__":
    unittest.main()
