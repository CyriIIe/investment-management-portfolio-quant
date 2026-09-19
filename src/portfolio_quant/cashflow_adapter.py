"""Read-only validation of existing CORE cashflow exports."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class CashflowEvent:
    event_id: int
    event_date: date
    event_type: str
    currency: str
    gross_amount: Decimal
    certainty: str
    isin: str | None = None
    secid: str | None = None


@dataclass(frozen=True)
class UnknownSchedule:
    isin: str | None
    secid: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class CashflowRun:
    run_id: int
    portfolio_date: date
    snapshot_ids: frozenset[int]
    events: tuple[CashflowEvent, ...]
    coupon_coverage_pct: Decimal
    unknown_schedule_count: int
    horizon_days: int
    unknown_schedules: tuple[UnknownSchedule, ...] = ()

    @property
    def has_complete_cashflows(self) -> bool:
        # No assertion of completeness is possible from this adapter alone.
        return False


def _decimal(value, field):
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError(f"{field}: missing or invalid decimal")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: invalid decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{field}: non-finite decimal")
    return number


def _optional_identifier(value, field: str, length: int | None = None):
    """Preserve an optional source identity without guessing a missing one."""
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or (length is not None and len(value) != length)
    ):
        raise ValueError(f"Invalid {field}")
    return value


def parse_core_cashflows(payload, *, expected_snapshot_ids):
    """Validate a CORE cashflow.show export against confirmed positions."""
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    if payload.get("schema_version") != "1":
        raise ValueError("Unsupported CORE schema version")
    if payload.get("command") != "cashflow.show":
        raise ValueError("Expected cashflow.show export")

    data = payload.get("data")
    if not isinstance(data, dict) or data.get("status") != "SUCCESS":
        raise ValueError("Missing or unsuccessful cashflow run")

    run_id = data.get("run_id")
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("Invalid run ID")

    try:
        portfolio_date = date.fromisoformat(data["portfolio_snapshot_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid portfolio snapshot date") from exc

    if data.get("as_of_date") != portfolio_date.isoformat():
        raise ValueError("Cashflow and portfolio dates differ")

    ids = data.get("portfolio_snapshot_ids")
    expected = list(expected_snapshot_ids)

    if (
        not isinstance(ids, list)
        or not ids
        or any(type(value) is not int or value <= 0 for value in ids)
        or len(ids) != len(set(ids))
        or any(type(value) is not int or value <= 0 for value in expected)
        or not expected
        or len(expected) != len(set(expected))
        or set(ids) != set(expected)
    ):
        raise ValueError("Cashflow snapshot IDs do not match confirmed positions")

    details = data.get("details")
    if not isinstance(details, dict):
        raise ValueError("Missing cashflow details")

    coverage = details.get("coverage")
    if not isinstance(coverage, dict):
        raise ValueError("Missing coverage information")

    coupon_coverage = _decimal(
        coverage.get("coupon_schedule_coverage_pct"),
        "coupon coverage",
    )
    if not Decimal("0") <= coupon_coverage <= Decimal("100"):
        raise ValueError("Invalid coupon coverage percentage")

    unknown = details.get("unknown_cashflow_schedules")
    if not isinstance(unknown, list):
        raise ValueError("Missing unknown-schedules information")

    unknown_schedules = []
    for index, item in enumerate(unknown):
        if not isinstance(item, dict):
            raise ValueError(f"Unknown schedule {index}: expected an object")

        reasons = item.get("reasons", [])
        if (
            not isinstance(reasons, list)
            or any(
                not isinstance(reason, str) or not reason.strip()
                for reason in reasons
            )
        ):
            raise ValueError(f"Unknown schedule {index}: invalid reasons")

        unknown_schedules.append(
            UnknownSchedule(
                isin=_optional_identifier(item.get("isin"), "ISIN", 12),
                secid=_optional_identifier(item.get("secid"), "secid"),
                reasons=tuple(reasons),
            )
        )

    horizon = details.get("horizon_days")
    if type(horizon) is not int or horizon <= 0:
        raise ValueError("Invalid cashflow horizon")

    raw_events = data.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("Missing cashflow events")

    events = []
    event_ids = set()

    for index, item in enumerate(raw_events):
        if not isinstance(item, dict):
            raise ValueError(f"Event {index}: expected an object")

        event_id = item.get("id")
        if type(event_id) is not int or event_id <= 0 or event_id in event_ids:
            raise ValueError(f"Event {index}: invalid or duplicate ID")
        event_ids.add(event_id)

        try:
            event_date = date.fromisoformat(item["event_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Event {index}: invalid date") from exc

        event_type = item.get("event_type")
        if event_type not in {
            "COUPON",
            "AMORTIZATION",
            "MATURITY_REDEMPTION",
            "OFFER_REDEMPTION",
        }:
            raise ValueError(f"Event {index}: unsupported type")

        currency = item.get("currency_code")
        if not isinstance(currency, str) or len(currency) != 3:
            raise ValueError(f"Event {index}: invalid currency")

        certainty = item.get("certainty")
        if not isinstance(certainty, str) or not certainty:
            raise ValueError(f"Event {index}: missing certainty")

        gross = _decimal(item.get("gross_amount_decimal"), "gross amount")
        if gross < 0:
            raise ValueError(f"Event {index}: negative gross amount")

        events.append(
            CashflowEvent(
                event_id=event_id,
                event_date=event_date,
                event_type=event_type,
                currency=currency,
                gross_amount=gross,
                certainty=certainty,
            isin=_optional_identifier(item.get("isin"), "ISIN", 12),
            secid=_optional_identifier(item.get("secid"), "secid"),
            )
        )

    return CashflowRun(
        run_id=run_id,
        portfolio_date=portfolio_date,
        snapshot_ids=frozenset(ids),
        events=tuple(events),
        coupon_coverage_pct=coupon_coverage,
        unknown_schedule_count=len(unknown_schedules),
        horizon_days=horizon,
        unknown_schedules=tuple(unknown_schedules),
    )
