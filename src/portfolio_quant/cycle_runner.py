"""Run one experimental cycle, skipping an already stored identity."""

import sqlite3
from dataclasses import dataclass

from portfolio_quant.core_readonly import CoreInputs
from portfolio_quant.cycle_store import (
    experimental_cycle_exists,
    save_experimental_cycle,
)
from portfolio_quant.experimental_cycle import (
    identify_experimental_cycle,
    prepare_experimental_cycle,
)


@dataclass(frozen=True)
class CycleRunOutcome:
    identity_sha256: str
    status: str


def run_experimental_cycle(
    connection: sqlite3.Connection,
    core_inputs: CoreInputs,
    *,
    cashflow_input_sha256: str,
    cashflow_result_sha256: str,
    cashflow_policy_sha256: str,
    **simulation_parameters,
) -> CycleRunOutcome:
    """Check identity before simulation; store results in caller's database."""
    parameters = {
        "cashflow_input_sha256": cashflow_input_sha256,
        "cashflow_result_sha256": cashflow_result_sha256,
        "cashflow_policy_sha256": cashflow_policy_sha256,
        **simulation_parameters,
    }

    identity = identify_experimental_cycle(core_inputs, **parameters)

    if experimental_cycle_exists(
        connection,
        identity_sha256=identity,
    ):
        return CycleRunOutcome(
            identity_sha256=identity,
            status="ALREADY_EXISTS",
        )

    prepared = prepare_experimental_cycle(core_inputs, **parameters)

    if prepared.identity_sha256 != identity:
        raise RuntimeError(
            "Cycle identity changed between identification and calculation"
        )

    inserted = save_experimental_cycle(
        connection,
        identity_sha256=identity,
        inputs=prepared.inputs,
        results=prepared.results,
    )

    return CycleRunOutcome(
        identity_sha256=identity,
        status="INSERTED" if inserted else "ALREADY_EXISTS",
    )
