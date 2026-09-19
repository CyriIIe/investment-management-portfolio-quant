"""Read-only individual cashflow metadata for the local dashboard."""

from portfolio_quant.asset_cashflows import associate_asset_cashflows
from portfolio_quant.core_readonly import load_core_inputs


def read_asset_cashflows() -> dict:
    """Expose known event metadata, never individual amounts or quantities."""
    inputs = load_core_inputs()
    association = associate_asset_cashflows(inputs)

    return {
        "as_of_date": inputs.snapshot.as_of_date.isoformat(),
        "assets": [
            {
                "isin": asset.isin,
                "security_code": asset.security_code,
                "market_section": asset.market_section,
                "currency": asset.currency,
                "known_event_count": asset.known_event_count,
                "next_known_event_date": (
                    asset.next_known_event_date.isoformat()
                    if asset.next_known_event_date is not None
                    else None
                ),
                "incomplete_reasons": list(asset.incomplete_reasons),
                "known_contractual_coupon_count": (
                    asset.known_contractual_coupon_count
                ),
                "next_known_coupon_date": (
                    asset.next_known_coupon_date.isoformat()
                    if asset.next_known_coupon_date is not None else None
                ),
                "days_until_next_known_coupon": (
                    asset.days_until_next_known_coupon
                ),
            }
            for asset in association.assets
        ],
        "unassigned_event_count": association.unassigned_event_count,
        "unassigned_schedule_count": association.unassigned_schedule_count,
        "complete_cashflows": False,
        "portfolio_risk_measure": False,
        "performance_measure": False,
    }
