"""Tests for the compact Python-to-Rust scenario bridge."""

import unittest
from decimal import Decimal
from pathlib import Path

from portfolio_quant.grid_bridge import discount_grid_rust


class GridBridgeTests(unittest.TestCase):
    def test_totals_match_python_reference(self):
        coupons = [
            ("100", 365),
            ("125.50", 30),
            ("250", 180),
        ]
        rates = ["0", "0.10", "0.11"]

        rust_totals = discount_grid_rust(coupons, rates)

        self.assertEqual(len(rust_totals), len(rates))

        for rate_text, rust_total in zip(rates, rust_totals):
            with self.subTest(rate=rate_text):
                rate = Decimal(rate_text)
                expected = sum(
                    (
                        Decimal(amount)
                        * (-rate * Decimal(days) / Decimal("365")).exp()
                        for amount, days in coupons
                    ),
                    Decimal("0"),
                )

                self.assertLessEqual(
                    abs(rust_total - expected),
                    Decimal("0.00000001"),
                )

    def test_higher_rate_reduces_total(self):
        low, high = discount_grid_rust(
            [("100", 365)],
            ["0.10", "0.11"],
        )
        self.assertLess(high, low)

    def test_negative_coupon_is_rejected(self):
        with self.assertRaises(ValueError):
            discount_grid_rust(
                [("-100", 30)],
                ["0.10"],
            )

    def test_empty_rates_are_rejected(self):
        with self.assertRaises(ValueError):
            discount_grid_rust(
                [("100", 30)],
                [],
            )

    def test_missing_binary_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            discount_grid_rust(
                [("100", 30)],
                ["0.10"],
                binary_path=Path("/nonexistent/quant_grid"),
            )


if __name__ == "__main__":
    unittest.main()
