"""Offline tests for read-only CBR key-rate history."""

import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from portfolio_quant import web_overview
from portfolio_quant.web_rates import read_rates


class WebRatesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.data_dir = Path(temporary.name) / "quant-data"
        self.data_dir.mkdir()
        self.database = self.data_dir / "key_rates.sqlite3"

        directory_patch = patch.object(
            web_overview, "QUANT_DATA_DIR", self.data_dir
        )
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

    def create_observations(self, count):
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                CREATE TABLE key_rate_observations (
                    id INTEGER PRIMARY KEY,
                    effective_date TEXT NOT NULL,
                    rate_percent TEXT NOT NULL,
                    collected_at_utc TEXT NOT NULL
                )
                """
            )
            for number in range(count):
                effective_date = (
                    date(2026, 1, 1) + timedelta(days=number)
                ).isoformat()
                connection.execute(
                    """
                    INSERT INTO key_rate_observations
                    (effective_date, rate_percent, collected_at_utc)
                    VALUES (?, ?, ?)
                    """,
                    (
                        effective_date,
                        "16.00",
                        "2026-09-19T07:00:00+00:00",
                    ),
                )

    def test_empty_database(self):
        self.create_observations(0)
        self.assertEqual(read_rates(), {"total": 0, "observations": []})

    def test_latest_fifty_and_only_expected_fields(self):
        self.create_observations(51)

        result = read_rates()

        self.assertEqual(result["total"], 51)
        self.assertEqual(len(result["observations"]), 50)
        self.assertEqual(
            result["observations"][0]["effective_date"],
            "2026-02-20",
        )
        self.assertEqual(
            result["observations"][-1]["effective_date"],
            "2026-01-02",
        )
        self.assertEqual(
            set(result["observations"][0]),
            {"effective_date", "rate_percent", "collected_at_utc"},
        )
        self.assertEqual(result["observations"][0]["rate_percent"], "16.00")

    def test_missing_database_is_not_created(self):
        with self.assertRaisesRegex(RuntimeError, "Missing or unsafe"):
            read_rates()

        self.assertFalse(self.database.exists())

    def test_symlinked_database_is_rejected(self):
        self.create_observations(1)
        original = self.data_dir / "original.sqlite3"
        self.database.rename(original)
        self.database.symlink_to(original)

        with self.assertRaisesRegex(RuntimeError, "Missing or unsafe"):
            read_rates()

        self.assertTrue(original.is_file())


if __name__ == "__main__":
    unittest.main()
