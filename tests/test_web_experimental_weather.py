"""Offline reader tests: archived weather must never be refreshed by HTTP."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from portfolio_quant import web_experimental_weather as module
from portfolio_quant.experimental_weather_store import (
    initialize_weather_store, save_weather_result,
)


class WebExperimentalWeatherTests(unittest.TestCase):
    def test_missing_archive_returns_three_unavailable_instruments(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.sqlite3"
            with patch.object(module, "WEATHER_DATABASE", missing):
                result = module.read_experimental_weather()
        self.assertEqual(result["modeled_instrument_count"], 3)
        self.assertTrue(all(item["status"] == "UNAVAILABLE" for item in result["instruments"]))

    def test_stale_archive_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "weather.sqlite3"
            old = datetime.now(timezone.utc) - timedelta(hours=49)
            result = {
                "instrument_isin": "RU000A10D4Y2", "board": "TQOB",
                "market_observation_date": (old - timedelta(days=1)).date().isoformat(),
                "market_collected_at_utc": old.isoformat(),
                "source_url": "https://iss.moex.com/example", "source_sha256": "a" * 64,
                "dirty_price_rub_per_bond": "1000",
            }
            with closing(sqlite3.connect(database)) as connection:
                initialize_weather_store(connection)
                save_weather_result(connection, identity_sha256="b" * 64, result=result)
            with patch.object(module, "WEATHER_DATABASE", database):
                response = module.read_experimental_weather()
        self.assertEqual(response["instruments"][0]["status"], "UNAVAILABLE")
