"""Read-only descriptive weather for the local dashboard."""

from portfolio_quant.core_readonly import load_core_inputs
from portfolio_quant.portfolio_weather import build_portfolio_weather


def read_weather() -> dict:
    """Return aggregate weather; no individual holdings or amounts."""
    weather = build_portfolio_weather(load_core_inputs())

    return {
        "portfolio_date": weather.portfolio_date.isoformat(),
        "cashflow_run_id": weather.cashflow_run_id,
        "position_count": weather.position_count,
        "coupon_coverage_pct": str(weather.coupon_coverage_pct),
        "unknown_schedule_count": weather.unknown_schedule_count,
        "cashflow_horizon_days": weather.cashflow_horizon_days,
        "event_count": weather.event_count,
        "events_by_type": dict(weather.events_by_type),
        "events_by_currency": dict(weather.events_by_currency),
        "complete_cashflows": weather.complete_cashflows,
        "portfolio_risk_measure": weather.portfolio_risk_measure,
    }
