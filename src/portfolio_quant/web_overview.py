"""Read-only, aggregate data for the local Portfolio Quant dashboard."""

import sqlite3
from contextlib import closing
from pathlib import Path


QUANT_DATA_DIR = (
    Path.home() / "investment-management-portfolio-quant-data"
)


def _open_readonly(filename: str):
    """Open an existing Quant-owned database without creating it."""
    directory = QUANT_DATA_DIR
    database = directory / filename

    if (
        directory.is_symlink()
        or not directory.is_dir()
        or database.is_symlink()
        or not database.is_file()
        or database.resolve().parent != directory.resolve()
    ):
        raise RuntimeError(f"Missing or unsafe Quant database: {filename}")

    connection = sqlite3.connect(
        database.as_uri() + "?mode=ro",
        uri=True,
        timeout=2,
    )
    connection.execute("PRAGMA query_only = ON")
    return connection


def read_overview() -> dict:
    """Return aggregate metadata only; never return holdings or cashflows."""
    with closing(_open_readonly("cycles.sqlite3")) as connection:
        cycle_count = connection.execute(
            "SELECT COUNT(*) FROM experimental_cycles"
        ).fetchone()[0]

        latest_cycle = connection.execute(
            """
            SELECT created_at_utc, substr(identity_sha256, 1, 16)
            FROM experimental_cycles
            ORDER BY created_at_utc DESC, identity_sha256 DESC
            LIMIT 1
            """
        ).fetchone()

    with closing(_open_readonly("key_rates.sqlite3")) as connection:
        observation_count = connection.execute(
            "SELECT COUNT(*) FROM key_rate_observations"
        ).fetchone()[0]

        latest_observation = connection.execute(
            """
            SELECT MAX(effective_date)
            FROM key_rate_observations
            """
        ).fetchone()[0]

        latest_collection = connection.execute(
            """
            SELECT collected_at_utc
            FROM key_rate_collection_runs
            ORDER BY collected_at_utc DESC, id DESC
            LIMIT 1
            """
        ).fetchone()

    return {
        "cycles": {
            "count": cycle_count,
            "latest_created_at_utc": (
                latest_cycle[0] if latest_cycle else None
            ),
            "latest_identity_prefix": (
                latest_cycle[1] if latest_cycle else None
            ),
        },
        "key_rates": {
            "observation_count": observation_count,
            "latest_effective_date": latest_observation,
            "latest_collected_at_utc": (
                latest_collection[0] if latest_collection else None
            ),
        },
        "model": {
            "name": "fictional-known-coupon-paths",
            "calibrated_to_market": False,
            "complete_portfolio_valuation": False,
            "portfolio_risk_measure": False,
        },
    }
