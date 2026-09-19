"""Read existing, matching CORE portfolio and cashflow data without writes."""

import json
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from portfolio_quant.cashflow_adapter import (
    CashflowRun,
    parse_core_cashflows,
)
from portfolio_quant.core_adapter import (
    PortfolioSnapshot,
    parse_core_positions,
)


CORE_DATABASE = (
    Path.home()
    / "investment-management-data-data"
    / "database"
    / "investment_management.sqlite3"
)


@dataclass(frozen=True)
class CoreInputs:
    snapshot: PortfolioSnapshot
    cashflows: CashflowRun


def load_core_inputs(*, database: Path = CORE_DATABASE) -> CoreInputs:
    """Load validated positions and matching existing cashflows, read-only.

    Requires the existing CORE Python package on PYTHONPATH.
    Does not invoke the CORE CLI, migrations, collectors, or calculations.
    """
    from investment_manager.database.connection import connect_readonly
    from investment_manager.control.reports import (
        envelope,
        portfolio_positions,
    )
    from investment_manager.cashflow.service import show

    database = Path(database)

    if (
        database.is_symlink()
        or database.parent.is_symlink()
        or not database.is_file()
    ):
        raise RuntimeError("CORE database is missing or has an unsafe path")

    with closing(connect_readonly(database)) as connection:
        snapshot = parse_core_positions(
            envelope(
                "portfolio.positions",
                portfolio_positions(connection),
            )
        )

        rows = connection.execute(
            """
            SELECT s.id, s.isin, s.security_code, s.market_section,
                   s.source_observation_id, s.quantity_decimal
            FROM portfolio_security_snapshots s
            JOIN (
                SELECT MAX(id) AS id
                FROM portfolio_security_snapshots
                WHERE as_of_date = ?
                GROUP BY as_of_date, isin, security_code, market_section
            ) canonical ON canonical.id = s.id
            """,
            (snapshot.as_of_date.isoformat(),),
        ).fetchall()

        canonical = {}
        for row in rows:
            quantity = Decimal(row["quantity_decimal"])
            if quantity <= 0:
                continue

            identity = (
                row["isin"],
                row["security_code"] or None,
                row["market_section"],
            )
            if identity in canonical:
                raise RuntimeError("Ambiguous CORE position identity")

            canonical[identity] = row

        if len(canonical) != len(snapshot.positions):
            raise RuntimeError("CORE position count does not match")

        snapshot_ids = set()
        for position in snapshot.positions:
            identity = (
                position.isin,
                position.security_code,
                position.market_section,
            )
            row = canonical.get(identity)

            if (
                row is None
                or row["source_observation_id"]
                != position.source_observation_id
                or Decimal(row["quantity_decimal"]) != position.quantity
            ):
                raise RuntimeError("CORE position does not match its snapshot")

            snapshot_ids.add(row["id"])

        candidates = connection.execute(
            """
            SELECT id, portfolio_snapshot_ids_json
            FROM cashflow_forecast_runs
            WHERE status = 'SUCCESS'
              AND portfolio_snapshot_date = ?
            ORDER BY id DESC
            """,
            (snapshot.as_of_date.isoformat(),),
        ).fetchall()

        for candidate in candidates:
            stored_ids = json.loads(
                candidate["portfolio_snapshot_ids_json"]
            )
            if (
                not isinstance(stored_ids, list)
                or set(stored_ids) != snapshot_ids
            ):
                continue

            cashflows = parse_core_cashflows(
                envelope(
                    "cashflow.show",
                    show(connection, candidate["id"]),
                ),
                expected_snapshot_ids=snapshot_ids,
            )

            if cashflows.portfolio_date != snapshot.as_of_date:
                raise RuntimeError("CORE portfolio and cashflow dates differ")

            return CoreInputs(
                snapshot=snapshot,
                cashflows=cashflows,
            )

    raise RuntimeError(
        "No existing successful CORE cashflow run matches current positions"
    )
