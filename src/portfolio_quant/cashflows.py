"""Deterministic cash flows for a simple fixed-coupon bullet bond.

This initial module intentionally does not support floating coupons,
amortisation, embedded options or default events.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CashFlow:
    payment_date: date
    kind: str
    amount: Decimal


def fixed_bond_cashflows(
    *,
    valuation_date: date,
    maturity_date: date,
    coupon_dates: list[date],
    coupon_per_bond: Decimal,
    nominal_per_bond: Decimal,
    quantity: int,
) -> list[CashFlow]:
    """Return future coupon payments and principal repayment in RUB.

    Coupon dates and coupon amount must come from a verified bond schedule.
    Amounts are contractual gross cash flows, before tax and fees.
    """
    if maturity_date <= valuation_date:
        raise ValueError("Maturity must be after valuation date.")
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")
    if nominal_per_bond <= 0:
        raise ValueError("Nominal must be positive.")
    if coupon_per_bond < 0:
        raise ValueError("Coupon cannot be negative.")
    if len(coupon_dates) != len(set(coupon_dates)):
        raise ValueError("Duplicate coupon dates.")
    if coupon_dates != sorted(coupon_dates):
        raise ValueError("Coupon dates must be sorted.")
    if any(d > maturity_date for d in coupon_dates):
        raise ValueError("Coupon date after maturity.")

    flows = [
        CashFlow(
            payment_date=d,
            kind="coupon",
            amount=coupon_per_bond * quantity,
        )
        for d in coupon_dates
        if valuation_date < d <= maturity_date
    ]

    flows.append(
        CashFlow(
            payment_date=maturity_date,
            kind="principal",
            amount=nominal_per_bond * quantity,
        )
    )
    return sorted(flows, key=lambda flow: (flow.payment_date, flow.kind))
