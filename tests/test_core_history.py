"""Offline tests for historical CORE snapshot reading."""

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from portfolio_quant.core_history import load_historical_snapshot


class CoreHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Path(temporary.name) / "core.sqlite3"

        with sqlite3.connect(self.database) as connection:
            connection.execute("""
                CREATE TABLE portfolio_security_snapshots (
                    id INTEGER PRIMARY KEY,
                    as_of_date TEXT,
                    isin TEXT,
                    security_code TEXT,
                    market_section TEXT,
                    currency_code TEXT,
                    quantity_decimal TEXT,
                    market_value_ex_accrued_decimal TEXT,
                    accrued_interest_decimal TEXT,
                    source_observation_id INTEGER
                )
            """)
            connection.executemany(
                """INSERT INTO portfolio_security_snapshots
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (1, "2026-09-09", "RU000A000001", "TEST",
                     "TQCB", "RUB", "3", "2800", "40", 101),
                    (2, "2026-09-10", "RU000A000001", "TEST",
                     "TQCB", "RUB", "3", "2850", "45", 102),
                    (3, "2026-09-10", "RU000A000001", "TEST",
                     "TQCB", "RUB", "4", "3800", "50", 103),
                ],
            )

    def test_latest_observation_per_position_is_selected(self):
        snapshot = load_historical_snapshot(
            date(2026, 9, 10), database=self.database
        )
        self.assertEqual(len(snapshot.positions), 1)
        self.assertEqual(snapshot.positions[0].source_observation_id, 103)
        self.assertEqual(str(snapshot.positions[0].quantity), "4")

    def test_previous_date_is_independent(self):
        snapshot = load_historical_snapshot(
            date(2026, 9, 9), database=self.database
        )
        self.assertEqual(snapshot.positions[0].source_observation_id, 101)

    def test_missing_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "No CORE snapshot"):
            load_historical_snapshot(
                date(2026, 9, 8), database=self.database
            )

    def test_missing_database_is_not_created(self):
        missing = self.database.parent / "absent.sqlite3"
        with self.assertRaises(RuntimeError):
            load_historical_snapshot(date(2026, 9, 10), database=missing)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
