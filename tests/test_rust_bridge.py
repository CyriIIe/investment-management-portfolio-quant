"""Tests for the Python-to-Rust batch calculation bridge."""

import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from portfolio_quant.cashflow_adapter import CashflowEvent, CashflowRun
from portfolio_quant.discounting import present_value_of_known_coupons
from portfolio_quant.rust_bridge import discount_batch_rust


class RustBridgeTests(unittest.TestCase):
    def test_batch_matches_python_reference(self):
        cases = [
            ("100", 365, "0.10"),
            ("125.50", 30, "0.11"),
            ("1000000", 200, "0.075"),
        ]

        rust_values = discount_batch_rust(cases)

        self.assertEqual(len(rust_values), len(cases))

        start = date(2026, 9, 10)
        tolerance = Decimal("0.00000001")

        for index, ((amount, days, rate), rust_value) in enumerate(
            zip(cases, rust_values), start=1
        ):
            with self.subTest(case=index):
                run = CashflowRun(
                    run_id=1,
                    portfolio_date=start,
                    snapshot_ids=frozenset({1}),
                    events=(
                        CashflowEvent(
                            event_id=index,
                            event_date=start + timedelta(days=days),
                            event_type="COUPON",
                            currency="RUB",
                            gross_amount=Decimal(amount),
                            certainty="CONTRACTUAL",
                        ),
                    ),
                    coupon_coverage_pct=Decimal("100"),
                    unknown_schedule_count=0,
                    horizon_days=365,
                )

                python_value = present_value_of_known_coupons(
                    run,
                    annual_discount_rate=rate,
                ).present_value_by_currency["RUB"]

                self.assertLessEqual(
                    abs(python_value - rust_value),
                    tolerance,
                )

    def test_empty_batch(self):
        self.assertEqual(discount_batch_rust([]), ())

    def test_negative_amount_is_rejected(self):
        with self.assertRaises(ValueError):
            discount_batch_rust([("-1", 30, "0.10")])

    def test_invalid_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            discount_batch_rust([("100", 30, "1.01")])

    def test_missing_binary_is_reported(self):
        missing = Path("/nonexistent/portfolio-quant/quant_batch")

        with self.assertRaises(FileNotFoundError):
            discount_batch_rust(
                [("100", 30, "0.10")],
                binary_path=missing,
            )


if __name__ == "__main__":
    unittest.main()
