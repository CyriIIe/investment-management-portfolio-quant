"""Tests for reproducible, fictional interest-rate paths."""

import unittest
from decimal import Decimal

from portfolio_quant.rate_paths import generate_rate_paths


def simulation(**overrides):
    parameters = {
        "initial_rate": "0.10",
        "monthly_volatility": "0.005",
        "months": 12,
        "path_count": 3,
        "seed": 42,
    }
    parameters.update(overrides)
    return generate_rate_paths(**parameters)


class RatePathTests(unittest.TestCase):
    def test_same_seed_produces_identical_paths(self):
        first = simulation()
        second = simulation()

        self.assertEqual(first.paths, second.paths)

    def test_different_seed_changes_paths(self):
        first = simulation(seed=42)
        second = simulation(seed=43)

        self.assertNotEqual(first.paths, second.paths)

    def test_path_dimensions_and_initial_rate(self):
        result = simulation()

        self.assertEqual(len(result.paths), 3)

        for path in result.paths:
            self.assertEqual(len(path), 13)
            self.assertEqual(path[0], Decimal("0.10"))

    def test_zero_volatility_produces_constant_rates(self):
        result = simulation(monthly_volatility="0")

        for path in result.paths:
            self.assertEqual(
                path,
                (Decimal("0.10"),) * 13,
            )

    def test_invalid_parameters_are_rejected(self):
        invalid_cases = (
            {"initial_rate": "-0.01"},
            {"monthly_volatility": "-0.01"},
            {"months": 0},
            {"path_count": 0},
            {"seed": -1},
            {"seed": True},
        )

        for parameters in invalid_cases:
            with self.subTest(parameters=parameters):
                with self.assertRaises(ValueError):
                    simulation(**parameters)

    def test_out_of_range_path_is_rejected_not_clipped(self):
        with self.assertRaisesRegex(
            ValueError, "Generated rate outside supported range"
        ):
            simulation(
                initial_rate="0",
                monthly_volatility="0.005",
                seed=42,
            )

    def test_results_are_explicitly_experimental(self):
        result = simulation()

        self.assertFalse(result.calibrated_to_market)
        self.assertFalse(result.portfolio_risk_measure)


if __name__ == "__main__":
    unittest.main()
