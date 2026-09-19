"""Prepare a reproducible, partial experimental cycle without database writes."""

from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256

from portfolio_quant.core_readonly import CoreInputs
from portfolio_quant.cycle_identity import cycle_identity
from portfolio_quant.path_bridge import PATHS_BINARY
from portfolio_quant.path_scenarios import calculate_known_coupon_paths
from portfolio_quant.rate_paths import generate_rate_paths


@dataclass(frozen=True)
class PreparedCycle:
    identity_sha256: str
    inputs: dict
    results: dict


def _identify_cycle(
    core_inputs: CoreInputs,
    *,
    cashflow_input_sha256: str,
    cashflow_result_sha256: str,
    cashflow_policy_sha256: str,
    rust_binary: Path = PATHS_BINARY,
    initial_rate: str = "0.10",
    monthly_volatility: str = "0.005",
    path_count: int = 10,
    seed: int = 42,
) -> tuple[str, str]:
    """Return the identity and binary hash without simulating."""
    if not isinstance(core_inputs, CoreInputs):
        raise ValueError("Expected validated CORE inputs")

    binary = Path(rust_binary)
    if not binary.is_file() or not binary.samefile(PATHS_BINARY):
        raise ValueError("Expected the existing quant_paths Rust binary")

    binary_hash = sha256(binary.read_bytes()).hexdigest()
    snapshot = core_inputs.snapshot
    cashflows = core_inputs.cashflows

    if snapshot.as_of_date != cashflows.portfolio_date:
        raise ValueError("CORE position and cashflow dates differ")

    identity = cycle_identity(
        positions_sha256=snapshot.source_hash,
        cashflow_input_sha256=cashflow_input_sha256,
        cashflow_result_sha256=cashflow_result_sha256,
        cashflow_policy_sha256=cashflow_policy_sha256,
        rust_binary_sha256=binary_hash,
        initial_rate=initial_rate,
        monthly_volatility=monthly_volatility,
        months=12,
        path_count=path_count,
        seed=seed,
    )

    return identity, binary_hash


def identify_experimental_cycle(
    core_inputs: CoreInputs,
    *,
    cashflow_input_sha256: str,
    cashflow_result_sha256: str,
    cashflow_policy_sha256: str,
    rust_binary: Path = PATHS_BINARY,
    initial_rate: str = "0.10",
    monthly_volatility: str = "0.005",
    path_count: int = 10,
    seed: int = 42,
) -> str:
    """Identify a cycle without generating trajectories or invoking Rust."""
    identity, _ = _identify_cycle(
        core_inputs,
        cashflow_input_sha256=cashflow_input_sha256,
        cashflow_result_sha256=cashflow_result_sha256,
        cashflow_policy_sha256=cashflow_policy_sha256,
        rust_binary=rust_binary,
        initial_rate=initial_rate,
        monthly_volatility=monthly_volatility,
        path_count=path_count,
        seed=seed,
    )
    return identity


def prepare_experimental_cycle(
    core_inputs: CoreInputs,
    *,
    cashflow_input_sha256: str,
    cashflow_result_sha256: str,
    cashflow_policy_sha256: str,
    rust_binary: Path = PATHS_BINARY,
    initial_rate: str = "0.10",
    monthly_volatility: str = "0.005",
    path_count: int = 10,
    seed: int = 42,
) -> PreparedCycle:
    """Run fictional known-coupon calculations; do not persist anything."""
    identity, binary_hash = _identify_cycle(
        core_inputs,
        cashflow_input_sha256=cashflow_input_sha256,
        cashflow_result_sha256=cashflow_result_sha256,
        cashflow_policy_sha256=cashflow_policy_sha256,
        rust_binary=rust_binary,
        initial_rate=initial_rate,
        monthly_volatility=monthly_volatility,
        path_count=path_count,
        seed=seed,
    )
    snapshot = core_inputs.snapshot
    cashflows = core_inputs.cashflows

    simulation = generate_rate_paths(
        initial_rate=initial_rate,
        monthly_volatility=monthly_volatility,
        months=12,
        path_count=path_count,
        seed=seed,
    )
    calculation = calculate_known_coupon_paths(cashflows, simulation)

    if (
        calculation.calibrated_to_market
        or calculation.complete_portfolio_valuation
        or calculation.portfolio_risk_measure
    ):
        raise ValueError("Experimental calculation has unexpected scope")

    inputs = {
        "model": "fictional-known-coupon-paths",
        "portfolio_date": snapshot.as_of_date.isoformat(),
        "positions_sha256": snapshot.source_hash,
        "cashflow_run_id": cashflows.run_id,
        "cashflow_input_sha256": cashflow_input_sha256,
        "cashflow_result_sha256": cashflow_result_sha256,
        "cashflow_policy_sha256": cashflow_policy_sha256,
        "rust_binary_sha256": binary_hash,
        "initial_rate": str(simulation.initial_rate),
        "monthly_volatility": str(simulation.monthly_volatility),
        "months": simulation.months,
        "path_count": calculation.path_count,
        "seed": simulation.seed,
    }

    results = {
        "event_count": calculation.event_count,
        "coupon_coverage_pct": str(calculation.coupon_coverage_pct),
        "unknown_schedule_count": calculation.unknown_schedule_count,
        "includes_principal": calculation.includes_principal,
        "calibrated_to_market": calculation.calibrated_to_market,
        "complete_portfolio_valuation": (
            calculation.complete_portfolio_valuation
        ),
        "portfolio_risk_measure": calculation.portfolio_risk_measure,
        "scope": "known-contractual-coupons-only",
        "path_values_by_currency": [
            {
                currency: str(value)
                for currency, value in sorted(
                    path.present_value_by_currency.items()
                )
            }
            for path in calculation.paths
        ],
    }

    return PreparedCycle(
        identity_sha256=identity,
        inputs=inputs,
        results=results,
    )
