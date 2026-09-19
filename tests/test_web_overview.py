"""Offline tests for read-only dashboard aggregates."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portfolio_quant import web_overview


class WebOverviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data_dir = Path(temporary.name) / "quant-data"
        self.data_dir.mkdir()

        directory_patch = patch.object(
            web_overview, "QUANT_DATA_DIR", self.data_dir
        )
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

    def create_databases(self):
        with sqlite3.connect(self.data_dir / "cycles.sqlite3") as db:
            db.execute(
                "CREATE TABLE experimental_cycles "
                "(identity_sha256 TEXT, created_at_utc TEXT)"
            )
            db.execute(
                "INSERT INTO experimental_cycles VALUES (?, ?)",
                ("a" * 64, "2026-09-19T07:00:00+00:00"),
            )

        with sqlite3.connect(self.data_dir / "key_rates.sqlite3") as db:
            db.execute(
                "CREATE TABLE key_rate_observations "
                "(effective_date TEXT)"
            )
            db.execute(
                "CREATE TABLE key_rate_collection_runs "
                "(id INTEGER, collected_at_utc TEXT)"
            )
            db.execute(
                "INSERT INTO key_rate_observations VALUES (?)",
                ("2026-09-18",),
            )
            db.execute(
                "INSERT INTO key_rate_collection_runs VALUES (?, ?)",
                (1, "2026-09-19T06:00:00+00:00"),
            )

    def test_returns_only_expected_aggregate_metadata(self):
        self.create_databases()

        result = web_overview.read_overview()

        self.assertEqual(result["cycles"]["count"], 1)
        self.assertEqual(
            result["cycles"]["latest_identity_prefix"], "a" * 16
        )
        self.assertEqual(
            result["cycles"]["latest_created_at_utc"],
            "2026-09-19T07:00:00+00:00",
        )
        self.assertEqual(result["key_rates"]["observation_count"], 1)
        self.assertEqual(
            result["key_rates"]["latest_effective_date"], "2026-09-18"
        )
        self.assertEqual(
            result["key_rates"]["latest_collected_at_utc"],
            "2026-09-19T06:00:00+00:00",
        )
        self.assertFalse(result["model"]["calibrated_to_market"])
        self.assertFalse(result["model"]["complete_portfolio_valuation"])
        self.assertFalse(result["model"]["portfolio_risk_measure"])
        self.assertEqual(
            set(result),
            {"cycles", "key_rates", "model"},
        )

    def test_missing_databases_are_not_created(self):
        with self.assertRaisesRegex(RuntimeError, "Missing or unsafe"):
            web_overview.read_overview()

        self.assertFalse((self.data_dir / "cycles.sqlite3").exists())
        self.assertFalse((self.data_dir / "key_rates.sqlite3").exists())

    def test_symlinked_database_is_rejected(self):
        self.create_databases()
        database = self.data_dir / "cycles.sqlite3"
        moved = self.data_dir / "original.sqlite3"
        database.rename(moved)
        database.symlink_to(moved)

        with self.assertRaisesRegex(RuntimeError, "Missing or unsafe"):
            web_overview.read_overview()

        self.assertTrue(moved.is_file())


if __name__ == "__main__":
    unittest.main()
