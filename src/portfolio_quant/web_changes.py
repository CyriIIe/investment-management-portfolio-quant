"""Aggregate portfolio changes from read-only CORE snapshots."""

from portfolio_quant.change_explanations import explain_changes
from portfolio_quant.core_history import load_previous_historical_snapshot
from portfolio_quant.core_readonly import load_core_inputs
from portfolio_quant.portfolio_changes import compare_portfolio_snapshots


def read_changes() -> dict:
    """Describe changes, without holdings, amounts or performance claims."""
    current = load_core_inputs().snapshot
    previous = load_previous_historical_snapshot(current.as_of_date)
    changes = compare_portfolio_snapshots(previous, current)
    explanations = explain_changes(changes)

    return {
        "previous_date": changes.previous_date,
        "current_date": changes.current_date,
        "previous_position_count": changes.previous_position_count,
        "current_position_count": changes.current_position_count,
        "added_count": changes.added_count,
        "removed_count": changes.removed_count,
        "quantity_changed_count": changes.quantity_changed_count,
        "value_changed_at_constant_quantity_count": (
            changes.value_changed_at_constant_quantity_count
        ),
        "accrued_changed_at_constant_quantity_count": (
            changes.accrued_changed_at_constant_quantity_count
        ),
        "source_only_changed_count": changes.source_only_changed_count,
        "unchanged_count": changes.unchanged_count,
        "portfolio_risk_measure": changes.portfolio_risk_measure,
        "performance_measure": changes.performance_measure,
        "explanations": {
            "observations": list(explanations.observations),
            "limitations": list(explanations.limitations),
        },
    }
