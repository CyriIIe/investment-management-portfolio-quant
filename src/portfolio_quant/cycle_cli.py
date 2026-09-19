"""Manual entry point for explicitly experimental Portfolio Quant cycles."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from portfolio_quant.core_readonly import CORE_DATABASE, load_core_inputs
from portfolio_quant.cycle_runner import run_experimental_cycle
from portfolio_quant.cycle_store import experimental_cycle_exists
from portfolio_quant.experimental_cycle import identify_experimental_cycle


QUANT_DATA_DIR = (
    Path.home() / "investment-management-portfolio-quant-data"
)
CYCLE_DATABASE = QUANT_DATA_DIR / "cycles.sqlite3"


def run_manual_cycle(*, apply: bool = False) -> str:
    """Identify a cycle, or explicitly run it using an existing Quant DB."""
    if type(apply) is not bool:
        raise ValueError("apply must be a boolean")

    if (
        QUANT_DATA_DIR.is_symlink()
        or not QUANT_DATA_DIR.is_dir()
        or CYCLE_DATABASE != QUANT_DATA_DIR / "cycles.sqlite3"
        or CYCLE_DATABASE.is_symlink()
        or CYCLE_DATABASE.resolve().parent != QUANT_DATA_DIR.resolve()
    ):
        raise RuntimeError("Unsafe or missing Quant data directory")

    if not CORE_DATABASE.is_file() or CORE_DATABASE.is_symlink():
        raise RuntimeError("Missing or unsafe CORE database")

    inputs = load_core_inputs()

    # Read only the hashes needed to identify the existing CORE calculation.
    with closing(
        sqlite3.connect(CORE_DATABASE.as_uri() + "?mode=ro", uri=True)
    ) as core:
        core.execute("PRAGMA query_only = ON")
        hashes = core.execute(
            """
            SELECT input_sha256, result_sha256, policy_sha256
            FROM cashflow_forecast_runs
            WHERE id = ? AND status = 'SUCCESS'
            """,
            (inputs.cashflows.run_id,),
        ).fetchone()

    if hashes is None or any(not value for value in hashes):
        raise RuntimeError("Missing CORE cashflow calculation hashes")

    parameters = {
        "cashflow_input_sha256": hashes[0],
        "cashflow_result_sha256": hashes[1],
        "cashflow_policy_sha256": hashes[2],
    }
    identity = identify_experimental_cycle(inputs, **parameters)

    print("===== CYCLE PORTFOLIO QUANT =====")
    print("Mode :", "ENREGISTREMENT" if apply else "VERIFICATION")
    print("Positions validées :", len(inputs.snapshot.positions))
    print("Calcul de flux :", inputs.cashflows.run_id)
    print("Échéanciers inconnus :", inputs.cashflows.unknown_schedule_count)
    print("Identité du cycle (préfixe) :", identity[:16])

    if not CYCLE_DATABASE.is_file():
        if apply:
            raise RuntimeError(
                "Quant cycle database missing; initialize it separately"
            )
        print("Base de cycles : absente ; aucun calcul lancé.")
        return "DATABASE_MISSING"

    mode = "rw" if apply else "ro"
    with closing(
        sqlite3.connect(
            CYCLE_DATABASE.as_uri() + f"?mode={mode}",
            uri=True,
        )
    ) as connection:
        if not apply:
            connection.execute("PRAGMA query_only = ON")
            exists = experimental_cycle_exists(
                connection,
                identity_sha256=identity,
            )
            print("Cycle déjà enregistré :", exists)
            print("Aucun calcul ni écriture effectués.")
            return "ALREADY_EXISTS" if exists else "NOT_CALCULATED"

        outcome = run_experimental_cycle(
            connection,
            inputs,
            **parameters,
        )

    print("Résultat :", outcome.status)
    return outcome.status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Experimental known-coupon cycle; dry-run by default"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Calculate and save to the existing Quant cycles database",
    )
    args = parser.parse_args()
    run_manual_cycle(apply=args.apply)


if __name__ == "__main__":
    main()
