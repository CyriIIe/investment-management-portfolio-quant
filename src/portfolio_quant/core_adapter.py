"""Read-only adapter for Investment Management CORE portfolio exports."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json


@dataclass(frozen=True)
class Position:
    isin: str
    security_code: str | None
    market_section: str
    currency: str
    quantity: Decimal
    market_value_ex_accrued: Decimal
    accrued_interest: Decimal
    source_observation_id: int


@dataclass(frozen=True)
class PortfolioSnapshot:
    as_of_date: date
    source_hash: str
    positions: tuple[Position, ...]


def _decimal(value, field: str) -> Decimal:
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError(f"{field}: expected a decimal string")

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: invalid decimal") from exc

    if not result.is_finite():
        raise ValueError(f"{field}: non-finite decimal")

    return result


def parse_core_positions(payload: dict) -> PortfolioSnapshot:
    """Validate the CORE portfolio.positions JSON envelope.

    No database connection, network request or file write is performed.
    """
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")

    if payload.get("schema_version") != "1":
        raise ValueError("Unsupported CORE schema version")

    if payload.get("command") != "portfolio.positions":
        raise ValueError("Expected portfolio.positions export")

    generated = payload.get("generated_at_utc")
    if not isinstance(generated, str):
        raise ValueError("Missing export generation timestamp")

    try:
        timestamp = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid generation timestamp") from exc

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Generation timestamp must include timezone")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Missing portfolio data")

    try:
        as_of_date = date.fromisoformat(data["as_of_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid portfolio date") from exc

    raw_positions = data.get("positions")
    if not isinstance(raw_positions, list):
        raise ValueError("Positions must be an array")

    if not raw_positions:
        raise ValueError("Empty portfolio: verify the CORE export")

    positions = []
    identities = set()

    for index, item in enumerate(raw_positions):
        if not isinstance(item, dict):
            raise ValueError(f"Position {index}: expected an object")

        isin = item.get("isin")
        code = item.get("security_code")
        section = item.get("market_section")
        currency = item.get("currency_code")
        source_id = item.get("source_observation_id")

        if not isinstance(isin, str) or len(isin) != 12:
            raise ValueError(f"Position {index}: invalid ISIN")

        if code is not None and not isinstance(code, str):
            raise ValueError(f"Position {index}: invalid security code")
        if isinstance(code, str) and not code.strip():
            code = None

        if not isinstance(section, str) or not section.strip():
            raise ValueError(f"Position {index}: missing market section")

        if not isinstance(currency, str) or len(currency) != 3:
            raise ValueError(f"Position {index}: invalid currency")

        if type(source_id) is not int or source_id <= 0:
            raise ValueError(f"Position {index}: missing source observation ID")

        identity = (isin, code, section)
        if identity in identities:
            raise ValueError(f"Position {index}: duplicate position")
        identities.add(identity)

        quantity = _decimal(item.get("quantity_decimal"), "quantity")
        value = _decimal(
            item.get("market_value_ex_accrued_decimal"),
            "market value",
        )
        accrued = _decimal(
            item.get("accrued_interest_decimal"),
            "accrued interest",
        )

        if quantity < 0 or value < 0 or accrued < 0:
            raise ValueError(f"Position {index}: negative quantity or amount")

        if quantity == 0:
            continue

        positions.append(
            Position(
                isin=isin,
                security_code=code,
                market_section=section,
                currency=currency,
                quantity=quantity,
                market_value_ex_accrued=value,
                accrued_interest=accrued,
                source_observation_id=source_id,
            )
        )

    if not positions:
        raise ValueError("No positive positions in the snapshot")

    # Hash portfolio data, not the time at which it was exported.
    canonical = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    source_hash = sha256(canonical.encode("utf-8")).hexdigest()

    return PortfolioSnapshot(
        as_of_date=as_of_date,
        source_hash=source_hash,
        positions=tuple(positions),
    )
