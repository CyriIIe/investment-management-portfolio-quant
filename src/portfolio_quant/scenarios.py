"""Experimental flat-rate scenarios for known contractual coupons."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from portfolio_quant.cashflow_adapter import CashflowRun
from portfolio_quant.grid_bridge import MAX_GRID_SIZE, discount_grid_rust


@dataclass(frozen=True)
class CouponScenario:
    annual_rate: Decimal
    present_value_by_currency: dict[str, Decimal]


@dataclass(frozen=True)
class CouponScenarioGrid:
    portfolio_date: str
    cashflow_run_id: int
    event_count: int
    coupon_coverage_pct: Decimal
    unknown_schedule_count: int
    scenarios: tuple[CouponScenario, ...]
    includes_principal: bool = False
    complete_portfolio_valuation: bool = False


def _rate(value) -> Decimal:
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError("Rate must be a decimal string or Decimal")

    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid scenario rate") from exc

    if not rate.is_finite() or not Decimal("0") <= rate <= Decimal("1"):
        raise ValueError("Scenario rate must be between 0 and 1")

    return rate


def calculate_coupon_scenarios(
    run: CashflowRun,
    *,
    annual_rates,
) -> CouponScenarioGrid:
    """Discount known coupons under several illustrative flat rates.

    Rates are hypotheses, not observed market yields or forecasts.
    No principal, unknown schedules or future reinvestment is valued.
    """
    if not isinstance(run, CashflowRun):
        raise ValueError("Expected a validated CashflowRun")

    if not isinstance(annual_rates, (list, tuple)) or not annual_rates:
        raise ValueError("Provide a non-empty list of scenario rates")

    rates = tuple(_rate(value) for value in annual_rates)

    if len(set(rates)) != len(rates):
        raise ValueError("Duplicate scenario rates")

    if len(run.events) * len(rates) > MAX_GRID_SIZE:
        raise ValueError("Scenario grid exceeds Rust batch limit")

    horizon_end = run.portfolio_date + timedelta(days=run.horizon_days)
    coupons = []

    for index, event in enumerate(run.events):
        if event.event_type != "COUPON":
            raise ValueError(f"Event {index}: only coupons are supported")

        if event.certainty != "CONTRACTUAL":
            raise ValueError(f"Event {index}: only contractual coupons are supported")

        if not run.portfolio_date < event.event_date <= horizon_end:
            raise ValueError(f"Event {index}: outside the cashflow horizon")

        days = (event.event_date - run.portfolio_date).days

        # The current Rust kernel supports at most 365 days.
        if days > 365:
            raise ValueError("Rust kernel does not yet support horizons above 365 days")

        coupons.append((event.gross_amount, days, event.currency))

    # Group coupons by currency: never combine monetary units.
    by_currency: dict[str, list[tuple[Decimal, int]]] = {}

    for amount, days, currency in coupons:
        by_currency.setdefault(currency, []).append((amount, days))

    totals_by_rate: list[dict[str, Decimal]] = [
        {} for _ in rates
    ]

    # Compact Rust protocol: one process per currency, one total per rate.
    for currency, currency_coupons in sorted(by_currency.items()):
        currency_totals = discount_grid_rust(
            currency_coupons,
            rates,
        )

        if len(currency_totals) != len(rates):
            raise ValueError("Incomplete Rust scenario result")

        for index, value in enumerate(currency_totals):
            totals_by_rate[index][currency] = value

    scenarios = [
        CouponScenario(
            annual_rate=rate,
            present_value_by_currency=totals,
        )
        for rate, totals in zip(rates, totals_by_rate)
    ]

    return CouponScenarioGrid(
        portfolio_date=run.portfolio_date.isoformat(),
        cashflow_run_id=run.run_id,
        event_count=len(coupons),
        coupon_coverage_pct=run.coupon_coverage_pct,
        unknown_schedule_count=run.unknown_schedule_count,
        scenarios=tuple(scenarios),
    )
