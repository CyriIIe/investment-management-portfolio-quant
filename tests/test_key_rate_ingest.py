"""Tests for atomic ingestion into Portfolio Quant's own SQLite store."""

import sqlite3
import unittest
from datetime import date, datetime, timezone

from portfolio_quant.key_rate_ingest import ingest_key_rates
from portfolio_quant.key_rate_store import initialize_key_rate_store


FROM_DATE = date(2026, 9, 1)
TO_DATE = date(2026, 9, 18)
COLLECTED = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


def soap(rate="16.50"):
    return (
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/'
        'soap/envelope/">'
        "<soap:Body><KeyRateXMLResponse><KeyRateXMLResult>"
        "<KeyRate>"
        "<KR><DT>2026-09-17T00:00:00+03:00</DT>"
        f"<Rate>{rate}</Rate></KR>"
        "</KeyRate>"
        "</KeyRateXMLResult></KeyRateXMLResponse></soap:Body>"
        "</soap:Envelope>"
    ).encode("utf-8")


class KeyRateIngestTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        initialize_key_rate_store(self.connection)

    def tearDown(self):
        self.connection.close()

    def ingest(self, payload=None):
        return ingest_key_rates(
            self.connection,
            soap() if payload is None else payload,
            requested_from_date=FROM_DATE,
            requested_to_date=TO_DATE,
            collected_at_utc=COLLECTED,
        )

    def count(self, table):
        # Only test-controlled table names are supplied.
        return self.connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

    def test_first_collection_stores_observation_and_run(self):
        result = self.ingest()

        self.assertEqual(result.observation_count, 1)
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.duplicate_count, 0)
        self.assertEqual(result.revision_count, 0)
        self.assertEqual(self.count("key_rate_observations"), 1)
        self.assertEqual(self.count("key_rate_collection_runs"), 1)

        row = self.connection.execute(
            """
            SELECT effective_date, rate_percent, rate_fraction,
                   source_method, source_response_sha256
            FROM key_rate_observations
            """
        ).fetchone()

        self.assertEqual(row[0], "2026-09-17")
        self.assertEqual(row[1], "16.50")
        self.assertEqual(row[2], "0.165")
        self.assertEqual(row[3], "KeyRateXML")
        self.assertEqual(row[4], result.response_sha256)

    def test_repeat_collection_keeps_one_observation_and_logs_both(self):
        self.ingest()
        result = self.ingest()

        self.assertEqual(result.inserted_count, 0)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.revision_count, 0)
        self.assertEqual(self.count("key_rate_observations"), 1)
        self.assertEqual(self.count("key_rate_collection_runs"), 2)

    def test_revision_preserves_both_values(self):
        self.ingest(soap("16.50"))
        result = self.ingest(soap("16.75"))

        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.revision_count, 1)
        self.assertEqual(self.count("key_rate_collection_runs"), 2)

        values = [
            row[0]
            for row in self.connection.execute(
                """
                SELECT rate_percent
                FROM key_rate_observations
                ORDER BY id
                """
            )
        ]
        self.assertEqual(values, ["16.50", "16.75"])

    def test_failed_collection_log_rolls_back_observation(self):
        self.connection.execute(
            """
            CREATE TRIGGER reject_collection_log
            BEFORE INSERT ON key_rate_collection_runs
            BEGIN
                SELECT RAISE(ABORT, 'simulated journal failure');
            END
            """
        )
        self.connection.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            self.ingest()

        self.assertEqual(self.count("key_rate_observations"), 0)
        self.assertEqual(self.count("key_rate_collection_runs"), 0)


if __name__ == "__main__":
    unittest.main()
