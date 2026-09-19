"""Read-only observed CBR key-rate history for the local dashboard."""

from contextlib import closing

from portfolio_quant.web_overview import _open_readonly


def read_rates() -> dict:
    """Return recent observed rates; never forecasts or portfolio data."""
    with closing(_open_readonly("key_rates.sqlite3")) as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM key_rate_observations"
        ).fetchone()[0]

        rows = connection.execute(
            """
            SELECT effective_date, rate_percent, collected_at_utc
            FROM key_rate_observations
            ORDER BY effective_date DESC, id DESC
            LIMIT 50
            """
        ).fetchall()

    return {
        "total": total,
        "observations": [
            {
                "effective_date": row[0],
                "rate_percent": row[1],
                "collected_at_utc": row[2],
            }
            for row in rows
        ],
    }
