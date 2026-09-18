"""Transactional ingestion into a caller-provided Portfolio Quant database.

No network access and no CORE database access.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import sqlite3

from portfolio_quant.cbr_key_rate import (
    SOURCE_METHOD,
    SOURCE_URL,
    parse_key_rate_xml,
)


@dataclass(frozen=True)
class KeyRateIngestResult:
    observation_count: int
    inserted_count: int
    duplicate_count: int
    revision_count: int
    response_sha256: str


def ingest_key_rates(
    connection: sqlite3.Connection,
    xml_content: bytes,
    *,
    requested_from_date: date,
    requested_to_date: date,
    collected_at_utc: datetime,
) -> KeyRateIngestResult:
    """Validate the complete response, then store it atomically.

    A revision is a newly inserted rate differing from a previously
    stored rate for the same effective date. Previous values are kept.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("Expected an SQLite connection")

    if not isinstance(xml_content, bytes) or not xml_content:
        raise ValueError("Expected non-empty XML bytes")

    if (
        type(requested_from_date) is not date
        or type(requested_to_date) is not date
        or requested_from_date > requested_to_date
    ):
        raise ValueError("Invalid requested date range")

    if (
        not isinstance(collected_at_utc, datetime)
        or collected_at_utc.tzinfo is None
        or collected_at_utc.utcoffset() is None
    ):
        raise ValueError("Collection timestamp must include a timezone")

    observations = parse_key_rate_xml(xml_content)

    if any(
        not requested_from_date <= observation.effective_date <= requested_to_date
        for observation in observations
    ):
        raise ValueError("Observation outside requested date range")

    collected = collected_at_utc.astimezone(timezone.utc).isoformat()
    response_hash = sha256(xml_content).hexdigest()

    inserted_count = 0
    revision_count = 0

    # Any database error rolls back observations AND the collection log.
    with connection:
        for observation in observations:
            effective_date = observation.effective_date.isoformat()

            previous_rates = [
                Decimal(row[0])
                for row in connection.execute(
                    """
                    SELECT rate_percent
                    FROM key_rate_observations
                    WHERE effective_date = ?
                    """,
                    (effective_date,),
                )
            ]

            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO key_rate_observations (
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
                    effective_date,
                    observation.source_timestamp.isoformat(),
                    str(observation.rate_percent),
                    str(observation.rate_fraction),
                    collected,
                    SOURCE_URL,
                    SOURCE_METHOD,
                    response_hash,
                ),
            )

            if cursor.rowcount == 1:
                inserted_count += 1

                if previous_rates and any(
                    rate != observation.rate_percent
                    for rate in previous_rates
                ):
                    revision_count += 1

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
                requested_from_date.isoformat(),
                requested_to_date.isoformat(),
                SOURCE_URL,
                SOURCE_METHOD,
                response_hash,
                len(observations),
                inserted_count,
            ),
        )

    return KeyRateIngestResult(
        observation_count=len(observations),
        inserted_count=inserted_count,
        duplicate_count=len(observations) - inserted_count,
        revision_count=revision_count,
        response_sha256=response_hash,
    )
