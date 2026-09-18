"""Tests for the Python-to-Rust fictional path bridge."""

import subprocess
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from portfolio_quant.path_bridge import discount_paths_rust
from portfolio_quant.path_discounting import discount_coupon_on_path


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "rust/quant_core/target/release/quant_paths"
TOLERANCE = Decimal("0.00000001")

COUPONS = [
    ("100", 30),
    ("125.50", 180),
    ("200", 365),
]

PATHS = [
    ["0.10"] * 13,
    ["0"] * 6 + ["0.20"] * 7,
    ["0.10"] * 12 + ["0.90"],
    ["0"] * 13,
]


class PathBridgeTests(unittest.TestCase):
    def test_matches_python_reference(self):
        totals = discount_paths_rust(
            COUPONS, PATHS, binary_path=BINARY
        )

        self.assertEqual(len(totals), len(PATHS))

        for index, (path, actual) in enumerate(zip(PATHS, totals)):
            with self.subTest(path=index):
                expected = sum(
                    (
                        discount_coupon_on_path(amount, days, path)
                        for amount, days in COUPONS
                    ),
                    Decimal("0"),
                )

                self.assertLessEqual(
                    abs(actual - expected),
                    TOLERANCE,
                )

    def test_invalid_inputs_are_rejected(self):
        cases = (
            ([], PATHS),
            (COUPONS, []),
            ([("-1", 30)], PATHS),
            ([("100", 0)], PATHS),
            ([("100", 366)], PATHS),
            ([("100", True)], PATHS),
            (COUPONS, [["0.10"] * 12]),
            (COUPONS, [["NaN"] * 13]),
            (COUPONS, [["-0.01"] * 13]),
        )

        for coupons, paths in cases:
            with self.subTest(coupons=coupons, paths=paths):
                with self.assertRaises(ValueError):
                    discount_paths_rust(
                        coupons, paths, binary_path=BINARY
                    )

    def test_batch_limits_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "exceeds Rust limits"):
            discount_paths_rust(
                COUPONS,
                PATHS * 2501,
                binary_path=BINARY,
            )

    def test_missing_binary_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            discount_paths_rust(
                COUPONS,
                PATHS,
                binary_path=ROOT / "nonexistent_quant_paths",
            )

    def test_incomplete_rust_output_is_rejected(self):
        fake_result = subprocess.CompletedProcess(
            args=["quant_paths"],
            returncode=0,
            stdout="1.0\n",
            stderr="",
        )

        with patch(
            "portfolio_quant.path_bridge.subprocess.run",
            return_value=fake_result,
        ):
            with self.assertRaisesRegex(
                ValueError, "unexpected number"
            ):
                discount_paths_rust(
                    COUPONS, PATHS, binary_path=BINARY
                )


if __name__ == "__main__":
    unittest.main()
