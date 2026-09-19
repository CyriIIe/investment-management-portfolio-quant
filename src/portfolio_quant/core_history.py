"""Read historical CORE position snapshots without modifying CORE."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from portfolio_quant.core_adapter import parse_core_positions
from portfolio_quant.core_readonly import CORE_DATABASE


def load_historical_snapshot(
    as_of_date: date,
    *,
    database: Path = CORE_DATABASE,
):
    """Read canonical positions for one existing historical date."""
    if type(as_of_date) is not date:
        raise ValueError("Expected a portfolio date")

    database = Path(database)
    if (
        database.is_symlink()
        or database.parent.is_symlink()
        or not database.is_file()
    ):
        raise RuntimeError("CORE database is missing or has an unsafe path")

    with closing(sqlite3.connect(
        database.as_uri() + "?mode=ro",
        uri=True,
        timeout=2,
    )) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")

        rows = connection.execute(
            """
            SELECT s.isin, s.security_code, s.market_section,
                   s.currency_code, s.quantity_decimal,
                   s.market_value_ex_accrued_decimal,
                   s.accrued_interest_decimal,
                   s.source_observation_id
            FROM portfolio_security_snapshots s
            JOIN (
                SELECT MAX(id) AS id
                FROM portfolio_security_snapshots
                WHERE as_of_date = ?
                GROUP BY as_of_date, isin, security_code, market_section
            ) canonical ON canonical.id = s.id
            ORDER BY s.isin, s.security_code, s.market_section
            """,
            (as_of_date.isoformat(),),
        ).fetchall()

    if not rows:
        raise ValueError("No CORE snapshot for requested date")

    payload = {
        "schema_version": "1",
        "command": "portfolio.positions",
        "generated_at_utc": "2000-01-01T00:00:00+00:00",
        "data": {
            "as_of_date": as_of_date.isoformat(),
            "positions": [dict(row) for row in rows],
        },
    }

    return parse_core_positions(payload)


def load_previous_historical_snapshot(
    before_date: date,
    *,
    database: Path = CORE_DATABASE,
):
    """Find the preceding dated snapshot; never select a future date."""
    if type(before_date) is not date:
        raise ValueError("Expected a portfolio date")

    database = Path(database)
    if (
        database.is_symlink()
        or database.parent.is_symlink()
        or not database.is_file()
    ):
        raise RuntimeError("CORE database is missing or has an unsafe path")

    with closing(sqlite3.connect(
        database.as_uri() + "?mode=ro",
        uri=True,
        timeout=2,
    )) as connection:
        connection.execute("PRAGMA query_only = ON")
        row = connection.execute(
            """
            SELECT MAX(as_of_date)
            FROM portfolio_security_snapshots
            WHERE as_of_date < ?
            """,
            (before_date.isoformat(),),
        ).fetchone()

    if row is None or row[0] is None:
        raise ValueError("No preceding CORE snapshot")

    return load_historical_snapshot(
        date.fromisoformat(row[0]),
        database=database,
    )
