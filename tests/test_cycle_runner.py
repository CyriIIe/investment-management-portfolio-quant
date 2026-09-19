"""Offline tests for deduplicated experimental cycle execution."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from portfolio_quant.cycle_runner import run_experimental_cycle
from portfolio_quant.cycle_store import initialize_cycle_store


IDENTITY = "a" * 64
HASHES = {
    "cashflow_input_sha256": "b" * 64,
    "cashflow_result_sha256": "c" * 64,
    "cashflow_policy_sha256": "d" * 64,
}


class CycleRunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.database = Path(temporary.name) / "cycles.sqlite3"
        self.connection = sqlite3.connect(self.database)
        self.addCleanup(self.connection.close)
        initialize_cycle_store(self.connection)

        self.core_inputs = object()
        self.prepared = SimpleNamespace(
            identity_sha256=IDENTITY,
            inputs={"model": "fictional-known-coupon-paths"},
            results={
                "event_count": 3,
                "calibrated_to_market": False,
                "complete_portfolio_valuation": False,
                "portfolio_risk_measure": False,
            },
        )

        identify_patch = patch(
            "portfolio_quant.cycle_runner.identify_experimental_cycle",
            return_value=IDENTITY,
        )
        prepare_patch = patch(
            "portfolio_quant.cycle_runner.prepare_experimental_cycle",
            return_value=self.prepared,
        )

        self.identify = identify_patch.start()
        self.prepare = prepare_patch.start()
        self.addCleanup(identify_patch.stop)
        self.addCleanup(prepare_patch.stop)

    def run_cycle(self):
        return run_experimental_cycle(
            self.connection,
            self.core_inputs,
            **HASHES,
        )

    def stored_count(self):
        return self.connection.execute(
            "SELECT COUNT(*) FROM experimental_cycles"
        ).fetchone()[0]

    def test_first_pass_inserts_result(self):
        outcome = self.run_cycle()

        self.assertEqual(outcome.status, "INSERTED")
        self.assertEqual(outcome.identity_sha256, IDENTITY)
        self.assertEqual(self.stored_count(), 1)
        self.identify.assert_called_once()
        self.prepare.assert_called_once()

    def test_second_pass_skips_calculation(self):
        self.assertEqual(self.run_cycle().status, "INSERTED")
        self.prepare.reset_mock()
        self.identify.reset_mock()

        outcome = self.run_cycle()

        self.assertEqual(outcome.status, "ALREADY_EXISTS")
        self.assertEqual(self.stored_count(), 1)
        self.identify.assert_called_once()
        self.prepare.assert_not_called()

    def test_changed_identity_creates_separate_cycle(self):
        first_identity = IDENTITY
        second_identity = "f" * 64

        self.assertEqual(self.run_cycle().status, "INSERTED")
        self.assertEqual(self.stored_count(), 1)

        self.identify.return_value = second_identity
        self.prepare.return_value = SimpleNamespace(
            identity_sha256=second_identity,
            inputs={"model": "fictional-known-coupon-paths", "version": 2},
            results={
                "event_count": 3,
                "calibrated_to_market": False,
                "complete_portfolio_valuation": False,
                "portfolio_risk_measure": False,
            },
        )

        outcome = self.run_cycle()

        self.assertEqual(outcome.status, "INSERTED")
        self.assertEqual(outcome.identity_sha256, second_identity)
        self.assertEqual(self.stored_count(), 2)
        self.assertEqual(self.prepare.call_count, 2)

        identities = {
            row[0]
            for row in self.connection.execute(
                "SELECT identity_sha256 FROM experimental_cycles"
            )
        }
        self.assertEqual(identities, {first_identity, second_identity})

    def test_identity_mismatch_is_not_stored(self):
        self.prepared.identity_sha256 = "e" * 64

        with self.assertRaisesRegex(RuntimeError, "identity changed"):
            self.run_cycle()

        self.assertEqual(self.stored_count(), 0)

    def test_calculation_failure_does_not_store_cycle(self):
        self.prepare.side_effect = RuntimeError("simulation failed")

        with self.assertRaisesRegex(RuntimeError, "simulation failed"):
            self.run_cycle()

        self.assertEqual(self.stored_count(), 0)


if __name__ == "__main__":
    unittest.main()
