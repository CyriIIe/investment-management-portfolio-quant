"""Pure, conditional weather calculations for the three registered pilots.

No network, CORE/LAB access, or writes occur in this module.  A caller must
provide a verified market observation; stale data is deliberately not turned
into a current valuation.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from portfolio_quant.deterministic_total_return import BondCase, calculate_total_return
from portfolio_quant.documented_bond_flows import parse_documented_bond_flows
from portfolio_quant.documented_reference_price import market_observation_reference_price


SCENARIO_YIELDS = ("0.10", "0.125", "0.15")
MAX_OBSERVATION_AGE_DAYS = 4
MAX_COLLECTION_AGE_HOURS = 48


@dataclass(frozen=True)
class MarketObservation:
    isin: str
    board: str
    trade_date: date
    collected_at_utc: datetime
    source_url: str
    source_sha256: str
    legal_close_price_pct: Decimal
    accrued_interest: Decimal | None


def rolling_year(value: date) -> date:
    """Return the same calendar day next year, with a safe leap-day rule."""
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def _require_observation(observation: MarketObservation, documented) -> None:
    if not isinstance(observation, MarketObservation):
        raise ValueError("Verified market observation required")
    if (
        observation.isin != documented.isin
        or observation.board != documented.primary_board
        or not observation.source_url.startswith("https://iss.moex.com/")
        or len(observation.source_sha256) != 64
        or observation.trade_date < documented.valuation_date
        or observation.trade_date >= documented.maturity_date
        or observation.collected_at_utc.tzinfo is None
        or observation.collected_at_utc.utcoffset() is None
    ):
        raise ValueError("Market observation is inconsistent or unverified")


def weather_is_fresh(observation: MarketObservation, *, now: datetime) -> bool:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware current time required")
    _require_observation(observation, type("Document", (), {
        "isin": observation.isin,
        "primary_board": observation.board,
        "valuation_date": date.min,
        "maturity_date": date.max,
    })())
    now_utc = now.astimezone(timezone.utc)
    collected = observation.collected_at_utc.astimezone(timezone.utc)
    if collected > now_utc:
        return False
    return (
        (now.date() - observation.trade_date).days <= MAX_OBSERVATION_AGE_DAYS
        and (now_utc - collected).total_seconds() <= MAX_COLLECTION_AGE_HOURS * 3600
    )


def calculate_weather(document: dict, observation: MarketObservation) -> dict:
    """Recalculate one conditional one-year result from a market observation."""
    documented = parse_documented_bond_flows(document)
    _require_observation(observation, documented)
    if not weather_is_fresh(observation, now=observation.collected_at_utc):
        raise ValueError("Market observation is stale")

    remaining = tuple(flow for flow in documented.flows if flow.payment_date > observation.trade_date)
    remaining_principal = sum(
        (flow.amount for flow in remaining if flow.kind == "PRINCIPAL"), Decimal("0")
    )
    if not remaining or remaining_principal <= 0:
        raise ValueError("No remaining contractual cashflows")

    price, price_basis = market_observation_reference_price(
        documented,
        close=observation.legal_close_price_pct,
        accrued_interest=observation.accrued_interest,
        nominal=remaining_principal,
    )
    horizon = rolling_year(observation.trade_date)
    if horizon >= documented.maturity_date:
        horizon = documented.maturity_date
    bond = BondCase(
        valuation_date=observation.trade_date,
        horizon_date=horizon,
        currency=documented.currency,
        dirty_price=price,
        remaining_principal=remaining_principal,
        flows=remaining,
        fixed_coupon_verified=documented.coupon_type != "DISCOUNT_NO_COUPON",
        complete_schedule_verified=True,
        primary_board_verified=True,
        zero_coupon_verified=documented.coupon_type == "DISCOUNT_NO_COUPON",
    )
    scenarios = calculate_total_return(bond, annual_market_yields=SCENARIO_YIELDS)
    return {
        "status": "EXPERIMENTAL",
        "instrument_isin": documented.isin,
        "valuation_date": observation.trade_date.isoformat(),
        "calculated_at_utc": observation.collected_at_utc.astimezone(timezone.utc).isoformat(),
        "horizon_date": horizon.isoformat(),
        "board": observation.board,
        "source_url": observation.source_url,
        "source_sha256": observation.source_sha256,
        "market_observation_date": observation.trade_date.isoformat(),
        "market_collected_at_utc": observation.collected_at_utc.astimezone(timezone.utc).isoformat(),
        "price_basis": price_basis,
        "dirty_price_rub_per_bond": str(price),
        "scenarios_are_conditional_not_forecasts": True,
        "historical_backtest_validated": False,
        "portfolio_representative": False,
        "scenarios": [
            {
                "hypothetical_annual_market_yield": str(item.annual_market_yield),
                "received_through_horizon_rub_per_bond": str(item.received_before_or_on_horizon),
                "theoretical_terminal_price_rub_per_bond": str(item.theoretical_terminal_price),
                "terminal_wealth_rub_per_bond": str(item.terminal_wealth),
                "gross_total_return_decimal": str(item.total_return),
            }
            for item in scenarios
        ],
    }
