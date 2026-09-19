"""Conservative, read-only bond eligibility diagnostics.

No CORE writes, no MOEX calls, no inferred coupon fixity or completeness.
"""

from collections import Counter
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sqlite3

CORE_DB = (
    Path.home() / "investment-management-data-data"
    / "database" / "investment_management.sqlite3"
)


def decimal_or_none(value):
    if value is None or isinstance(value, (float, bool)):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


def evaluate_evidence(
    *,
    as_of,
    terms,
    primary_boards,
    accepted_closes,
    actions,
):
    """Return evidence and blockers without claiming unproved completeness."""
    reasons = []

    if len(set(primary_boards)) != 1:
        reasons.append("PRIMARY_BOARD_UNVERIFIED")
    if len(accepted_closes) != 1:
        reasons.append("CANONICAL_CLOSE_UNVERIFIED")

    if not isinstance(terms, dict):
        terms = {}

    face = decimal_or_none(terms.get("FACEVALUE"))
    if face is None or face <= 0:
        reasons.append("REMAINING_PRINCIPAL_UNVERIFIED")

    try:
        maturity = date.fromisoformat(terms["MATDATE"])
        if maturity <= as_of:
            raise ValueError("Maturity not future")
    except (KeyError, TypeError, ValueError):
        maturity = None
        reasons.append("MATURITY_UNVERIFIED")

    principal_sum = Decimal("0")
    principal_count = 0
    coupon_count = 0
    coupon_amounts_ok = True
    conditional_offer = False

    for kind, day, raw_amount in actions:
        try:
            action_date = date.fromisoformat(day)
        except (ValueError, TypeError):
            reasons.append("ACTION_DATE_INVALID")
            continue

        if action_date <= as_of:
            continue

        if maturity is not None and action_date > maturity:
            reasons.append("ACTION_AFTER_MATURITY")
            continue

        amount = decimal_or_none(raw_amount)

        if kind == "OFFER":
            conditional_offer = True
        elif kind == "COUPON":
            coupon_count += 1
            if amount is None or amount <= 0:
                coupon_amounts_ok = False
        elif kind in ("AMORTIZATION", "MATURITY"):
            principal_count += 1
            if amount is None or amount <= 0:
                reasons.append("PRINCIPAL_AMOUNT_MISSING")
            else:
                principal_sum += amount
        else:
            reasons.append("UNKNOWN_ACTION_TYPE")

    if conditional_offer:
        reasons.append("CONDITIONAL_OFFER_REQUIRES_MODEL")

    if coupon_count == 0 or not coupon_amounts_ok:
        reasons.append("COUPON_AMOUNTS_UNVERIFIED")

    if (
        principal_count == 0
        or face is None
        or face <= 0
        or abs(principal_sum - face) > Decimal("0.01")
    ):
        reasons.append("PRINCIPAL_SCHEDULE_UNRECONCILED")

    # Neither a coupon percentage nor positive recorded coupons proves
    # that the bond is fixed-rate or that no coupons are missing.
    reasons.extend((
        "FIXED_COUPON_NOT_PROVEN",
        "FULL_COUPON_SCHEDULE_NOT_PROVEN",
    ))

    return {
        "determinable": False,
        "reasons": tuple(dict.fromkeys(reasons)),
        "coupon_count": coupon_count,
        "principal_count": principal_count,
    }


def diagnose_held_bonds(database=CORE_DB):
    """Return aggregate blockers only; never return holdings or prices."""
    database = Path(database)
    if (
        not database.is_file()
        or database.is_symlink()
        or database.parent.is_symlink()
    ):
        raise RuntimeError("CORE database missing or unsafe path")

    connection = sqlite3.connect(
        f"{database.as_uri()}?mode=ro",
        uri=True,
    )
    connection.execute("PRAGMA query_only = ON")

    with closing(connection) as con:
        row = con.execute(
            "SELECT MAX(as_of_date) FROM portfolio_security_snapshots"
        ).fetchone()
        if row is None or row[0] is None:
            raise RuntimeError("No CORE portfolio snapshot")

        as_of_text = row[0]
        as_of = date.fromisoformat(as_of_text)
        positions = con.execute(
            """
            WITH canonical AS (
                SELECT MAX(id) AS id
                FROM portfolio_security_snapshots
                WHERE as_of_date = ?
                GROUP BY as_of_date, isin, security_code, market_section
            )
            SELECT p.isin
            FROM canonical c
            JOIN portfolio_security_snapshots p ON p.id = c.id
            """,
            (as_of_text,),
        ).fetchall()

        counts = Counter()

        for (isin,) in positions:
            bond_rows = con.execute(
                "SELECT id FROM bonds WHERE isin = ?",
                (isin,),
            ).fetchall()

            if len(bond_rows) != 1:
                counts["BOND_IDENTITY_UNVERIFIED"] += 1
                continue

            bond_id = bond_rows[0][0]
            term_rows = con.execute(
                """
                SELECT terms_json
                FROM bond_terms_history
                WHERE bond_id = ?
                  AND substr(observed_at_utc, 1, 10) <= ?
                ORDER BY observed_at_utc DESC, id DESC
                LIMIT 1
                """,
                (bond_id, as_of_text),
            ).fetchall()

            try:
                terms = json.loads(term_rows[0][0]) if term_rows else {}
            except (ValueError, TypeError):
                terms = {}

            boards = [
                record[0] for record in con.execute(
                    """
                    SELECT DISTINCT board_id
                    FROM bond_board_history
                    WHERE bond_id = ?
                      AND is_primary = 1
                      AND valid_from <= ?
                      AND (valid_to IS NULL OR valid_to >= ?)
                    """,
                    (bond_id, as_of_text, as_of_text),
                )
            ]

            closes = []
            if len(boards) == 1:
                closes = con.execute(
                    """
                    SELECT id
                    FROM bond_market_history
                    WHERE bond_id = ?
                      AND board_id = ?
                      AND trade_date = ?
                      AND quality_status = 'ACCEPTED'
                      AND canonical_close_price_decimal IS NOT NULL
                    """,
                    (bond_id, boards[0], as_of_text),
                ).fetchall()

            actions = con.execute(
                """
                SELECT action_type, action_date, amount_decimal
                FROM corporate_actions
                WHERE bond_id = ? AND action_date > ?
                ORDER BY action_date, id
                """,
                (bond_id, as_of_text),
            ).fetchall()

            evidence = evaluate_evidence(
                as_of=as_of,
                terms=terms,
                primary_boards=boards,
                accepted_closes=closes,
                actions=actions,
            )

            counts["EXAMINED"] += 1
            if evidence["determinable"]:
                counts["DETERMINABLE"] += 1
            for reason in evidence["reasons"]:
                counts[reason] += 1

        return as_of_text, len(positions), dict(sorted(counts.items()))
