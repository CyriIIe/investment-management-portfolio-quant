"""Private, append-only archive for experimental pilot weather results."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone


def initialize_weather_store(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS experimental_pilot_weather (
            identity_sha256 TEXT PRIMARY KEY,
            instrument_isin TEXT NOT NULL,
            market_observation_date TEXT NOT NULL,
            market_collected_at_utc TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """CREATE INDEX IF NOT EXISTS pilot_weather_latest
        ON experimental_pilot_weather (instrument_isin, created_at_utc DESC)"""
    )


def weather_identity(*, document_sha256: str, observation_sha256: str) -> str:
    if not all(isinstance(value, str) and len(value) == 64 for value in (
        document_sha256, observation_sha256
    )):
        raise ValueError("Weather inputs require SHA-256 fingerprints")
    return hashlib.sha256(
        f"pilot-weather-v1:{document_sha256}:{observation_sha256}".encode()
    ).hexdigest()


def save_weather_result(
    connection: sqlite3.Connection, *, identity_sha256: str, result: dict
) -> bool:
    """Archive a result once; an identical verified input is deduplicated."""
    if not isinstance(result, dict) or len(identity_sha256) != 64:
        raise ValueError("Invalid weather archive input")
    required = (
        "instrument_isin", "market_observation_date",
        "market_collected_at_utc",
    )
    if any(not isinstance(result.get(key), str) for key in required):
        raise ValueError("Incomplete weather result")
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with connection:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO experimental_pilot_weather
            (identity_sha256, instrument_isin, market_observation_date,
             market_collected_at_utc, created_at_utc, result_json)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                identity_sha256, result["instrument_isin"],
                result["market_observation_date"],
                result["market_collected_at_utc"],
                datetime.now(timezone.utc).isoformat(), encoded,
            ),
        )
    return cursor.rowcount == 1


def latest_weather_result(connection: sqlite3.Connection, *, isin: str) -> dict | None:
    row = connection.execute(
        """SELECT result_json FROM experimental_pilot_weather
        WHERE instrument_isin = ? ORDER BY created_at_utc DESC LIMIT 1""",
        (isin,),
    ).fetchone()
    return None if row is None else json.loads(row[0])
