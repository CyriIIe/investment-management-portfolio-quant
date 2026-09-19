"""Descriptive per-unit valuation from validated CORE broker positions."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from portfolio_quant.core_adapter import Position


@dataclass(frozen=True)
class BrokerUnitPrice:
    as_of_date: date
    currency: str
    clean_price_per_unit: Decimal
    accrued_interest_per_unit: Decimal
    dirty_price_per_unit: Decimal


def calculate_broker_unit_price(
    position: Position,
    *,
    as_of_date: date,
) -> BrokerUnitPrice:
    """Divide existing broker values by quantity; no yield or MOEX fallback."""
    if not isinstance(position, Position):
        raise ValueError("Expected a validated Position")
    if not isinstance(as_of_date, date):
        raise ValueError("Invalid snapshot date")
    if position.quantity <= 0:
        raise ValueError("Quantity must be positive")

    clean = position.market_value_ex_accrued / position.quantity
    accrued = position.accrued_interest / position.quantity

    return BrokerUnitPrice(
        as_of_date=as_of_date,
        currency=position.currency,
        clean_price_per_unit=clean,
        accrued_interest_per_unit=accrued,
        dirty_price_per_unit=clean + accrued,
    )
