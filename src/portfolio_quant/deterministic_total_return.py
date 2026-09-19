"""Offline, synthetic deterministic bond scenarios; no CORE I/O."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class BondFlow:
    payment_date: date
    kind: str
    amount: Decimal


@dataclass(frozen=True)
class BondCase:
    valuation_date: date
    horizon_date: date
    currency: str
    dirty_price: Decimal
    remaining_principal: Decimal
    flows: tuple[BondFlow, ...]
    fixed_coupon_verified: bool
    complete_schedule_verified: bool
    primary_board_verified: bool


@dataclass(frozen=True)
class ScenarioResult:
    annual_market_yield: Decimal
    received_before_or_on_horizon: Decimal
    theoretical_terminal_price: Decimal
    terminal_wealth: Decimal
    total_return: Decimal


def _decimal(value, field: str) -> Decimal:
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError(f"{field}: expected a decimal string or Decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field}: invalid decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field}: non-finite decimal")
    return result


def calculate_total_return(
    bond: BondCase,
    *,
    annual_market_yields,
) -> tuple[ScenarioResult, ...]:
    """Return conditional one-horizon results, not trading decisions.

    Cash received by horizon is not reinvested. Remaining contractual
    flows are discounted at a hypothetical flat market yield using
    annual compounding and ACT/365. No taxes, fees or default.
    """
    if not isinstance(bond, BondCase):
        raise ValueError("Expected a BondCase")

    if (
        bond.fixed_coupon_verified is not True
        or bond.complete_schedule_verified is not True
        or bond.primary_board_verified is not True
    ):
        raise ValueError("Eligibility or complete schedule not verified")

    if (
        not isinstance(bond.valuation_date, date)
        or not isinstance(bond.horizon_date, date)
        or bond.horizon_date <= bond.valuation_date
    ):
        raise ValueError("Invalid valuation dates")

    if not isinstance(bond.currency, str) or len(bond.currency) != 3:
        raise ValueError("Invalid currency")

    dirty = _decimal(bond.dirty_price, "dirty price")
    principal = _decimal(bond.remaining_principal, "remaining principal")
    if dirty <= 0 or principal <= 0:
        raise ValueError("Price and remaining principal must be positive")

    if not isinstance(bond.flows, tuple) or not bond.flows:
        raise ValueError("No contractual flows")

    principal_sum = Decimal("0")
    checked_flows = []

    for flow in bond.flows:
        if not isinstance(flow, BondFlow):
            raise ValueError("Invalid flow")
        if (
            not isinstance(flow.payment_date, date)
            or flow.payment_date <= bond.valuation_date
        ):
            raise ValueError("Flow outside valuation period")
        if flow.kind not in {"COUPON", "PRINCIPAL"}:
            raise ValueError("Unsupported or conditional flow")

        amount = _decimal(flow.amount, "flow amount")
        if amount <= 0:
            raise ValueError("Flow amount must be positive")
        if flow.kind == "PRINCIPAL":
            principal_sum += amount
        checked_flows.append((flow.payment_date, amount))

    if principal_sum != principal:
        raise ValueError("Principal schedule does not match remaining principal")

    if not any(day >= bond.horizon_date for day, _ in checked_flows):
        raise ValueError("Horizon extends beyond all contractual flows")

    if not isinstance(annual_market_yields, (tuple, list)):
        raise ValueError("Expected scenario yields")

    rates = tuple(
        _decimal(rate, "annual market yield")
        for rate in annual_market_yields
    )
    if not rates or len(rates) != len(set(rates)):
        raise ValueError("Empty or duplicate scenarios")
    if any(rate < 0 or rate > 1 for rate in rates):
        raise ValueError("Scenario yield outside supported range")

    received = sum(
        (amount for day, amount in checked_flows
         if day <= bond.horizon_date),
        Decimal("0"),
    )

    results = []
    for rate in rates:
        terminal = sum(
            (
                amount / (
                    (Decimal("1") + rate)
                    ** (Decimal((day - bond.horizon_date).days)
                        / Decimal("365"))
                )
                for day, amount in checked_flows
                if day > bond.horizon_date
            ),
            Decimal("0"),
        )
        wealth = received + terminal
        results.append(
            ScenarioResult(
                annual_market_yield=rate,
                received_before_or_on_horizon=received,
                theoretical_terminal_price=terminal,
                terminal_wealth=wealth,
                total_return=(wealth - dirty) / dirty,
            )
        )

    return tuple(results)
