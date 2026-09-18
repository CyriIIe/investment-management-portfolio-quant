"""Experimental rate-path scenarios for validated, known CORE coupons.

No principal, unknown coupon amounts, currency conversion, or full
portfolio valuation is included.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from portfolio_quant.cashflow_adapter import CashflowRun
from portfolio_quant.path_bridge import (
    MAX_CALCULATIONS,
    MAX_COUPONS,
    MAX_PATHS,
    discount_paths_rust,
)
from portfolio_quant.rate_paths import RatePathSimulation


@dataclass(frozen=True)
class KnownCouponPath:
    path_index: int
    present_value_by_currency: dict[str, Decimal]


@dataclass(frozen=True)
class KnownCouponPathResults:
    portfolio_date: str
    cashflow_run_id: int
    event_count: int
    path_count: int
    seed: int
    coupon_coverage_pct: Decimal
    unknown_schedule_count: int
    paths: tuple[KnownCouponPath, ...]
    includes_principal: bool = False
    complete_portfolio_valuation: bool = False
    calibrated_to_market: bool = False
    portfolio_risk_measure: bool = False


def calculate_known_coupon_paths(
    run: CashflowRun,
    simulation: RatePathSimulation,
) -> KnownCouponPathResults:
    """Discount validated contractual coupons over fictional rate paths.

    Coupons are grouped by currency; monetary units are never combined.
    Results are partial known-coupon values, not complete bond prices.
    """
    if not isinstance(run, CashflowRun):
        raise ValueError("Expected a validated CashflowRun")

    if not isinstance(simulation, RatePathSimulation):
        raise ValueError("Expected a RatePathSimulation")

    if simulation.calibrated_to_market or simulation.portfolio_risk_measure:
        raise ValueError("Only explicitly experimental paths are supported")

    if simulation.months != 12:
        raise ValueError("Rust path kernel requires 12 monthly intervals")

    if not 1 <= run.horizon_days <= 365:
        raise ValueError("Rust path kernel supports at most 365 days")

    paths = simulation.paths

    if not paths or len(paths) > MAX_PATHS:
        raise ValueError("Unsupported number of paths")

    if len(run.events) > MAX_COUPONS:
        raise ValueError("Too many coupons for one Rust batch")

    horizon_end = run.portfolio_date + timedelta(days=run.horizon_days)
    by_currency: dict[str, list[tuple[Decimal, int]]] = {}

    for index, event in enumerate(run.events):
        if event.event_type != "COUPON":
            raise ValueError(
                f"Event {index}: only coupons are supported"
            )

        if event.certainty != "CONTRACTUAL":
            raise ValueError(
                f"Event {index}: only contractual coupons are supported"
            )

        if not run.portfolio_date < event.event_date <= horizon_end:
            raise ValueError(
                f"Event {index}: outside the cashflow horizon"
            )

        days = (event.event_date - run.portfolio_date).days

        if days > 365:
            raise ValueError(
                f"Event {index}: outside the Rust kernel horizon"
            )

        by_currency.setdefault(event.currency, []).append(
            (event.gross_amount, days)
        )

    if not by_currency:
        raise ValueError("No known contractual coupons to simulate")

    # Validate every batch size before launching any Rust process.
    for currency_coupons in by_currency.values():
        if (
            len(currency_coupons) > MAX_COUPONS
            or len(currency_coupons) * len(paths) > MAX_CALCULATIONS
        ):
            raise ValueError("Path batch exceeds Rust limits")

    totals_by_path: list[dict[str, Decimal]] = [
        {} for _ in paths
    ]

    for currency, coupons in sorted(by_currency.items()):
        totals = discount_paths_rust(coupons, paths)

        if len(totals) != len(paths):
            raise ValueError("Incomplete Rust path result")

        for index, value in enumerate(totals):
            totals_by_path[index][currency] = value

    return KnownCouponPathResults(
        portfolio_date=run.portfolio_date.isoformat(),
        cashflow_run_id=run.run_id,
        event_count=len(run.events),
        path_count=len(paths),
        seed=simulation.seed,
        coupon_coverage_pct=run.coupon_coverage_pct,
        unknown_schedule_count=run.unknown_schedule_count,
        paths=tuple(
            KnownCouponPath(
                path_index=index,
                present_value_by_currency=totals,
            )
            for index, totals in enumerate(totals_by_path)
        ),
    )
