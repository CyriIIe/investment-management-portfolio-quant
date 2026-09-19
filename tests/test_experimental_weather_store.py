"""Offline archive and deduplication tests for pilot weather."""

import sqlite3
import unittest

from portfolio_quant.experimental_weather_store import (
    initialize_weather_store, latest_weather_result, save_weather_result,
    weather_identity,
)


class WeatherStoreTests(unittest.TestCase):
    def test_result_is_archived_once_per_verified_input(self):
        with sqlite3.connect(":memory:") as connection:
            initialize_weather_store(connection)
            identity = weather_identity(document_sha256="a" * 64, observation_sha256="b" * 64)
            result = {
                "instrument_isin": "RU000A10DCH3",
                "market_observation_date": "2026-09-19",
                "market_collected_at_utc": "2026-09-19T12:00:00+00:00",
            }
            self.assertTrue(save_weather_result(connection, identity_sha256=identity, result=result))
            self.assertFalse(save_weather_result(connection, identity_sha256=identity, result=result))
            self.assertEqual(latest_weather_result(connection, isin="RU000A10DCH3"), result)
