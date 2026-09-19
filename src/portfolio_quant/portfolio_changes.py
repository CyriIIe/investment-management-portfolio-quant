"""Offline comparison of validated portfolio snapshots; no I/O."""

from dataclasses import dataclass

from portfolio_quant.core_adapter import PortfolioSnapshot


@dataclass(frozen=True)
class PortfolioChanges:
    previous_date: str
    current_date: str
    previous_position_count: int
    current_position_count: int
    added_count: int
    removed_count: int
    quantity_changed_count: int
    value_changed_at_constant_quantity_count: int
    accrued_changed_at_constant_quantity_count: int
    source_only_changed_count: int
    unchanged_count: int
    portfolio_risk_measure: bool = False
    performance_measure: bool = False


def _positions_by_identity(snapshot: PortfolioSnapshot) -> dict:
    positions = {}
    for position in snapshot.positions:
        identity = (
            position.isin,
            position.security_code,
            position.market_section,
        )
        if identity in positions:
            raise ValueError("Duplicate position identity")
        positions[identity] = position
    return positions


def compare_portfolio_snapshots(
    previous: PortfolioSnapshot,
    current: PortfolioSnapshot,
) -> PortfolioChanges:
    """Compare observations without inferring trades or performance."""
    if not isinstance(previous, PortfolioSnapshot) or not isinstance(
        current, PortfolioSnapshot
    ):
        raise ValueError("Expected validated portfolio snapshots")

    if previous.as_of_date >= current.as_of_date:
        raise ValueError("Snapshots must be in chronological order")

    old = _positions_by_identity(previous)
    new = _positions_by_identity(current)

    shared = old.keys() & new.keys()
    quantity_changed = 0
    value_changed = 0
    accrued_changed = 0
    source_only_changed = 0
    unchanged = 0

    for identity in shared:
        before = old[identity]
        after = new[identity]

        if before.currency != after.currency:
            raise ValueError("Position currency changed unexpectedly")

        if before.quantity != after.quantity:
            quantity_changed += 1
            continue

        value_differs = (
            before.market_value_ex_accrued
            != after.market_value_ex_accrued
        )
        accrued_differs = before.accrued_interest != after.accrued_interest

        if value_differs:
            value_changed += 1
        if accrued_differs:
            accrued_changed += 1

        if not value_differs and not accrued_differs:
            if before.source_observation_id != after.source_observation_id:
                source_only_changed += 1
            else:
                unchanged += 1

    return PortfolioChanges(
        previous_date=previous.as_of_date.isoformat(),
        current_date=current.as_of_date.isoformat(),
        previous_position_count=len(old),
        current_position_count=len(new),
        added_count=len(new.keys() - old.keys()),
        removed_count=len(old.keys() - new.keys()),
        quantity_changed_count=quantity_changed,
        value_changed_at_constant_quantity_count=value_changed,
        accrued_changed_at_constant_quantity_count=accrued_changed,
        source_only_changed_count=source_only_changed,
        unchanged_count=unchanged,
    )
