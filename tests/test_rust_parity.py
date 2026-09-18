"""Numerical parity between the Python reference and the Rust kernel."""

import subprocess
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from portfolio_quant.cashflow_adapter import CashflowEvent, CashflowRun
from portfolio_quant.discounting import present_value_of_known_coupons


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "rust/quant_core/Cargo.toml"

# Fictional cases, also defined in rust/quant_core/examples/parity.rs.
CASES = (
    (Decimal("100.0"), 365, Decimal("0.10")),
    (Decimal("125.50"), 30, Decimal("0.11")),
    (Decimal("1000000.0"), 200, Decimal("0.075")),
)

TOLERANCE = Decimal("0.00000001")


class RustParityTests(unittest.TestCase):
    def test_rust_matches_python_reference(self):
        result = subprocess.run(
            [
                "cargo",
                "run",
                "--offline",
                "--quiet",
                "--manifest-path",
                str(MANIFEST),
                "--example",
                "parity",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )

        lines = result.stdout.strip().splitlines()
        self.assertEqual(len(lines), len(CASES))

        for index, (line, expected_case) in enumerate(
            zip(lines, CASES), start=1
        ):
            with self.subTest(case=index):
                amount_text, days_text, rate_text, rust_text = line.split(",")

                amount = Decimal(amount_text)
                days = int(days_text)
                rate = Decimal(rate_text)
                rust_value = Decimal(rust_text)

                self.assertEqual(
                    (amount, days, rate),
                    expected_case,
                    "Rust and Python test inputs differ",
                )

                start = date(2026, 9, 10)

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
                            gross_amount=amount,
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

                difference = abs(python_value - rust_value)

                self.assertLessEqual(
                    difference,
                    TOLERANCE,
                    f"Python/Rust difference: {difference}",
                )


if __name__ == "__main__":
    unittest.main()
