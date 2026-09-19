"""Expose only documented, archived experimental per-bond results."""

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from portfolio_quant.web_experimental_pilot import (
    RESEARCH,
    read_experimental_pilot,
)


GTLK_SOURCE = RESEARCH / "gtlk_002p_13_2026-09-10.json"
GTLK_RESULT = RESEARCH / "gtlk_002p_13_pilot_results.json"

SCENARIO_FIELDS = (
    "received_through_horizon_rub_per_bond",
    "theoretical_terminal_price_rub_per_bond",
    "terminal_wealth_rub_per_bond",
    "gross_total_return_decimal",
)
EXPECTED_YIELDS = ("0.10", "0.125", "0.15")


def _decimal_string(value, field):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field}: missing decimal string")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: invalid decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{field}: non-finite decimal")
    return number


def _read_private_json(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Private research file missing or unsafe")
    return path.read_bytes()


def _read_gtlk():
    raw_source = _read_private_json(GTLK_SOURCE)
    raw_result = _read_private_json(GTLK_RESULT)

    source = json.loads(raw_source, parse_float=Decimal)
    result = json.loads(raw_result)
    source_hash = hashlib.sha256(raw_source).hexdigest()

    if (
        not isinstance(source, dict)
        or not isinstance(source.get("instrument"), dict)
        or not isinstance(source.get("completeness"), dict)
        or not isinstance(result, dict)
    ):
        raise ValueError("Malformed GTLK research document or result")

    if (
        source["instrument"].get("isin") != "RU000A10F801"
        or source["instrument"].get("coupon_type") != "FIXED_AMORTIZING"
        or source.get("valuation_date") != "2026-09-10"
        or source["instrument"].get("source_observation_date") != "2026-09-19"
        or source["completeness"].get(
            "as_of_2026_09_10_schedule_publication_proven"
        ) is not False
    ):
        raise ValueError("Unexpected GTLK source")

    if (
        result.get("status") != "EXPERIMENTAL"
        or result.get("instrument_isin") != "RU000A10F801"
        or result.get("coupon_type") != "FIXED_AMORTIZING"
        or result.get("valuation_date") != "2026-09-10"
        or result.get("horizon_date") != "2027-09-10"
        or result.get("document_observation_date") != "2026-09-19"
        or result.get("historical_cashflow_availability") != "NOT_PROVEN"
        or result.get("historical_backtest_validated") is not False
        or result.get("price_basis") != "MOEX_LEGALCLOSEPRICE_PLUS_ACCINT"
        or result.get("source_json_sha256") != source_hash
        or result.get("coupon_count") != 45
        or result.get("principal_event_count") != 5
        or result.get("principal_reconciled") is not True
        or result.get("core_read_only_reconciliation") != "PASSED"
        or result.get("independent_numerical_check") != "PASSED"
        or not isinstance(result.get("scenarios"), list)
        or len(result["scenarios"]) != 3
    ):
        raise ValueError("GTLK result has not passed validation")

    assumptions = result.get("assumptions")
    if (
        not isinstance(assumptions, dict)
        or any(
            assumptions.get(key) != "NOT_INCLUDED"
            for key in ("taxes", "fees", "reinvestment")
        )
        or assumptions.get("default") != "NOT_MODELED"
        or assumptions.get("market_yields_are_forecasts") is not False
        or assumptions.get("price_is_broker_execution_price") is not False
    ):
        raise ValueError("Unexpected GTLK assumptions")

    # Verify the archived result against the documented amounts rather
    # than relying solely on its self-reported validation flags.
    from portfolio_quant.deterministic_total_return import (
        calculate_total_return,
    )
    from portfolio_quant.documented_bond_flows import (
        build_bond_case,
        parse_documented_bond_flows,
    )
    from datetime import date

    documented = parse_documented_bond_flows(source)
    price = _decimal_string(
        result.get("dirty_price_rub_per_bond"), "dirty price"
    )
    if price <= 0:
        raise ValueError("Invalid dirty price")

    market = source["market_reference"]
    if market.get("accrued_interest") is None:
        raise ValueError("Missing GTLK accrued interest")
    expected_price = (
        documented.face_value
        * Decimal(str(market["canonical_close_price_pct"]))
        / Decimal("100")
        + Decimal(str(market["accrued_interest"]))
    )
    if price != expected_price:
        raise ValueError("GTLK price differs from documentary reference")

    bond = build_bond_case(
        documented,
        horizon_date=date(2027, 9, 10),
        verified_dirty_price=price,
    )
    calculated = calculate_total_return(
        bond, annual_market_yields=EXPECTED_YIELDS
    )

    scenarios = []
    for item, expected_yield, computed in zip(
        result["scenarios"], EXPECTED_YIELDS, calculated, strict=True
    ):
        if (
            not isinstance(item, dict)
            or item.get("hypothetical_annual_market_yield") != expected_yield
        ):
            raise ValueError("Unexpected GTLK yield scenario")

        actual = {
            key: _decimal_string(item.get(key), key)
            for key in SCENARIO_FIELDS
        }
        reference = {
            "received_through_horizon_rub_per_bond":
                computed.received_before_or_on_horizon,
            "theoretical_terminal_price_rub_per_bond":
                computed.theoretical_terminal_price,
            "terminal_wealth_rub_per_bond": computed.terminal_wealth,
            "gross_total_return_decimal": computed.total_return,
        }
        if actual != reference:
            raise ValueError("GTLK archived scenario differs from calculation")

        scenarios.append({
            "hypothetical_annual_market_yield": expected_yield,
            **{key: item[key] for key in SCENARIO_FIELDS},
        })

    received_coupon = sum(
        (flow.amount for flow in documented.flows
         if flow.kind == "COUPON"
         and flow.payment_date <= bond.horizon_date),
        Decimal("0"),
    )
    received_principal = sum(
        (flow.amount for flow in documented.flows
         if flow.kind == "PRINCIPAL"
         and flow.payment_date <= bond.horizon_date),
        Decimal("0"),
    )

    if received_coupon + received_principal != (
        calculated[0].received_before_or_on_horizon
    ):
        raise ValueError("Received cashflow breakdown does not reconcile")

    return {
        "status": "EXPERIMENTAL",
        "instrument_isin": documented.isin,
        "instrument_label": "GTLK 002P-13",
        "coupon_type": "FIXED_AMORTIZING",
        "valuation_date": result["valuation_date"],
        "horizon_date": result["horizon_date"],
        "document_observation_date": result["document_observation_date"],
        "historical_cashflow_availability": "NOT_PROVEN",
        "historical_backtest_validated": False,
        "price_basis": result["price_basis"],
        "dirty_price_rub_per_bond": result["dirty_price_rub_per_bond"],
        "coupon_count": 45,
        "principal_event_count": 5,
        "received_coupon_rub_per_bond": str(received_coupon),
        "received_principal_rub_per_bond": str(received_principal),
        "scenarios": scenarios,
        "performance_measure": False,
        "portfolio_risk_measure": False,
    }


def read_experimental_pilots() -> dict:
    """Both instruments must validate before either is exposed."""
    ofz = read_experimental_pilot()
    gtlk = _read_gtlk()

    if (
        ofz["instrument_isin"] != "RU000A10D4Y2"
        or ofz["status"] != "EXPERIMENTAL"
        or ofz["historical_backtest_validated"] is not False
    ):
        raise ValueError("Unexpected OFZ pilot")

    ofz = {
        **ofz,
        "instrument_label": "OFZ 26252",
        "coupon_type": "FIXED_KNOWN",
        "principal_event_count": 1,
        "received_coupon_rub_per_bond":
            ofz["scenarios"][0]["received_through_horizon_rub_per_bond"],
        "received_principal_rub_per_bond": "0",
    }

    return {
        "status": "EXPERIMENTAL",
        "instruments": [ofz, gtlk],
        "historical_backtest_validated": False,
        "portfolio_risk_measure": False,
    }
