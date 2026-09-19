"""Read archived pilot weather only; HTTP reads never collect or calculate."""

import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from portfolio_quant.experimental_registry import validate_registry
from portfolio_quant.experimental_weather import (
    MAX_COLLECTION_AGE_HOURS,
    MAX_OBSERVATION_AGE_DAYS,
    MarketObservation,
    weather_is_fresh,
)
from portfolio_quant.experimental_weather_store import latest_weather_result


WEATHER_DATABASE = Path.home() / "investment-management-portfolio-quant-data" / "pilot_weather.sqlite3"


def _unavailable(registration, reason: str) -> dict:
    return {
        "status": "UNAVAILABLE", "instrument_isin": registration.isin,
        "instrument_label": registration.label, "coupon_type": registration.coupon_type,
        "reason": reason,
    }


def read_experimental_weather(*, now=None) -> dict:
    """Expose only fresh archived results for exactly the registered pilots."""
    now = now or datetime.now(timezone.utc)
    results = []
    if WEATHER_DATABASE.is_symlink() or not WEATHER_DATABASE.is_file():
        return {
            "status": "EXPERIMENTAL", "modeled_instrument_count": 3,
            "portfolio_representative": False,
            "instruments": [_unavailable(item, "Résultat archivé non disponible") for item in validate_registry()],
        }
    with closing(sqlite3.connect(
        WEATHER_DATABASE.as_uri() + "?mode=ro", uri=True
    )) as connection:
        connection.execute("PRAGMA query_only = ON")
        for registration in validate_registry():
            result = latest_weather_result(connection, isin=registration.isin)
            if result is None:
                results.append(_unavailable(registration, "Résultat archivé non disponible"))
                continue
            try:
                observation = MarketObservation(
                    isin=result["instrument_isin"], board=result["board"],
                    trade_date=date.fromisoformat(result["market_observation_date"]),
                    collected_at_utc=datetime.fromisoformat(result["market_collected_at_utc"]),
                    source_url=result["source_url"], source_sha256=result["source_sha256"],
                    legal_close_price_pct=__import__("decimal").Decimal(result["dirty_price_rub_per_bond"]),
                    accrued_interest=None,
                )
                fresh = weather_is_fresh(observation, now=now)
            except (KeyError, TypeError, ValueError):
                fresh = False
            if not fresh:
                results.append(_unavailable(registration, "Observation absente, incohérente ou périmée"))
                continue
            results.append({**result, "instrument_label": registration.label, "coupon_type": registration.coupon_type, "status": "AVAILABLE"})
    return {
        "status": "EXPERIMENTAL", "modeled_instrument_count": 3,
        "portfolio_representative": False, "instruments": results,
        "max_observation_age_days": MAX_OBSERVATION_AGE_DAYS,
        "max_collection_age_hours": MAX_COLLECTION_AGE_HOURS,
    }
