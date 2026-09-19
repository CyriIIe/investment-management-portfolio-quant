"""Read-only cycle metadata for the local dashboard."""

from contextlib import closing

from portfolio_quant.web_overview import _open_readonly


def read_cycles() -> dict:
    """Return recent cycle metadata, never inputs or simulation results."""
    with closing(_open_readonly("cycles.sqlite3")) as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM experimental_cycles"
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT
                substr(identity_sha256, 1, 16),
                created_at_utc,
                model_name,
                calibrated_to_market,
                complete_portfolio_valuation,
                portfolio_risk_measure
            FROM experimental_cycles
            ORDER BY created_at_utc DESC, identity_sha256 DESC
            LIMIT 20
            """
        ).fetchall()

    return {
        "total": total,
        "cycles": [
            {
                "identity_prefix": row[0],
                "created_at_utc": row[1],
                "model_name": row[2],
                "calibrated_to_market": bool(row[3]),
                "complete_portfolio_valuation": bool(row[4]),
                "portfolio_risk_measure": bool(row[5]),
            }
            for row in rows
        ],
    }
