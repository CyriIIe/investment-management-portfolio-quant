"""Controlled refresh of Portfolio Quant's independent CBR key-rate store.

Default: fetch and validate without writing.
--apply: ingest into the existing Quant-owned database.
Never opens the CORE database or creates a new database.
"""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from portfolio_quant.cbr_key_rate import parse_key_rate_xml
from portfolio_quant.cbr_key_rate_client import fetch_key_rates
from portfolio_quant.key_rate_ingest import ingest_key_rates


LOOKBACK_DAYS = 45
QUANT_DATA_DIR = (
    Path.home() / "investment-management-portfolio-quant-data"
)
QUANT_DATABASE = QUANT_DATA_DIR / "key_rates.sqlite3"


def refresh_key_rates(*, apply: bool = False) -> None:
    """Validate a recent CBR window; optionally ingest it."""
    if type(apply) is not bool:
        raise ValueError("apply must be a boolean")

    if (
        QUANT_DATA_DIR.is_symlink()
        or QUANT_DATABASE.is_symlink()
        or not QUANT_DATA_DIR.is_dir()
        or not QUANT_DATABASE.is_file()
        or QUANT_DATABASE.resolve().parent
           != QUANT_DATA_DIR.resolve()
    ):
        raise RuntimeError(
            "Existing independent Quant database not found or unsafe"
        )

    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    from_date = today - timedelta(days=LOOKBACK_DAYS)

    print("===== COLLECTE CBR =====")
    print("Période demandée :", from_date, "→", today)
    print("Mode :", "ENREGISTREMENT" if apply else "VERIFICATION")

    # Network fetch and complete validation happen before any DB write.
    content = fetch_key_rates(
        from_date=from_date,
        to_date=today,
    )
    observations = parse_key_rate_xml(content)

    print("Observations validées :", len(observations))
    print(
        "Période reçue :",
        observations[0].effective_date,
        "→",
        observations[-1].effective_date,
    )

    if not apply:
        print("Aucune écriture effectuée.")
        return

    # mode=rw opens the existing file; it cannot silently create another DB.
    with sqlite3.connect(
        QUANT_DATABASE.as_uri() + "?mode=rw",
        uri=True,
        timeout=15,
    ) as connection:
        result = ingest_key_rates(
            connection,
            content,
            requested_from_date=from_date,
            requested_to_date=today,
            collected_at_utc=datetime.now(timezone.utc),
        )

    print("Observations insérées :", result.inserted_count)
    print("Doublons :", result.duplicate_count)
    print("Révisions détectées :", result.revision_count)
    print("Empreinte source :", result.response_sha256[:16] + "…")
    print("Rafraîchissement : OK")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh independent Portfolio Quant CBR key rates"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Record observations in the existing Quant database",
    )
    args = parser.parse_args()
    refresh_key_rates(apply=args.apply)


if __name__ == "__main__":
    main()
