"""Offline tests for preparing an experimental Quant cycle."""

import tempfile
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from portfolio_quant.cashflow_adapter import CashflowRun
from portfolio_quant.core_adapter import PortfolioSnapshot
from portfolio_quant.core_readonly import CoreInputs
from portfolio_quant.experimental_cycle import prepare_experimental_cycle


HASHES = {
    "cashflow_input_sha256": "b" * 64,
    "cashflow_result_sha256": "c" * 64,
    "cashflow_policy_sha256": "d" * 64,
}


class ExperimentalCycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.binary = Path(temporary.name) / "quant_paths"
        self.binary.write_bytes(b"fictional-test-binary")

        self.inputs = CoreInputs(
            snapshot=PortfolioSnapshot(
                as_of_date=date(2026, 9, 10),
                source_hash="a" * 64,
                positions=(),
            ),
            cashflows=CashflowRun(
                run_id=8,
                portfolio_date=date(2026, 9, 10),
                snapshot_ids=frozenset({101}),
                events=(),
                coupon_coverage_pct=Decimal("91.67"),
                unknown_schedule_count=25,
                horizon_days=365,
            ),
        )

        self.simulation = SimpleNamespace(
            initial_rate=Decimal("0.10"),
            monthly_volatility=Decimal("0.005"),
            months=12,
            seed=42,
        )
        self.calculation = SimpleNamespace(
            event_count=79,
            path_count=10,
            coupon_coverage_pct=Decimal("91.67"),
            unknown_schedule_count=25,
            includes_principal=False,
            calibrated_to_market=False,
            complete_portfolio_valuation=False,
            portfolio_risk_measure=False,
            paths=(
                SimpleNamespace(
                    present_value_by_currency={"RUB": Decimal("123.45")}
                ),
            ),
        )

        binary_patch = patch(
            "portfolio_quant.experimental_cycle.PATHS_BINARY",
            self.binary,
        )
        paths_patch = patch(
            "portfolio_quant.experimental_cycle.generate_rate_paths",
            return_value=self.simulation,
        )
        calculation_patch = patch(
            "portfolio_quant.experimental_cycle.calculate_known_coupon_paths",
            return_value=self.calculation,
        )

        for item in (binary_patch, paths_patch, calculation_patch):
            item.start()
            self.addCleanup(item.stop)

    def prepare(self, **changes):
        arguments = {
            "core_inputs": self.inputs,
            "rust_binary": self.binary,
            **HASHES,
        }
        arguments.update(changes)
        return prepare_experimental_cycle(**arguments)

    def test_prepared_result_preserves_incomplete_scope(self):
        prepared = self.prepare()

        self.assertEqual(len(prepared.identity_sha256), 64)
        self.assertEqual(prepared.inputs["cashflow_run_id"], 8)
        self.assertEqual(prepared.results["event_count"], 79)
        self.assertEqual(prepared.results["unknown_schedule_count"], 25)
        self.assertEqual(
            prepared.results["path_values_by_currency"],
            [{"RUB": "123.45"}],
        )
        self.assertFalse(prepared.results["includes_principal"])
        self.assertFalse(prepared.results["calibrated_to_market"])
        self.assertFalse(prepared.results["complete_portfolio_valuation"])
        self.assertFalse(prepared.results["portfolio_risk_measure"])

    def test_same_inputs_produce_same_identity(self):
        self.assertEqual(
            self.prepare().identity_sha256,
            self.prepare().identity_sha256,
        )

    def test_changed_parameters_change_identity(self):
        original = self.prepare().identity_sha256

        self.assertNotEqual(
            original,
            self.prepare(seed=43).identity_sha256,
        )
        self.assertNotEqual(
            original,
            self.prepare(path_count=11).identity_sha256,
        )

    def test_changed_binary_changes_identity(self):
        original = self.prepare().identity_sha256
        self.binary.write_bytes(b"changed-fictional-test-binary")

        self.assertNotEqual(
            original,
            self.prepare().identity_sha256,
        )

    def test_mismatched_portfolio_dates_are_rejected(self):
        changed = replace(
            self.inputs,
            cashflows=replace(
                self.inputs.cashflows,
                portfolio_date=date(2026, 9, 11),
            ),
        )

        with self.assertRaisesRegex(ValueError, "dates differ"):
            self.prepare(core_inputs=changed)

    def test_unexpected_risk_claim_is_rejected(self):
        self.calculation.portfolio_risk_measure = True

        with self.assertRaisesRegex(ValueError, "unexpected scope"):
            self.prepare()

    def test_unexpected_binary_is_rejected(self):
        other = self.binary.parent / "other_binary"
        other.write_bytes(b"other")

        with self.assertRaisesRegex(ValueError, "existing quant_paths"):
            self.prepare(rust_binary=other)


if __name__ == "__main__":
    unittest.main()
