"""Simulation documentaire expérimentale, sans écriture CORE ni LAB."""

import hashlib
import json
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

from portfolio_quant.deterministic_total_return import calculate_total_return
from portfolio_quant.documented_bond_flows import (
    build_bond_case,
    parse_documented_bond_flows,
)

HOME = Path.home()
RESEARCH = HOME / "investment-management-portfolio-quant-data" / "research"
CORE = (
    HOME / "investment-management-data-data"
    / "database" / "investment_management.sqlite3"
)

# Liste explicite : aucun balayage automatique du portefeuille.
INSTRUMENTS = {
    "gtlk": (
        "RU000A10F801",
        "gtlk_002p_13_2026-09-10.json",
        "gtlk_002p_13_pilot_results.json",
    ),
    "sber": (
        "RU000A10DCH3",
        "sber_d10_2026-09-10.json",
        "sber_d10_pilot_results.json",
    ),
}

RATES = ("0.10", "0.125", "0.15")
HORIZON = date(2027, 9, 10)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reconcile_price(document, validated):
    """Rapproche le prix avec CORE, ouvert exclusivement en lecture seule."""
    market = document["market_reference"]

    require(CORE.is_file() and not CORE.is_symlink(),
            "Chemin CORE absent ou non conforme")
    require(
        market["accrued_interest"] is not None,
        "ACCINT manquant : prix dirty non vérifiable",
    )

    with closing(sqlite3.connect(
        f"{CORE.as_uri()}?mode=ro", uri=True
    )) as connection:
        connection.execute("PRAGMA query_only = ON")

        identities = connection.execute(
            "SELECT id FROM bonds WHERE isin = ?",
            (validated.isin,),
        ).fetchall()
        require(len(identities) == 1, "Identité CORE absente ou ambiguë")
        bond_id = identities[0][0]

        boards = connection.execute(
            """
            SELECT DISTINCT board_id
            FROM bond_board_history
            WHERE bond_id = ?
              AND is_primary = 1
              AND valid_from <= ?
              AND (valid_to IS NULL OR valid_to >= ?)
            """,
            (
                bond_id,
                validated.valuation_date.isoformat(),
                validated.valuation_date.isoformat(),
            ),
        ).fetchall()
        require(
            len(boards) == 1
            and boards[0][0] == validated.primary_board,
            "Board primaire CORE non réconcilié",
        )

        prices = connection.execute(
            """
            SELECT canonical_close_price_decimal,
                   accrued_interest_decimal
            FROM bond_market_history
            WHERE bond_id = ?
              AND board_id = ?
              AND trade_date = ?
              AND quality_status = 'ACCEPTED'
            """,
            (
                bond_id,
                validated.primary_board,
                validated.valuation_date.isoformat(),
            ),
        ).fetchall()

    require(len(prices) == 1, "Prix CORE absent ou ambigu")
    close, accrued = prices[0]
    require(close is not None and accrued is not None,
            "Prix ou ACCINT CORE manquant")

    document_close = Decimal(str(market["canonical_close_price_pct"]))
    document_accrued = Decimal(str(market["accrued_interest"]))

    require(
        Decimal(str(close)) == document_close
        and Decimal(str(accrued)) == document_accrued,
        "Prix documentaire non réconcilié avec CORE",
    )

    dirty = validated.face_value * document_close / Decimal("100")
    dirty += document_accrued
    require(dirty > 0, "Prix dirty invalide")
    return dirty


def run(name):
    require(name in INSTRUMENTS, "Instrument non autorisé")
    expected_isin, filename, output_name = INSTRUMENTS[name]
    source = RESEARCH / filename
    output = RESEARCH / output_name

    require(source.is_file() and not source.is_symlink(),
            "Document privé absent ou chemin non conforme")

    raw = source.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    document = json.loads(raw, parse_float=Decimal)

    validated = parse_documented_bond_flows(document)
    require(validated.isin == expected_isin, "ISIN inattendu")
    require(
        validated.valuation_date == date(2026, 9, 10)
        and validated.observation_date == date(2026, 9, 19)
        and validated.historical_availability_proven is False,
        "Dates ou disponibilité historique inattendues",
    )

    dirty = reconcile_price(document, validated)
    bond = build_bond_case(
        validated,
        horizon_date=HORIZON,
        verified_dirty_price=dirty,
    )
    results = calculate_total_return(
        bond, annual_market_yields=RATES
    )

    scenarios = []
    for result in results:
        rate = float(result.annual_market_yield)

        independent_received = math.fsum(
            float(flow.amount)
            for flow in validated.flows
            if flow.payment_date <= HORIZON
        )
        independent_terminal = math.fsum(
            float(flow.amount)
            / (1.0 + rate) ** (
                (flow.payment_date - HORIZON).days / 365.0
            )
            for flow in validated.flows
            if flow.payment_date > HORIZON
        )
        independent_return = (
            independent_received + independent_terminal - float(dirty)
        ) / float(dirty)

        require(
            abs(float(result.total_return) - independent_return) < 1e-10,
            "Échec du contrôle numérique indépendant",
        )

        scenarios.append({
            "hypothetical_annual_market_yield": str(
                result.annual_market_yield
            ),
            "received_through_horizon_rub_per_bond": str(
                result.received_before_or_on_horizon
            ),
            "theoretical_terminal_price_rub_per_bond": str(
                result.theoretical_terminal_price
            ),
            "terminal_wealth_rub_per_bond": str(result.terminal_wealth),
            "gross_total_return_decimal": str(result.total_return),
        })

    payload = {
        "status": "EXPERIMENTAL",
        "instrument_isin": validated.isin,
        "coupon_type": validated.coupon_type,
        "valuation_date": validated.valuation_date.isoformat(),
        "horizon_date": HORIZON.isoformat(),
        "document_observation_date": validated.observation_date.isoformat(),
        "historical_cashflow_availability": "NOT_PROVEN",
        "historical_backtest_validated": False,
        "price_basis": "MOEX_LEGALCLOSEPRICE_PLUS_ACCINT",
        "dirty_price_rub_per_bond": str(dirty),
        "source_json_sha256": source_hash,
        "coupon_count": validated.coupon_count,
        "principal_event_count": validated.principal_event_count,
        "principal_reconciled": True,
        "core_read_only_reconciliation": "PASSED",
        "independent_numerical_check": "PASSED",
        "assumptions": {
            "valuation": "Flat hypothetical annual yield; ACT/365",
            "taxes": "NOT_INCLUDED",
            "fees": "NOT_INCLUDED",
            "default": "NOT_MODELED",
            "reinvestment": "NOT_INCLUDED",
            "market_yields_are_forecasts": False,
            "price_is_broker_execution_price": False,
        },
        "scenarios": scenarios,
    }

    require(output.parent.is_dir(), "Dossier privé introuvable")
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".documented_pilot_",
            suffix=".json",
            dir=output.parent,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)

    print("===== PILOTE DOCUMENTAIRE =====")
    print("Instrument :", name.upper())
    print("Calendrier et principal : OK")
    print("Prix CORE en lecture seule : OK")
    print("Trois scénarios et contrôle indépendant : OK")
    print("Résultat privé enregistré : OK")
    print("Historique sans connaissance future : NON VALIDÉ")
    print("Aucune position ni quantité détenue affichée.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("instrument", choices=tuple(INSTRUMENTS))
    arguments = parser.parse_args()
    run(arguments.instrument)
