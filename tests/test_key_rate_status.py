"""Offline, read-only tests for the CBR key-rate status command."""

import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from portfolio_quant.key_rate_status import read_key_rate_status
from portfolio_quant.key_rate_store import initialize_key_rate_store


NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
COLLECTED = "2026-09-19T11:00:00+00:00"
EFFECTIVE = "2026-09-18"


class KeyRateStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.database = (
            Path(temporary.name) / "key_rates.sqlite3"
        )

        with sqlite3.connect(self.database) as connection:
            initialize_key_rate_store(connection)

    def populate(self, *, collected=COLLECTED, effective=EFFECTIVE):
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                INSERT INTO key_rate_collection_runs (
                    collected_at_utc,
                    requested_from_date,
                    requested_to_date,
                    source_url,
                    source_method,
                    source_response_sha256,
                    observation_count,
                    inserted_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    collected,
                    "2026-09-01",
                    "2026-09-19",
                    "test-source",
                    "test-method",
                    "test-hash",
                    1,
                    1,
                ),
            )
            connection.execute(
                """
                INSERT INTO key_rate_observations (
                    effective_date,
                    source_timestamp,
                    rate_percent,
                    rate_fraction,
                    collected_at_utc,
                    source_url,
                    source_method,
                    source_response_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    effective,
                    "2026-09-18T00:00:00+03:00",
                    "16.50",
                    "0.165",
                    collected,
                    "test-source",
                    "test-method",
                    "test-hash",
                ),
            )

    def counts(self):
        with sqlite3.connect(
            self.database.as_uri() + "?mode=ro",
            uri=True,
        ) as connection:
            return (
                connection.execute(
                    "SELECT COUNT(*) FROM key_rate_observations"
                ).fetchone()[0],
                connection.execute(
                    "SELECT COUNT(*) FROM key_rate_collection_runs"
                ).fetchone()[0],
            )

    def test_recent_data_returns_ok_without_writing(self):
        self.populate()
        before = self.counts()

        collected, effective, assessment = read_key_rate_status(
            database=self.database,
            now=NOW,
        )

        self.assertEqual(collected.isoformat(), COLLECTED)
        self.assertEqual(effective, date(2026, 9, 18))
        self.assertEqual(assessment.status, "OK")
        self.assertEqual(self.counts(), before)

    def test_missing_database_is_rejected_without_creation(self):
        self.database.unlink()

        with self.assertRaisesRegex(RuntimeError, "existing"):
            read_key_rate_status(database=self.database, now=NOW)

        self.assertFalse(self.database.exists())

    def test_empty_history_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            read_key_rate_status(database=self.database, now=NOW)

    def test_invalid_stored_date_is_rejected(self):
        self.populate(collected="invalid-timestamp")

        with self.assertRaisesRegex(RuntimeError, "Invalid stored"):
            read_key_rate_status(database=self.database, now=NOW)

    def test_old_observation_is_distinct_from_collection_delay(self):
        self.populate(effective="2026-09-01")

        _, _, assessment = read_key_rate_status(
            database=self.database,
            now=NOW,
        )

        self.assertEqual(assessment.status, "OBSERVATION_REVIEW")
        self.assertFalse(assessment.collection_overdue)
        self.assertTrue(assessment.observation_old)


if __name__ == "__main__":
    unittest.main()
