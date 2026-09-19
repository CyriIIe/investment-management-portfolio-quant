"""Read-only allocation data for the local portfolio dashboard."""

from portfolio_quant.core_readonly import load_core_inputs
from portfolio_quant.portfolio_allocation import build_portfolio_allocation


def read_allocation() -> dict:
    """Return per-currency weights, without quantities or amounts."""
    allocation = build_portfolio_allocation(load_core_inputs().snapshot)

    return {
        "as_of_date": allocation.as_of_date.isoformat(),
        "currencies": [
            {
                "currency": group.currency,
                "weights_available": group.weights_available,
                "assets": [
                    {
                        "isin": asset.isin,
                        "security_code": asset.security_code,
                        "market_section": asset.market_section,
                        "weight_pct": (
                            str(asset.weight_pct)
                            if asset.weight_pct is not None else None
                        ),
                    }
                    for asset in group.assets
                ],
            }
            for group in allocation.currencies
        ],
        "includes_cash": allocation.includes_cash,
        "includes_accrued_interest": allocation.includes_accrued_interest,
        "portfolio_risk_measure": allocation.portfolio_risk_measure,
        "performance_measure": allocation.performance_measure,
    }
