"""Cross-language parity for fictional coupon discounting paths."""

import subprocess
import unittest
from decimal import Decimal
from pathlib import Path

from portfolio_quant.path_discounting import discount_coupon_on_path


ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = Decimal("0.00000001")


class PathParityTests(unittest.TestCase):
    def test_rust_matches_python_on_fictional_paths(self):
        constant = ["0.10"] * 13
        variable = ["0"] * 6 + ["0.20"] * 7
        changed_endpoint = ["0.10"] * 12 + ["0.90"]

        cases = [
            ("100", 365, constant),
            ("100", 365, variable),
            ("125.50", 30, variable),
            ("100", 365, changed_endpoint),
        ]

        result = subprocess.run(
            [
                "cargo", "run", "--offline", "--quiet",
                "--manifest-path",
                "rust/quant_core/Cargo.toml",
                "--example", "path_parity",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )

        lines = result.stdout.strip().splitlines()
        self.assertEqual(len(lines), len(cases))

        for (amount, days, rates), line in zip(cases, lines):
            with self.subTest(amount=amount, days=days, rates=rates):
                python_value = discount_coupon_on_path(
                    amount, days, rates
                )
                rust_value = Decimal(line)

                self.assertTrue(rust_value.is_finite())
                self.assertLessEqual(
                    abs(python_value - rust_value),
                    TOLERANCE,
                )


if __name__ == "__main__":
    unittest.main()
