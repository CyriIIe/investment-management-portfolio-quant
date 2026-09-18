"""Tests for Portfolio Quant's independent key-rate SQLite schema."""

import sqlite3
import unittest

from portfolio_quant.key_rate_store import initialize_key_rate_store


class KeyRateStoreTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        initialize_key_rate_store(self.connection)

    def tearDown(self):
        self.connection.close()

    def insert_observation(self, *, rate="16.50", collected="2026-09-18T12:00:00+00:00"):
        self.connection.execute(
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
                "2026-09-18",
                "2026-09-18T00:00:00+03:00",
                rate,
                str(float(rate) / 100),
                collected,
                "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx",
                "KeyRateXML",
                "a" * 64,
            ),
        )

    def test_expected_tables_and_index_exist(self):
        objects = {
            (kind, name)
            for kind, name in self.connection.execute(
                """
                SELECT type, name FROM sqlite_master
                WHERE type IN ('table', 'index')
                """
            )
        }

        self.assertIn(("table", "key_rate_observations"), objects)
        self.assertIn(("table", "key_rate_collection_runs"), objects)
        self.assertIn(
            ("index", "idx_key_rate_observations_effective_date"),
            objects,
        )

    def test_initialization_is_idempotent(self):
        initialize_key_rate_store(self.connection)
        initialize_key_rate_store(self.connection)

        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM key_rate_observations"
            ).fetchone()[0],
            0,
        )

    def test_identical_observation_cannot_be_duplicated(self):
        self.insert_observation()

        with self.assertRaises(sqlite3.IntegrityError):
            self.insert_observation(
                collected="2026-09-19T12:00:00+00:00"
            )

        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM key_rate_observations"
            ).fetchone()[0],
            1,
        )

    def test_revised_rate_is_preserved_alongside_original(self):
        self.insert_observation(rate="16.50")
        self.insert_observation(
            rate="16.75",
            collected="2026-09-19T12:00:00+00:00",
        )

        rates = [
            row[0]
            for row in self.connection.execute(
                """
                SELECT rate_percent
                FROM key_rate_observations
                ORDER BY id
                """
            )
        ]

        self.assertEqual(rates, ["16.50", "16.75"])

    def test_invalid_collection_counters_are_rejected(self):
        statement = """
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
        """

        common = (
            "2026-09-18T12:00:00+00:00",
            "2026-09-01",
            "2026-09-18",
            "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx",
            "KeyRateXML",
            "a" * 64,
        )

        for observations, inserted in ((-1, 0), (2, -1), (2, 3)):
            with self.subTest(observations=observations, inserted=inserted):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        statement,
                        (*common, observations, inserted),
                    )


if __name__ == "__main__":
    unittest.main()
