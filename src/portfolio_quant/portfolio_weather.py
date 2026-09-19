"""Offline, descriptive portfolio weather; no I/O or risk estimates."""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from portfolio_quant.core_readonly import CoreInputs


@dataclass(frozen=True)
class PortfolioWeather:
    portfolio_date: date
    cashflow_run_id: int
    position_count: int
    coupon_coverage_pct: Decimal
    unknown_schedule_count: int
    cashflow_horizon_days: int
    event_count: int
    events_by_type: tuple[tuple[str, int], ...]
    events_by_currency: tuple[tuple[str, int], ...]
    complete_cashflows: bool = False
    portfolio_risk_measure: bool = False


def build_portfolio_weather(inputs: CoreInputs) -> PortfolioWeather:
    """Summarize already-validated, matching CORE inputs without writes."""
    if not isinstance(inputs, CoreInputs):
        raise ValueError("Expected validated CORE inputs")

    snapshot = inputs.snapshot
    cashflows = inputs.cashflows

    if snapshot.as_of_date != cashflows.portfolio_date:
        raise ValueError("Portfolio and cashflow dates differ")

    return PortfolioWeather(
        portfolio_date=snapshot.as_of_date,
        cashflow_run_id=cashflows.run_id,
        position_count=len(snapshot.positions),
        coupon_coverage_pct=cashflows.coupon_coverage_pct,
        unknown_schedule_count=cashflows.unknown_schedule_count,
        cashflow_horizon_days=cashflows.horizon_days,
        event_count=len(cashflows.events),
        events_by_type=tuple(sorted(Counter(
            event.event_type for event in cashflows.events
        ).items())),
        events_by_currency=tuple(sorted(Counter(
            event.currency for event in cashflows.events
        ).items())),
    )
