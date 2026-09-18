"""Compact Python-to-Rust bridge for one-currency coupon scenarios."""

from decimal import Decimal, InvalidOperation
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
GRID_BINARY = ROOT / "rust/quant_core/target/release/quant_grid"
MAX_GRID_SIZE = 1_000_000


def _decimal(value, field):
    if value is None or isinstance(value, (float, bool)):
        raise ValueError(f"{field}: expected Decimal or decimal string")

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: invalid decimal") from exc

    if not number.is_finite():
        raise ValueError(f"{field}: non-finite decimal")

    return number


def discount_grid_rust(coupons, annual_rates, *, binary_path=None):
    """Return one total per rate for coupons belonging to ONE currency.

    coupons: sequence of (gross_amount, days_until_payment)
    annual_rates: sequence of decimal annual rates

    Experimental partial coupon valuation only.
    """
    if not isinstance(coupons, (list, tuple)) or not coupons:
        raise ValueError("Provide a non-empty coupon sequence")

    if not isinstance(annual_rates, (list, tuple)) or not annual_rates:
        raise ValueError("Provide a non-empty rate sequence")

    if len(coupons) * len(annual_rates) > MAX_GRID_SIZE:
        raise ValueError("Scenario grid exceeds maximum size")

    rates = []

    for index, value in enumerate(annual_rates):
        rate = _decimal(value, f"rate {index}")

        if not Decimal("0") <= rate <= Decimal("1"):
            raise ValueError(f"Rate {index}: outside supported range")

        rates.append(rate)

    records = []

    for index, coupon in enumerate(coupons):
        if not isinstance(coupon, (list, tuple)) or len(coupon) != 2:
            raise ValueError(f"Coupon {index}: expected amount and days")

        amount = _decimal(coupon[0], f"coupon {index} amount")
        days = coupon[1]

        if amount < 0:
            raise ValueError(f"Coupon {index}: negative amount")

        if type(days) is not int or not 1 <= days <= 365:
            raise ValueError(f"Coupon {index}: days outside supported horizon")

        records.append(f"{amount},{days}\n")

    payload = (
        f"{len(records)},{len(rates)}\n"
        + "".join(f"{rate}\n" for rate in rates)
        + "".join(records)
    )

    binary = Path(binary_path) if binary_path is not None else GRID_BINARY

    if not binary.is_file():
        raise FileNotFoundError(
            "Compact Rust executable missing; build quant_grid in release mode"
        )

    result = subprocess.run(
        [str(binary)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Rust grid calculation failed (exit code {result.returncode})"
        )

    lines = result.stdout.splitlines()

    if len(lines) != len(rates):
        raise ValueError("Rust returned an unexpected number of scenario totals")

    totals = tuple(
        _decimal(line, "Rust scenario total")
        for line in lines
    )

    if any(total < 0 for total in totals):
        raise ValueError("Rust returned a negative scenario total")

    return totals
