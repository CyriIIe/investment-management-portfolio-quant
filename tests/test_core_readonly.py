"""Offline tests for matching existing CORE inputs without writes."""

import json
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from portfolio_quant.core_readonly import load_core_inputs


class CoreReadonlyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "core.sqlite3"

        with sqlite3.connect(self.database) as connection:
            connection.executescript("""
                CREATE TABLE portfolio_security_snapshots (
                    id INTEGER PRIMARY KEY,
                    as_of_date TEXT,
                    isin TEXT,
                    security_code TEXT,
                    market_section TEXT,
                    source_observation_id INTEGER,
                    quantity_decimal TEXT
                );
                CREATE TABLE cashflow_forecast_runs (
                    id INTEGER PRIMARY KEY,
                    status TEXT,
                    portfolio_snapshot_date TEXT,
                    portfolio_snapshot_ids_json TEXT
                );
            """)
            connection.execute(
                """
                INSERT INTO portfolio_security_snapshots
                VALUES (101, '2026-09-10', 'RU000A000000',
                        'TEST', 'TQCB', 501, '3')
                """
            )
            connection.execute(
                """
                INSERT INTO cashflow_forecast_runs
                VALUES (8, 'SUCCESS', '2026-09-10', '[101]')
                """
            )

        self.positions = {
            "as_of_date": "2026-09-10",
            "positions": [{
                "isin": "RU000A000000",
                "security_code": "TEST",
                "market_section": "TQCB",
                "currency_code": "RUB",
                "quantity_decimal": "3",
                "market_value_ex_accrued_decimal": "2850.00",
                "accrued_interest_decimal": "45.00",
                "source_observation_id": 501,
            }],
        }

        self.cashflows = {
            "run_id": 8,
            "status": "SUCCESS",
            "as_of_date": "2026-09-10",
            "portfolio_snapshot_date": "2026-09-10",
            "portfolio_snapshot_ids": [101],
            "details": {
                "coverage": {
                    "coupon_schedule_coverage_pct": "50.00",
                },
                "unknown_cashflow_schedules": [{}],
                "horizon_days": 365,
            },
            "events": [],
        }

        def connect_readonly(path):
            connection = sqlite3.connect(
                Path(path).as_uri() + "?mode=ro",
                uri=True,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return connection

        def envelope(command, data):
            return {
                "schema_version": "1",
                "command": command,
                "generated_at_utc": "2026-09-19T09:00:00+00:00",
                "data": data,
            }

        modules = {}
        for name in (
            "investment_manager",
            "investment_manager.database",
            "investment_manager.database.connection",
            "investment_manager.control",
            "investment_manager.control.reports",
            "investment_manager.cashflow",
            "investment_manager.cashflow.service",
        ):
            module = types.ModuleType(name)
            if name in (
                "investment_manager",
                "investment_manager.database",
                "investment_manager.control",
                "investment_manager.cashflow",
            ):
                module.__path__ = []
            modules[name] = module

        modules[
            "investment_manager.database.connection"
        ].connect_readonly = connect_readonly
        modules[
            "investment_manager.control.reports"
        ].envelope = envelope
        modules[
            "investment_manager.control.reports"
        ].portfolio_positions = lambda connection: self.positions
        modules[
            "investment_manager.cashflow.service"
        ].show = lambda connection, run_id: self.cashflows

        module_patch = patch.dict(sys.modules, modules)
        module_patch.start()
        self.addCleanup(module_patch.stop)

    def test_matching_existing_run(self):
        result = load_core_inputs(database=self.database)

        self.assertEqual(len(result.snapshot.positions), 1)
        self.assertEqual(result.cashflows.run_id, 8)
        self.assertEqual(result.cashflows.unknown_schedule_count, 1)
        self.assertFalse(result.cashflows.has_complete_cashflows)

    def test_source_observation_id_is_not_snapshot_row_id(self):
        result = load_core_inputs(database=self.database)

        self.assertEqual(
            result.snapshot.positions[0].source_observation_id,
            501,
        )
        self.assertEqual(result.cashflows.snapshot_ids, frozenset({101}))

    def test_mismatched_cashflow_ids_are_rejected(self):
        self.cashflows["portfolio_snapshot_ids"] = [999]

        with self.assertRaisesRegex(ValueError, "snapshot IDs"):
            load_core_inputs(database=self.database)

    def test_no_matching_run_is_rejected(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                UPDATE cashflow_forecast_runs
                SET portfolio_snapshot_ids_json = '[999]'
                """
            )

        with self.assertRaisesRegex(RuntimeError, "No existing"):
            load_core_inputs(database=self.database)

    def test_changed_position_quantity_is_rejected(self):
        self.positions["positions"][0]["quantity_decimal"] = "4"

        with self.assertRaisesRegex(RuntimeError, "does not match"):
            load_core_inputs(database=self.database)

    def test_missing_database_is_not_created(self):
        self.database.unlink()

        with self.assertRaisesRegex(RuntimeError, "missing"):
            load_core_inputs(database=self.database)

        self.assertFalse(self.database.exists())


if __name__ == "__main__":
    unittest.main()
