"""Illustrative present value of known contractual coupons only."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from portfolio_quant.cashflow_adapter import CashflowRun


@dataclass(frozen=True)
class PartialCouponValuation:
    portfolio_date: str
    cashflow_run_id: int
    annual_discount_rate: Decimal
    present_value_by_currency: dict[str, Decimal]
    event_count: int
    coupon_coverage_pct: Decimal
    unknown_schedule_count: int
    includes_principal: bool = False
    complete_portfolio_valuation: bool = False


def _rate(value) -> Decimal:
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError("Discount rate must be a decimal string or Decimal")
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid discount rate") from exc
    if not rate.is_finite() or not Decimal("0") <= rate <= Decimal("1"):
        raise ValueError("Discount rate must be between 0 and 1")
    return rate


def present_value_of_known_coupons(
    run: CashflowRun,
    *,
    annual_discount_rate,
) -> PartialCouponValuation:
    """Discount validated coupons using an illustrative continuous rate.

    This is NOT a bond price, total-return forecast or full portfolio value.
    """
    rate = _rate(annual_discount_rate)
    totals: dict[str, Decimal] = {}

    horizon_end = run.portfolio_date + timedelta(days=run.horizon_days)

    for event in run.events:
        if event.event_type != "COUPON":
            raise ValueError("This calculation accepts coupon events only")
        if event.certainty != "CONTRACTUAL":
            raise ValueError("This calculation accepts contractual events only")
        if not run.portfolio_date < event.event_date <= horizon_end:
            raise ValueError("Event outside the future cashflow horizon")

        days = (event.event_date - run.portfolio_date).days
        years = Decimal(days) / Decimal("365")
        discount_factor = (-rate * years).exp()
        value = event.gross_amount * discount_factor

        totals[event.currency] = totals.get(
            event.currency, Decimal("0")
        ) + value

    return PartialCouponValuation(
        portfolio_date=run.portfolio_date.isoformat(),
        cashflow_run_id=run.run_id,
        annual_discount_rate=rate,
        present_value_by_currency=totals,
        event_count=len(run.events),
        coupon_coverage_pct=run.coupon_coverage_pct,
        unknown_schedule_count=run.unknown_schedule_count,
    )
