"""Offline tests for the independent CBR refresh command."""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from unittest.mock import patch

from portfolio_quant import key_rate_refresh
from portfolio_quant.key_rate_store import initialize_key_rate_store


def soap():
    return (
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/'
        'soap/envelope/">'
        "<soap:Body><KeyRateXMLResponse><KeyRateXMLResult>"
        "<KeyRate>"
        "<KR><DT>2026-09-18T00:00:00+03:00</DT>"
        "<Rate>16.50</Rate></KR>"
        "</KeyRate>"
        "</KeyRateXMLResult></KeyRateXMLResponse></soap:Body>"
        "</soap:Envelope>"
    ).encode("utf-8")


class KeyRateRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.data_dir = Path(self.temporary.name) / "quant-data"
        self.data_dir.mkdir()
        self.database = self.data_dir / "key_rates.sqlite3"

        with sqlite3.connect(self.database) as connection:
            initialize_key_rate_store(connection)

        fixed_clock = patch.object(key_rate_refresh, "datetime")
        mocked_datetime = fixed_clock.start()
        self.addCleanup(fixed_clock.stop)
        mocked_datetime.now.return_value = datetime(
            2026, 9, 19, 12, 0,
            tzinfo=ZoneInfo("Europe/Moscow"),
        )

        patches = (
            patch.object(
                key_rate_refresh,
                "QUANT_DATA_DIR",
                self.data_dir,
            ),
            patch.object(
                key_rate_refresh,
                "QUANT_DATABASE",
                self.database,
            ),
            patch.object(
                key_rate_refresh,
                "fetch_key_rates",
                return_value=soap(),
            ),
        )

        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def counts(self):
        with sqlite3.connect(
            self.database.as_uri() + "?mode=ro",
            uri=True,
        ) as connection:
            observations = connection.execute(
                "SELECT COUNT(*) FROM key_rate_observations"
            ).fetchone()[0]

            collections = connection.execute(
                "SELECT COUNT(*) FROM key_rate_collection_runs"
            ).fetchone()[0]

        return observations, collections

    def test_default_mode_does_not_write(self):
        before = self.counts()

        key_rate_refresh.refresh_key_rates()

        self.assertEqual(self.counts(), before)

    def test_apply_records_observation_and_collection(self):
        key_rate_refresh.refresh_key_rates(apply=True)

        self.assertEqual(self.counts(), (1, 1))

    def test_repeated_apply_does_not_duplicate_observation(self):
        key_rate_refresh.refresh_key_rates(apply=True)
        key_rate_refresh.refresh_key_rates(apply=True)

        self.assertEqual(self.counts(), (1, 2))

    def test_missing_database_is_rejected(self):
        self.database.unlink()

        with self.assertRaisesRegex(RuntimeError, "not found or unsafe"):
            key_rate_refresh.refresh_key_rates(apply=True)

        self.assertFalse(self.database.exists())

    def test_invalid_apply_flag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            key_rate_refresh.refresh_key_rates(apply="yes")


if __name__ == "__main__":
    unittest.main()
