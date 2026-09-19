"""Read-only, per-unit experimental pilot for the loopback dashboard."""

import hashlib
import json
from pathlib import Path

RESEARCH = (
    Path.home()
    / "investment-management-portfolio-quant-data"
    / "research"
)

RESULT = RESEARCH / "ofz_26252_pilot_results.json"
SOURCE = RESEARCH / "ofz_26252_2026-09-10.json"


def read_experimental_pilot() -> dict:
    """Expose only an already-validated pilot, never portfolio holdings."""
    result = json.loads(RESULT.read_text(encoding="utf-8"))

    if (
        result.get("status") != "EXPERIMENTAL"
        or result.get("historical_backtest_validated") is not False
        or result.get("historical_cashflow_availability") != "NOT_PROVEN"
        or result.get("core_read_only_reconciliation") != "PASSED"
        or result.get("independent_numerical_check") != "PASSED"
        or result.get("instrument_isin") != "RU000A10D4Y2"
        or result.get("valuation_date") != "2026-09-10"
        or result.get("horizon_date") != "2027-09-10"
        or result.get("document_observation_date") != "2026-09-19"
        or result.get("price_basis") != "MOEX_LEGALCLOSEPRICE_PLUS_ACCINT"
        or result.get("coupon_count") != 15
        or result.get("principal_reconciled") is not True
        or not isinstance(result.get("scenarios"), list)
        or len(result["scenarios"]) != 3
    ):
        raise ValueError("Experimental pilot has not passed validation")

    actual_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if result.get("source_json_sha256") != actual_hash:
        raise ValueError("Experimental pilot source has changed")

    assumptions = result.get("assumptions")
    if not isinstance(assumptions, dict) or any(
        assumptions.get(key) != "NOT_INCLUDED"
        for key in ("taxes", "fees", "reinvestment")
    ):
        raise ValueError("Unexpected pilot assumptions")

    scenarios = []
    expected_yields = ("0.10", "0.125", "0.15")

    for item, expected_yield in zip(
        result["scenarios"], expected_yields, strict=True
    ):
        if (
            not isinstance(item, dict)
            or item.get("hypothetical_annual_market_yield") != expected_yield
        ):
            raise ValueError("Unexpected experimental scenario")

        required = (
            "received_through_horizon_rub_per_bond",
            "theoretical_terminal_price_rub_per_bond",
            "terminal_wealth_rub_per_bond",
            "gross_total_return_decimal",
        )
        from decimal import Decimal

        for key in required:
            value = item.get(key)
            if not isinstance(value, str) or not Decimal(value).is_finite():
                raise ValueError("Invalid experimental scenario value")

        scenarios.append({
            "hypothetical_annual_market_yield": expected_yield,
            **{key: item[key] for key in required},
        })

    return {
        "status": "EXPERIMENTAL",
        "instrument_isin": result["instrument_isin"],
        "valuation_date": result["valuation_date"],
        "horizon_date": result["horizon_date"],
        "document_observation_date": result["document_observation_date"],
        "historical_cashflow_availability": "NOT_PROVEN",
        "historical_backtest_validated": False,
        "price_basis": result["price_basis"],
        "dirty_price_rub_per_bond": result["dirty_price_rub_per_bond"],
        "source_json_sha256": actual_hash,
        "coupon_count": 15,
        "assumptions": {
            "valuation": assumptions.get("valuation"),
            "taxes": "NOT_INCLUDED",
            "fees": "NOT_INCLUDED",
            "reinvestment": "NOT_INCLUDED",
            "default": assumptions.get("default"),
        },
        "scenarios": scenarios,
        "performance_measure": False,
        "portfolio_risk_measure": False,
    }
