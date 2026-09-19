"""Pilote documentaire OFZ 26252 : simulation expérimentale, sans écriture CORE."""

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

from portfolio_quant.deterministic_total_return import (
    BondCase,
    BondFlow,
    calculate_total_return,
)

HOME = Path.home()
RESEARCH = (
    HOME / "investment-management-portfolio-quant-data"
    / "research" / "ofz_26252_2026-09-10.json"
)
OUTPUT = (
    HOME / "investment-management-portfolio-quant-data"
    / "research" / "ofz_26252_pilot_results.json"
)
CORE = (
    HOME / "investment-management-data-data"
    / "database" / "investment_management.sqlite3"
)

def require(condition, message):
    if not condition:
        raise ValueError(message)

def main():
    require(RESEARCH.is_file(), "Document de recherche introuvable")
    require(CORE.is_file(), "Base CORE introuvable")

    raw = RESEARCH.read_bytes()
    document_hash = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw, parse_float=Decimal)

    instrument = data["instrument"]
    market = data["market_reference"]
    valuation = date.fromisoformat(data["valuation_date"])
    maturity = date.fromisoformat(instrument["maturity_date"])
    face = Decimal(str(instrument["face_value"]))

    require(instrument["isin"] == "RU000A10D4Y2", "ISIN inattendu")
    require(instrument["secid"] == "SU26252RMFS5", "SECID inattendu")
    require(instrument["coupon_type"] == "FIXED_KNOWN", "Coupon non fixe")
    require(instrument["status"] == "VERIFIED", "Instrument non vérifié")
    require(instrument["currency"] == "RUB", "Devise inattendue")
    require(face > 0, "Nominal invalide")
    require(valuation == date(2026, 9, 10), "Photographie inattendue")
    require(maturity == date(2033, 10, 12), "Échéance inattendue")
    require(
        instrument["source_observation_date"] == "2026-09-19",
        "Date de vérification documentaire inattendue",
    )
    require(market["status"] == "VERIFIED", "Marché non vérifié")
    require(market["trade_date"] == data["valuation_date"], "Date de prix incorrecte")
    require(market["canonical_close_price_field"] == "LEGALCLOSEPRICE",
            "Champ de clôture incorrect")
    require(market["accrued_interest_field"] == "ACCINT",
            "Champ d'intérêts courus incorrect")
    require(market["board"] == instrument["primary_board"],
            "Board documentaire incohérent")
    require(not data["conditional_events"], "Offre conditionnelle présente")

    completeness = data["completeness"]
    require(completeness["coupon_schedule_complete"] is True,
            "Calendrier des coupons incomplet")
    require(completeness["principal_schedule_complete"] is True,
            "Calendrier du principal incomplet")
    require(
        completeness["as_of_2026_09_10_schedule_publication_proven"] is False,
        "Statut de disponibilité historique inattendu",
    )

    coupons = data["cashflows"]
    principal_events = data["principal_events"]
    require(len(coupons) == 15, "Nombre de coupons inattendu")
    require(len(principal_events) == 1, "Nombre de remboursements inattendu")

    flows = []
    seen_dates = set()

    for item in coupons:
        payment_date = date.fromisoformat(item["date"])
        amount = Decimal(str(item["amount"]))
        require(
            item["type"] == "COUPON"
            and item["status"] == "VERIFIED"
            and item["currency"] == "RUB"
            and valuation < payment_date <= maturity
            and amount > 0
            and payment_date not in seen_dates,
            "Coupon invalide ou dupliqué",
        )
        require(
            item["availability_status"] == "UNKNOWN"
            and item["available_on_or_before_2026_09_10"] is None
            and item["source_observation_date"] == "2026-09-19",
            "Provenance temporelle incohérente",
        )
        seen_dates.add(payment_date)
        flows.append(BondFlow(payment_date, "COUPON", amount))

    principal_total = Decimal("0")
    for item in principal_events:
        payment_date = date.fromisoformat(item["date"])
        amount = Decimal(str(item["amount"]))
        require(
            item["type"] == "MATURITY_REDEMPTION"
            and item["status"] == "VERIFIED"
            and item["currency"] == "RUB"
            and payment_date == maturity
            and amount > 0,
            "Remboursement invalide",
        )
        principal_total += amount
        flows.append(BondFlow(payment_date, "PRINCIPAL", amount))

    require(principal_total == face, "Principal non réconcilié")

    # CORE : connexion SQLite explicitement en lecture seule.
    connection = sqlite3.connect(f"{CORE.as_uri()}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")

    with closing(connection) as con:
        bonds = con.execute(
            "SELECT id FROM bonds WHERE isin = ?",
            (instrument["isin"],),
        ).fetchall()
        require(len(bonds) == 1, "Identité CORE ambiguë ou absente")
        bond_id = bonds[0][0]

        boards = con.execute(
            """
            SELECT DISTINCT board_id FROM bond_board_history
            WHERE bond_id = ? AND is_primary = 1
              AND valid_from <= ?
              AND (valid_to IS NULL OR valid_to >= ?)
            """,
            (bond_id, data["valuation_date"], data["valuation_date"]),
        ).fetchall()
        require(
            len(boards) == 1 and boards[0][0] == market["board"],
            "Board primaire CORE non confirmé",
        )

        prices = con.execute(
            """
            SELECT canonical_close_price_decimal, accrued_interest_decimal
            FROM bond_market_history
            WHERE bond_id = ? AND board_id = ? AND trade_date = ?
              AND quality_status = 'ACCEPTED'
            """,
            (bond_id, market["board"], data["valuation_date"]),
        ).fetchall()

        require(len(prices) == 1, "Clôture CORE ambiguë ou absente")
        require(
            prices[0][0] is not None
            and prices[0][1] is not None
            and Decimal(str(prices[0][0]))
                == Decimal(str(market["canonical_close_price_pct"]))
            and Decimal(str(prices[0][1]))
                == Decimal(str(market["accrued_interest"])),
            "Écart entre prix documentaire et CORE",
        )

    dirty_price = (
        face * Decimal(str(market["canonical_close_price_pct"]))
        / Decimal("100")
        + Decimal(str(market["accrued_interest"]))
    )
    require(dirty_price > 0, "Prix dirty invalide")

    horizon = date(2027, 9, 10)
    bond = BondCase(
        valuation_date=valuation,
        horizon_date=horizon,
        currency="RUB",
        dirty_price=dirty_price,
        remaining_principal=face,
        flows=tuple(flows),
        fixed_coupon_verified=True,
        complete_schedule_verified=True,
        primary_board_verified=True,
    )

    results = calculate_total_return(
        bond, annual_market_yields=("0.10", "0.125", "0.15")
    )
    require(len(results) == 3, "Nombre de scénarios inattendu")

    scenarios = []
    for result in results:
        rate = float(result.annual_market_yield)
        received = math.fsum(
            float(flow.amount) for flow in flows
            if flow.payment_date <= horizon
        )
        terminal = math.fsum(
            float(flow.amount)
            / (1.0 + rate) ** ((flow.payment_date - horizon).days / 365.0)
            for flow in flows
            if flow.payment_date > horizon
        )
        reference_return = (
            received + terminal - float(dirty_price)
        ) / float(dirty_price)

        require(
            abs(float(result.total_return) - reference_return) < 1e-10,
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
            "terminal_wealth_rub_per_bond": str(
                result.terminal_wealth
            ),
            "gross_total_return_decimal": str(
                result.total_return
            ),
        })

    payload = {
        "status": "EXPERIMENTAL",
        "instrument_isin": instrument["isin"],
        "valuation_date": valuation.isoformat(),
        "horizon_date": horizon.isoformat(),
        "document_observation_date": "2026-09-19",
        "historical_cashflow_availability": "NOT_PROVEN",
        "historical_backtest_validated": False,
        "price_basis": "MOEX_LEGALCLOSEPRICE_PLUS_ACCINT",
        "dirty_price_rub_per_bond": str(dirty_price),
        "source_json_sha256": document_hash,
        "coupon_count": len(coupons),
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

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Écriture atomique du seul résultat privé ; permissions propriétaire.
    temporary_name = None
    try:
        fd, temporary_name = tempfile.mkstemp(
            prefix=".ofz_26252_pilot_",
            suffix=".json",
            dir=OUTPUT.parent,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, OUTPUT)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)

    print("===== PILOTE REPRODUCTIBLE =====")
    print("Document et provenance : OK")
    print("Rapprochement CORE en lecture seule : OK")
    print("Trois scénarios et contrôle indépendant : OK")
    print("Résultat privé enregistré : OK")
    print("Statut : EXPERIMENTAL — disponibilité historique non prouvée")
    print("Aucune position, quantité, prix ou montant individuel affiché.")

if __name__ == "__main__":
    main()
