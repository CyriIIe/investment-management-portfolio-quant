"""End-to-end tests of the experimental Rust path batch CLI."""

import subprocess
import unittest
from decimal import Decimal
from pathlib import Path

from portfolio_quant.path_discounting import discount_coupon_on_path


ROOT = Path(__file__).resolve().parents[1]
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


def make_input(coupons=COUPONS, paths=PATHS):
    lines = [f"{len(coupons)},{len(paths)}"]

    for path in paths:
        lines.extend(path)

    for amount, days in coupons:
        lines.append(f"{amount},{days}")

    return "\n".join(lines) + "\n"


def run_rust(payload):
    return subprocess.run(
        [
            "cargo", "run", "--offline", "--quiet",
            "--manifest-path", "rust/quant_core/Cargo.toml",
            "--bin", "quant_paths",
        ],
        cwd=ROOT,
        input=payload,
        capture_output=True,
        text=True,
        timeout=120,
    )


class QuantPathsTests(unittest.TestCase):
    def test_batch_matches_python_reference(self):
        result = run_rust(make_input())

        self.assertEqual(result.returncode, 0, result.stderr)

        lines = result.stdout.strip().splitlines()
        self.assertEqual(len(lines), len(PATHS))

        for index, (path, line) in enumerate(zip(PATHS, lines)):
            with self.subTest(path=index):
                expected = sum(
                    (
                        discount_coupon_on_path(amount, days, path)
                        for amount, days in COUPONS
                    ),
                    Decimal("0"),
                )
                actual = Decimal(line)

                self.assertTrue(actual.is_finite())
                self.assertLessEqual(
                    abs(expected - actual),
                    TOLERANCE,
                )

    def test_invalid_batches_produce_no_partial_output(self):
        valid = make_input()
        cases = {
            "negative coupon": make_input(
                COUPONS + [("-1", 30)]
            ),
            "extra input": valid + "unexpected\n",
            "missing coupon": "\n".join(
                valid.splitlines()[:-1]
            ) + "\n",
            "unsupported batch size": "10000,10000\n",
        }

        for name, payload in cases.items():
            with self.subTest(case=name):
                result = run_rust(payload)

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
