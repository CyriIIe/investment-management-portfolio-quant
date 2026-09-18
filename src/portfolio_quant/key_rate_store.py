"""SQLite schema for Portfolio Quant's independent key-rate history.

Never opens or modifies the CORE database.
"""

import sqlite3


SCHEMA_VERSION = 1


def initialize_key_rate_store(connection: sqlite3.Connection) -> None:
    """Create tables in a caller-provided, Quant-owned SQLite database.

    Observations are append-only by identity: revisions with different
    values are retained rather than overwriting earlier observations.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("Expected an SQLite connection")

    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS key_rate_observations (
                id INTEGER PRIMARY KEY,
                effective_date TEXT NOT NULL,
                source_timestamp TEXT NOT NULL,
                rate_percent TEXT NOT NULL,
                rate_fraction TEXT NOT NULL,
                collected_at_utc TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_method TEXT NOT NULL,
                source_response_sha256 TEXT NOT NULL,
                UNIQUE (
                    effective_date,
                    source_timestamp,
                    rate_percent
                )
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_key_rate_observations_effective_date
            ON key_rate_observations (
                effective_date,
                collected_at_utc
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS key_rate_collection_runs (
                id INTEGER PRIMARY KEY,
                collected_at_utc TEXT NOT NULL,
                requested_from_date TEXT NOT NULL,
                requested_to_date TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_method TEXT NOT NULL,
                source_response_sha256 TEXT NOT NULL,
                observation_count INTEGER NOT NULL
                    CHECK (observation_count >= 0),
                inserted_count INTEGER NOT NULL
                    CHECK (inserted_count >= 0),
                CHECK (inserted_count <= observation_count)
            )
            """
        )
