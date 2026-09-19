"""Offline tests for read-only dashboard cycle metadata."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portfolio_quant import web_overview
from portfolio_quant.cycle_store import initialize_cycle_store
from portfolio_quant.web_cycles import read_cycles


class WebCyclesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.data_dir = Path(temporary.name) / "quant-data"
        self.data_dir.mkdir()
        self.database = self.data_dir / "cycles.sqlite3"

        directory_patch = patch.object(
            web_overview, "QUANT_DATA_DIR", self.data_dir
        )
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

    def create_cycles(self, count):
        with sqlite3.connect(self.database) as connection:
            initialize_cycle_store(connection)

            for number in range(count):
                connection.execute(
                    """
                    INSERT INTO experimental_cycles (
                        identity_sha256,
                        created_at_utc,
                        model_name,
                        inputs_json,
                        results_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        f"{number:064x}",
                        f"2026-09-19T{number:02d}:00:00+00:00",
                        "fictional-known-coupon-paths",
                        '{"private_input":"must-not-be-returned"}',
                        '{"private_result":"must-not-be-returned"}',
                    ),
                )

    def test_empty_database(self):
        self.create_cycles(0)

        self.assertEqual(read_cycles(), {"total": 0, "cycles": []})

    def test_returns_latest_twenty_without_private_payloads(self):
        self.create_cycles(21)

        result = read_cycles()

        self.assertEqual(result["total"], 21)
        self.assertEqual(len(result["cycles"]), 20)
        self.assertEqual(result["cycles"][0]["identity_prefix"], f"{20:064x}"[:16])
        self.assertEqual(
            result["cycles"][0]["created_at_utc"],
            "2026-09-19T20:00:00+00:00",
        )
        self.assertEqual(
            result["cycles"][-1]["created_at_utc"],
            "2026-09-19T01:00:00+00:00",
        )
        self.assertEqual(
            set(result["cycles"][0]),
            {
                "identity_prefix",
                "created_at_utc",
                "model_name",
                "calibrated_to_market",
                "complete_portfolio_valuation",
                "portfolio_risk_measure",
            },
        )
        self.assertNotIn("must-not-be-returned", str(result))
        self.assertFalse(result["cycles"][0]["calibrated_to_market"])
        self.assertFalse(result["cycles"][0]["complete_portfolio_valuation"])
        self.assertFalse(result["cycles"][0]["portfolio_risk_measure"])

    def test_missing_database_is_not_created(self):
        with self.assertRaisesRegex(RuntimeError, "Missing or unsafe"):
            read_cycles()

        self.assertFalse(self.database.exists())

    def test_symlinked_database_is_rejected(self):
        self.create_cycles(1)
        original = self.data_dir / "original.sqlite3"
        self.database.rename(original)
        self.database.symlink_to(original)

        with self.assertRaisesRegex(RuntimeError, "Missing or unsafe"):
            read_cycles()

        self.assertTrue(original.is_file())


if __name__ == "__main__":
    unittest.main()
