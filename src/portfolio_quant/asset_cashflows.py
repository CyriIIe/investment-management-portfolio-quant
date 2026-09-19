"""Associate known CORE cashflows with assets without guessing identities."""

from dataclasses import dataclass
from datetime import date

from portfolio_quant.core_readonly import CoreInputs


@dataclass(frozen=True)
class AssetCashflowSummary:
    isin: str
    security_code: str | None
    market_section: str
    currency: str
    known_event_count: int
    next_known_event_date: date | None
    incomplete_reasons: tuple[str, ...]


@dataclass(frozen=True)
class AssetCashflowAssociation:
    assets: tuple[AssetCashflowSummary, ...]
    unassigned_event_count: int
    unassigned_schedule_count: int
    complete_cashflows: bool = False


def associate_asset_cashflows(
    inputs: CoreInputs,
) -> AssetCashflowAssociation:
    """Match only unambiguous identities from validated CORE inputs."""
    if not isinstance(inputs, CoreInputs):
        raise ValueError("Expected validated CORE inputs")

    snapshot = inputs.snapshot
    cashflows = inputs.cashflows

    if snapshot.as_of_date != cashflows.portfolio_date:
        raise ValueError("Portfolio and cashflow dates differ")

    positions = snapshot.positions

    by_isin_currency = {}
    by_isin = {}

    for index, position in enumerate(positions):
        by_isin_currency.setdefault(
            (position.isin, position.currency), []
        ).append(index)
        by_isin.setdefault(position.isin, []).append(index)

    events_by_index = [[] for _ in positions]
    reasons_by_index = [[] for _ in positions]
    unassigned_events = 0
    unassigned_schedules = 0

    for event in cashflows.events:
        matches = by_isin_currency.get(
            (event.isin, event.currency), []
        )

        if event.isin is None or len(matches) != 1:
            unassigned_events += 1
            continue

        events_by_index[matches[0]].append(event)

    for unknown in cashflows.unknown_schedules:
        matches = by_isin.get(unknown.isin, [])

        if unknown.isin is None or len(matches) != 1:
            unassigned_schedules += 1
            continue

        reasons_by_index[matches[0]].extend(unknown.reasons)

    assets = []

    for index, position in enumerate(positions):
        matched_events = events_by_index[index]
        next_date = min(
            (event.event_date for event in matched_events),
            default=None,
        )

        assets.append(
            AssetCashflowSummary(
                isin=position.isin,
                security_code=position.security_code,
                market_section=position.market_section,
                currency=position.currency,
                known_event_count=len(matched_events),
                next_known_event_date=next_date,
                incomplete_reasons=tuple(
                    dict.fromkeys(reasons_by_index[index])
                ),
            )
        )

    return AssetCashflowAssociation(
        assets=tuple(assets),
        unassigned_event_count=unassigned_events,
        unassigned_schedule_count=unassigned_schedules,
    )
