"""Tests for deterministic, experimental Quant cycle identities."""

import unittest

from portfolio_quant.cycle_identity import cycle_identity


def parameters():
    return {
        "positions_sha256": "a" * 64,
        "cashflow_input_sha256": "b" * 64,
        "cashflow_result_sha256": "c" * 64,
        "cashflow_policy_sha256": "d" * 64,
        "rust_binary_sha256": "e" * 64,
        "initial_rate": "0.10",
        "monthly_volatility": "0.005",
        "months": 12,
        "path_count": 10,
        "seed": 42,
    }


class CycleIdentityTests(unittest.TestCase):
    def test_same_inputs_have_same_identity(self):
        first = cycle_identity(**parameters())
        second = cycle_identity(**parameters())

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_equivalent_decimal_strings_have_same_identity(self):
        original = parameters()
        equivalent = parameters()
        equivalent["initial_rate"] = "0.1000"
        equivalent["monthly_volatility"] = "0.0050"

        self.assertEqual(
            cycle_identity(**original),
            cycle_identity(**equivalent),
        )

    def test_each_source_hash_changes_identity(self):
        original = parameters()
        baseline = cycle_identity(**original)

        for field in (
            "positions_sha256",
            "cashflow_input_sha256",
            "cashflow_result_sha256",
            "cashflow_policy_sha256",
            "rust_binary_sha256",
        ):
            with self.subTest(field=field):
                changed = parameters()
                changed[field] = "f" * 64
                self.assertNotEqual(
                    baseline,
                    cycle_identity(**changed),
                )

    def test_each_simulation_parameter_changes_identity(self):
        baseline = cycle_identity(**parameters())

        changes = {
            "initial_rate": "0.11",
            "monthly_volatility": "0.006",
            "path_count": 11,
            "seed": 43,
        }

        for field, value in changes.items():
            with self.subTest(field=field):
                changed = parameters()
                changed[field] = value
                self.assertNotEqual(
                    baseline,
                    cycle_identity(**changed),
                )

    def test_invalid_source_hashes_are_rejected(self):
        for invalid in ("abc", "G" * 64, "A" * 64, None):
            with self.subTest(invalid=invalid):
                changed = parameters()
                changed["positions_sha256"] = invalid
                with self.assertRaises(ValueError):
                    cycle_identity(**changed)

    def test_invalid_simulation_parameters_are_rejected(self):
        changes = {
            "initial_rate": "1.01",
            "monthly_volatility": "-0.01",
            "months": 13,
            "path_count": 0,
            "seed": True,
        }

        for field, value in changes.items():
            with self.subTest(field=field):
                changed = parameters()
                changed[field] = value
                with self.assertRaises(ValueError):
                    cycle_identity(**changed)


if __name__ == "__main__":
    unittest.main()
