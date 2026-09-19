"""Offline tests for the manual experimental cycle command."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from portfolio_quant import cycle_cli
from portfolio_quant.cycle_runner import CycleRunOutcome
from portfolio_quant.cycle_store import (
    initialize_cycle_store,
    save_experimental_cycle,
)


IDENTITY = "a" * 64


class CycleCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        root = Path(temporary.name)
        self.quant_dir = root / "quant-data"
        self.quant_dir.mkdir()
        self.cycles_db = self.quant_dir / "cycles.sqlite3"
        self.core_db = root / "core.sqlite3"

        with sqlite3.connect(self.core_db) as connection:
            connection.execute(
                """
                CREATE TABLE cashflow_forecast_runs (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    input_sha256 TEXT,
                    result_sha256 TEXT,
                    policy_sha256 TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO cashflow_forecast_runs
                VALUES (8, 'SUCCESS', ?, ?, ?)
                """,
                ("b" * 64, "c" * 64, "d" * 64),
            )

        self.inputs = SimpleNamespace(
            snapshot=SimpleNamespace(positions=(object(),)),
            cashflows=SimpleNamespace(
                run_id=8,
                unknown_schedule_count=25,
            ),
        )

        patches = (
            patch.object(cycle_cli, "QUANT_DATA_DIR", self.quant_dir),
            patch.object(cycle_cli, "CYCLE_DATABASE", self.cycles_db),
            patch.object(cycle_cli, "CORE_DATABASE", self.core_db),
            patch.object(
                cycle_cli,
                "load_core_inputs",
                return_value=self.inputs,
            ),
            patch.object(
                cycle_cli,
                "identify_experimental_cycle",
                return_value=IDENTITY,
            ),
            patch.object(cycle_cli, "run_experimental_cycle"),
        )

        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def initialize_cycles(self):
        with sqlite3.connect(self.cycles_db) as connection:
            initialize_cycle_store(connection)

    def run_cli(self, *, apply=False):
        with redirect_stdout(io.StringIO()):
            return cycle_cli.run_manual_cycle(apply=apply)

    def test_dry_run_does_not_create_missing_database(self):
        self.assertEqual(self.run_cli(), "DATABASE_MISSING")
        self.assertFalse(self.cycles_db.exists())
        cycle_cli.run_experimental_cycle.assert_not_called()

    def test_apply_refuses_missing_database(self):
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.run_cli(apply=True)

        self.assertFalse(self.cycles_db.exists())
        cycle_cli.run_experimental_cycle.assert_not_called()

    def test_dry_run_on_empty_store_does_not_calculate(self):
        self.initialize_cycles()

        self.assertEqual(self.run_cli(), "NOT_CALCULATED")
        cycle_cli.run_experimental_cycle.assert_not_called()

        with sqlite3.connect(
            self.cycles_db.as_uri() + "?mode=ro",
            uri=True,
        ) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM experimental_cycles"
            ).fetchone()[0]

        self.assertEqual(count, 0)

    def test_dry_run_detects_existing_cycle_without_calculation(self):
        self.initialize_cycles()

        with sqlite3.connect(self.cycles_db) as connection:
            save_experimental_cycle(
                connection,
                identity_sha256=IDENTITY,
                inputs={"model": "fictional-known-coupon-paths"},
                results={"event_count": 1},
            )

        self.assertEqual(self.run_cli(), "ALREADY_EXISTS")
        cycle_cli.run_experimental_cycle.assert_not_called()

    def test_apply_delegates_to_runner(self):
        self.initialize_cycles()
        cycle_cli.run_experimental_cycle.return_value = CycleRunOutcome(
            identity_sha256=IDENTITY,
            status="INSERTED",
        )

        self.assertEqual(self.run_cli(apply=True), "INSERTED")
        cycle_cli.run_experimental_cycle.assert_called_once()

    def test_unexpected_database_name_is_rejected(self):
        unexpected = self.quant_dir / "other.sqlite3"
        unexpected.touch()

        with patch.object(cycle_cli, "CYCLE_DATABASE", unexpected):
            with self.assertRaisesRegex(RuntimeError, "Unsafe"):
                self.run_cli()

        cycle_cli.load_core_inputs.assert_not_called()

    def test_symlinked_cycle_database_is_rejected(self):
        target = self.quant_dir / "target.sqlite3"
        target.touch()
        self.cycles_db.symlink_to(target)

        with self.assertRaisesRegex(RuntimeError, "Unsafe"):
            self.run_cli()

        cycle_cli.load_core_inputs.assert_not_called()

    def test_concurrent_apply_is_refused_before_core_read(self):
        from portfolio_quant.cycle_lock import exclusive_cycle_lock

        with exclusive_cycle_lock(self.quant_dir):
            with self.assertRaisesRegex(RuntimeError, "already running"):
                self.run_cli(apply=True)

        cycle_cli.load_core_inputs.assert_not_called()
        cycle_cli.run_experimental_cycle.assert_not_called()

    def test_dry_run_does_not_create_lock_file(self):
        self.assertEqual(self.run_cli(), "DATABASE_MISSING")
        self.assertFalse((self.quant_dir / "cycles.lock").exists())

    def test_invalid_apply_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.run_cli(apply="yes")

        cycle_cli.load_core_inputs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
