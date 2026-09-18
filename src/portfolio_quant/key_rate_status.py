"""Read-only status of Portfolio Quant's independent CBR key-rate data."""

from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3

from portfolio_quant.key_rate_freshness import assess_key_rate_freshness


DATA_DIR = Path.home() / "investment-management-portfolio-quant-data"
DATABASE = DATA_DIR / "key_rates.sqlite3"


def read_key_rate_status(*, database: Path = DATABASE, now=None):
    """Return a freshness assessment without modifying the database."""
    database = Path(database)

    if (
        database.is_symlink()
        or not database.is_file()
        or database.name != "key_rates.sqlite3"
    ):
        raise RuntimeError("Expected an existing Quant key-rate database")

    with sqlite3.connect(
        database.as_uri() + "?mode=ro",
        uri=True,
    ) as connection:
        collection = connection.execute(
            """
            SELECT collected_at_utc
            FROM key_rate_collection_runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        observation = connection.execute(
            """
            SELECT MAX(effective_date)
            FROM key_rate_observations
            """
        ).fetchone()

    if (
        collection is None
        or observation is None
        or observation[0] is None
    ):
        raise RuntimeError("Quant key-rate history is incomplete")

    try:
        collected_at = datetime.fromisoformat(collection[0])
        effective_date = date.fromisoformat(observation[0])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid stored key-rate date") from exc

    assessment = assess_key_rate_freshness(
        latest_collection_at_utc=collected_at,
        latest_effective_date=effective_date,
        now=datetime.now(timezone.utc) if now is None else now,
    )

    return collected_at, effective_date, assessment


def main():
    collected_at, effective_date, assessment = read_key_rate_status()

    print("===== PORTFOLIO QUANT — TAUX CBR =====")
    print("Dernière collecte :", collected_at.isoformat())
    print("Dernière observation :", effective_date.isoformat())
    print("Âge collecte (heures) :", round(assessment.collection_age_hours, 2))
    print("Âge observation (jours) :", assessment.observation_age_days)
    print("Statut :", assessment.status)
    print("Motif :", assessment.reason)


if __name__ == "__main__":
    main()
