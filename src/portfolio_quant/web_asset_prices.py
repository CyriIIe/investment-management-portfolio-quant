"""Read-only individual broker valuations for the local dashboard."""

from portfolio_quant.broker_unit_price import calculate_broker_unit_price
from portfolio_quant.core_readonly import load_core_inputs


def read_asset_prices() -> dict:
    """Expose dated per-unit broker values, never holdings or total amounts."""
    inputs = load_core_inputs()
    snapshot = inputs.snapshot

    assets = []
    for position in snapshot.positions:
        valuation = calculate_broker_unit_price(
            position,
            as_of_date=snapshot.as_of_date,
        )

        assets.append({
            "isin": position.isin,
            "security_code": position.security_code,
            "market_section": position.market_section,
            "currency": valuation.currency,
            "clean_price_per_unit": str(valuation.clean_price_per_unit),
            "accrued_interest_per_unit": str(
                valuation.accrued_interest_per_unit
            ),
            "dirty_price_per_unit": str(valuation.dirty_price_per_unit),
        })

    return {
        "as_of_date": snapshot.as_of_date.isoformat(),
        "assets": assets,
        "performance_measure": False,
        "portfolio_risk_measure": False,
    }
