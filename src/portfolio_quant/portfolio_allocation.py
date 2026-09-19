"""Descriptive portfolio allocation, calculated independently by currency."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from portfolio_quant.core_adapter import PortfolioSnapshot


@dataclass(frozen=True)
class AssetAllocation:
    isin: str
    security_code: str | None
    market_section: str
    weight_pct: Decimal | None


@dataclass(frozen=True)
class CurrencyAllocation:
    currency: str
    assets: tuple[AssetAllocation, ...]
    weights_available: bool


@dataclass(frozen=True)
class PortfolioAllocation:
    as_of_date: date
    currencies: tuple[CurrencyAllocation, ...]
    includes_cash: bool = False
    includes_accrued_interest: bool = True
    portfolio_risk_measure: bool = False
    performance_measure: bool = False


def build_portfolio_allocation(
    snapshot: PortfolioSnapshot,
) -> PortfolioAllocation:
    """Compute asset weights without combining different currencies."""
    if not isinstance(snapshot, PortfolioSnapshot):
        raise ValueError("Expected validated CORE snapshot")

    grouped = {}
    identities = set()

    for position in snapshot.positions:
        identity = (
            position.isin,
            position.security_code,
            position.market_section,
        )
        if identity in identities:
            raise ValueError("Duplicate asset identity")
        identities.add(identity)

        value = (
            position.market_value_ex_accrued
            + position.accrued_interest
        )
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid asset value")

        grouped.setdefault(position.currency, []).append(
            (position, value)
        )

    currencies = []
    for currency, entries in sorted(grouped.items()):
        total = sum(
            (value for _, value in entries),
            Decimal("0"),
        )
        available = total > 0

        assets = tuple(
            AssetAllocation(
                isin=position.isin,
                security_code=position.security_code,
                market_section=position.market_section,
                weight_pct=(
                    value * Decimal("100") / total
                    if available else None
                ),
            )
            for position, value in sorted(
                entries,
                key=lambda entry: (
                    entry[0].isin,
                    entry[0].security_code or "",
                    entry[0].market_section,
                ),
            )
        )
        currencies.append(
            CurrencyAllocation(
                currency=currency,
                assets=assets,
                weights_available=available,
            )
        )

    return PortfolioAllocation(
        as_of_date=snapshot.as_of_date,
        currencies=tuple(currencies),
    )
