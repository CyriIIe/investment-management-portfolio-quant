"""Independent SQLite storage for experimental Portfolio Quant cycles."""

import json
import sqlite3
from datetime import datetime, timezone

from portfolio_quant.cycle_identity import _digest


def _json_object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name}: expected an object")

    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: invalid JSON data") from exc

    return encoded


def initialize_cycle_store(connection: sqlite3.Connection):
    """Create tables in a caller-supplied Quant-owned database."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS experimental_cycles (
            identity_sha256 TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            model_name TEXT NOT NULL
                CHECK (model_name = 'fictional-known-coupon-paths'),
            inputs_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            calibrated_to_market INTEGER NOT NULL DEFAULT 0
                CHECK (calibrated_to_market = 0),
            complete_portfolio_valuation INTEGER NOT NULL DEFAULT 0
                CHECK (complete_portfolio_valuation = 0),
            portfolio_risk_measure INTEGER NOT NULL DEFAULT 0
                CHECK (portfolio_risk_measure = 0)
        )
        """
    )


def save_experimental_cycle(
    connection: sqlite3.Connection,
    *,
    identity_sha256: str,
    inputs: dict,
    results: dict,
) -> bool:
    """Insert a new experimental cycle; never overwrite an existing one.

    Returns True when inserted, False when the identity already exists.
    The caller controls which Quant-owned database is opened.
    """
    identity = _digest(identity_sha256, "cycle identity")
    inputs_json = _json_object(inputs, "inputs")
    results_json = _json_object(results, "results")

    created_at = datetime.now(timezone.utc).isoformat()

    with connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO experimental_cycles (
                identity_sha256,
                created_at_utc,
                model_name,
                inputs_json,
                results_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                identity,
                created_at,
                "fictional-known-coupon-paths",
                inputs_json,
                results_json,
            ),
        )

        if cursor.rowcount == 0:
            stored = connection.execute(
                """
                SELECT inputs_json, results_json
                FROM experimental_cycles
                WHERE identity_sha256 = ?
                """,
                (identity,),
            ).fetchone()

            if (
                stored is None
                or stored[0] != inputs_json
                or stored[1] != results_json
            ):
                raise RuntimeError(
                    "Cycle identity already exists with different data"
                )

    return cursor.rowcount == 1
