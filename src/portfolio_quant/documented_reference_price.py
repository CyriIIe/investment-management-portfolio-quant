"""Explicit, offline reference-price conventions for documented bonds.

A missing ACCINT remains missing in source data. For a contractually
zero-coupon discount bond, the quotation-only convention uses the
MOEX closing percentage of face value, not an imputed ACCINT field.
This is not a broker execution or settlement price.
"""

from decimal import Decimal, InvalidOperation

from portfolio_quant.documented_bond_flows import DocumentedBondFlows


DISCOUNT_BASIS = "MOEX_DISCOUNT_CLOSE_NO_COUPON_ACCRUAL"
COUPON_BASIS = "MOEX_LEGALCLOSEPRICE_PLUS_ACCINT"


def _number(value, name):
    if value is None or isinstance(value, (bool, float)):
        raise ValueError(f"{name}: missing or invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name}: invalid") from exc
    if not number.is_finite():
        raise ValueError(f"{name}: non-finite")
    return number


def documented_reference_price(
    document: dict,
    validated: DocumentedBondFlows,
    *,
    core_close,
    core_accint,
) -> tuple[Decimal, str]:
    """Use only the verified MOEX closing quote and its applicable convention."""
    if not isinstance(document, dict) or not isinstance(
        validated, DocumentedBondFlows
    ):
        raise ValueError("Validated document required")

    instrument = document["instrument"]
    market = document["market_reference"]
    completeness = document["completeness"]

    if (
        instrument.get("isin") != validated.isin
        or instrument.get("coupon_type") != validated.coupon_type
        or market.get("status") != "VERIFIED"
        or market.get("board") != validated.primary_board
        or market.get("trade_date") != validated.valuation_date.isoformat()
        or market.get("canonical_close_price_field") != "LEGALCLOSEPRICE"
        or market.get("accrued_interest_field") != "ACCINT"
    ):
        raise ValueError("Market reference does not match documented bond")

    close = _number(market.get("canonical_close_price_pct"), "MOEX close")
    if close <= 0 or close > 1000:
        raise ValueError("MOEX close outside supported range")
    if core_close is None or _number(core_close, "CORE close") != close:
        raise ValueError("MOEX close does not reconcile with CORE")

    quoted = validated.face_value * close / Decimal("100")

    if validated.coupon_type == "DISCOUNT_NO_COUPON":
        if (
            instrument.get("coupon_frequency_per_year") != 0
            or instrument.get("coupon_rate_pct") is not None
            or document.get("cashflows") != []
            or any(flow.kind == "COUPON" for flow in validated.flows)
            or completeness.get("coupon_schedule_complete") is not True
            or completeness.get("coupon_count_post_valuation_date") != 0
            or market.get("accrued_interest") is not None
            or market.get("accrued_interest_status") != "MISSING"
            or core_accint is not None
        ):
            raise ValueError("Discount-bond quotation convention not proven")
        return quoted, DISCOUNT_BASIS

    accrued = _number(market.get("accrued_interest"), "MOEX ACCINT")
    if accrued < 0:
        raise ValueError("Negative accrued interest")
    if core_accint is None or _number(core_accint, "CORE ACCINT") != accrued:
        raise ValueError("MOEX ACCINT does not reconcile with CORE")
    return quoted + accrued, COUPON_BASIS
