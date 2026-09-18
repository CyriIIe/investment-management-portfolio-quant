"""Tests for the reference path-dependent coupon discounting."""

import unittest
from decimal import Decimal

from portfolio_quant.path_discounting import discount_coupon_on_path


TOLERANCE = Decimal("1e-20")


class PathDiscountingTests(unittest.TestCase):

    def test_zero_rates_preserve_coupon(self):
        result = discount_coupon_on_path(
            "100",
            365,
            ["0"] * 13,
        )

        self.assertEqual(result, Decimal("100"))

    def test_constant_path_matches_flat_rate(self):
        rate = Decimal("0.10")

        result = discount_coupon_on_path(
            "100",
            365,
            [rate] * 13,
        )

        expected = Decimal("100") * (-rate).exp()

        self.assertLessEqual(abs(result - expected), TOLERANCE)

    def test_piecewise_rates_use_each_period(self):
        # Six equal periods at 0%, then six at 20%.
        # Over one year, the integrated rate is 10%.
        rates = ["0"] * 6 + ["0.20"] * 6 + ["0.20"]

        result = discount_coupon_on_path(
            "100",
            365,
            rates,
        )

        expected = Decimal("100") * Decimal("-0.10").exp()

        self.assertLessEqual(abs(result - expected), TOLERANCE)

    def test_final_observation_does_not_affect_result(self):
        first = ["0.10"] * 13
        second = ["0.10"] * 12 + ["0.90"]

        self.assertEqual(
            discount_coupon_on_path("100", 365, first),
            discount_coupon_on_path("100", 365, second),
        )

    def test_higher_rates_reduce_present_value(self):
        low = discount_coupon_on_path(
            "100", 365, ["0.10"] * 13
        )
        high = discount_coupon_on_path(
            "100", 365, ["0.11"] * 13
        )

        self.assertLess(high, low)

    def test_invalid_inputs_are_rejected(self):
        cases = (
            ("-100", 365, ["0.10"] * 13),
            ("100", 0, ["0.10"] * 13),
            ("100", 366, ["0.10"] * 13),
            ("100", 365, ["0.10"] * 12),
            ("100", 365, ["-0.01"] * 13),
            ("100", 365, ["NaN"] * 13),
        )

        for amount, days, rates in cases:
            with self.subTest(amount=amount, days=days, rates=rates):
                with self.assertRaises(ValueError):
                    discount_coupon_on_path(amount, days, rates)


if __name__ == "__main__":
    unittest.main()
