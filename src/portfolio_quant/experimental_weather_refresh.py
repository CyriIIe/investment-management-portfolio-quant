"""Explicit MOEX refresh for the three experimental pilots; never an HTTP path."""

import hashlib
import json
import sqlite3
import urllib.request
import argparse
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from portfolio_quant.experimental_registry import validate_registry
from portfolio_quant.experimental_weather import MarketObservation, calculate_weather
from portfolio_quant.experimental_weather_store import (
    initialize_weather_store, save_weather_result, weather_identity,
)


RESEARCH = Path.home() / "investment-management-portfolio-quant-data" / "research"
WEATHER_DATABASE = Path.home() / "investment-management-portfolio-quant-data" / "pilot_weather.sqlite3"
ISS_BASE = "https://iss.moex.com/iss/engines/stock/markets/bonds/boards"
PILOT_DOCUMENTS = {
    "ofz": ("ofz_26252_2026-09-10.json", "TQOB"),
    "gtlk": ("gtlk_002p_13_2026-09-10.json", "TQCB"),
    "sber_d10": ("sber_d10_2026-09-10.json", "TQCB"),
}


def _rows(payload: dict, block: str) -> list[dict]:
    table = payload.get(block)
    if not isinstance(table, dict) or not isinstance(table.get("columns"), list) or not isinstance(table.get("data"), list):
        raise ValueError("Incomplete MOEX response")
    return [dict(zip(table["columns"], row, strict=True)) for row in table["data"]]


def fetch_market_payload(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError("MOEX request failed")
        return response.read()


def parse_market_observation(*, raw: bytes, isin: str, board: str, collected_at_utc: datetime) -> MarketObservation:
    payload = json.loads(raw)
    rows = _rows(payload, "marketdata")
    if len(rows) != 1:
        raise ValueError("Ambiguous MOEX market observation")
    row = rows[0]
    if row.get("SECID") != isin or row.get("BOARDID") not in {None, board}:
        raise ValueError("MOEX instrument or board mismatch")
    trade_value = row.get("LASTDATE") or row.get("TRADEDATE")
    close = row.get("LEGALCLOSEPRICE")
    if not isinstance(trade_value, str) or close is None:
        raise ValueError("MOEX close or trade date unavailable")
    return MarketObservation(
        isin=isin, board=board, trade_date=date.fromisoformat(trade_value[:10]),
        collected_at_utc=collected_at_utc, source_url="",  # set by caller
        source_sha256=hashlib.sha256(raw).hexdigest(),
        legal_close_price_pct=Decimal(str(close)),
        accrued_interest=(None if row.get("ACCINT") is None else Decimal(str(row["ACCINT"]))),
    )


def refresh_pilot_weather(*, fetch=fetch_market_payload, now=None) -> dict:
    """Fetch, verify and archive changed inputs.  This is an explicit action."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware current time required")
    if WEATHER_DATABASE.is_symlink() or WEATHER_DATABASE.parent.is_symlink():
        raise RuntimeError("Unsafe private weather database path")
    WEATHER_DATABASE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    outcomes = []
    with closing(sqlite3.connect(WEATHER_DATABASE)) as connection:
        initialize_weather_store(connection)
        for registration in validate_registry():
            filename, expected_board = PILOT_DOCUMENTS[registration.reader_name]
            source = RESEARCH / filename
            if source.is_symlink() or not source.is_file():
                raise RuntimeError("Missing private documented source")
            raw_document = source.read_bytes()
            document = json.loads(raw_document, parse_float=Decimal)
            board = document["instrument"]["primary_board"]
            if board != expected_board:
                raise ValueError("Documentary board does not match pilot")
            url = f"{ISS_BASE}/{board}/securities/{registration.isin}.json?iss.meta=off&iss.only=marketdata"
            raw_market = fetch(url)
            observation = parse_market_observation(
                raw=raw_market, isin=registration.isin, board=board,
                collected_at_utc=now,
            )
            observation = MarketObservation(**{**observation.__dict__, "source_url": url})
            result = calculate_weather(document, observation)
            identity = weather_identity(
                document_sha256=hashlib.sha256(raw_document).hexdigest(),
                observation_sha256=observation.source_sha256,
            )
            outcomes.append({"isin": registration.isin, "status": "INSERTED" if save_weather_result(connection, identity_sha256=identity, result=result) else "UNCHANGED"})
    return {"status": "EXPERIMENTAL", "outcomes": outcomes}


def main() -> None:
    """Run only when explicitly invoked by an operator or future scheduler."""
    parser = argparse.ArgumentParser(
        description="Refresh archived experimental weather for three pilots"
    )
    parser.parse_args()
    result = refresh_pilot_weather()
    for item in result["outcomes"]:
        print(item["isin"], item["status"])


if __name__ == "__main__":
    main()
