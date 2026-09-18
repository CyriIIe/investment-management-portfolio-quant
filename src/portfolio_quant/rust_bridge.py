"""Call the experimental Rust discounting executable from Python."""

from decimal import Decimal, InvalidOperation
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
RUST_BINARY = ROOT / "rust/quant_core/target/release/quant_batch"
MAX_COUPONS = 1_000_000


def _decimal(value, field):
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError(f"{field}: expected Decimal or decimal string")

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: invalid decimal") from exc

    if not number.is_finite():
        raise ValueError(f"{field}: non-finite decimal")

    return number


def discount_batch_rust(coupons, *, binary_path=None):
    """Return one discounted value per (amount, days, annual_rate).

    This interface performs experimental calculations, not bond valuation.
    """
    if not isinstance(coupons, (list, tuple)):
        raise ValueError("Coupons must be a list or tuple")

    if len(coupons) > MAX_COUPONS:
        raise ValueError("Batch exceeds maximum size")

    records = []

    for index, coupon in enumerate(coupons):
        if not isinstance(coupon, (list, tuple)) or len(coupon) != 3:
            raise ValueError(f"Coupon {index}: expected three fields")

        amount = _decimal(coupon[0], "amount")
        days = coupon[1]
        rate = _decimal(coupon[2], "annual rate")

        if amount < 0:
            raise ValueError(f"Coupon {index}: negative amount")

        if type(days) is not int or not 1 <= days <= 365:
            raise ValueError(f"Coupon {index}: days outside supported horizon")

        if not Decimal("0") <= rate <= Decimal("1"):
            raise ValueError(f"Coupon {index}: invalid annual rate")

        records.append(f"{amount},{days},{rate}\n")

    binary = Path(binary_path) if binary_path is not None else RUST_BINARY

    if not binary.is_file():
        raise FileNotFoundError(
            "Rust executable missing; build quant_batch in release mode"
        )

    result = subprocess.run(
        [str(binary)],
        input="".join(records),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Rust batch calculation failed (exit code {result.returncode})"
        )

    lines = result.stdout.splitlines()

    if len(lines) != len(records):
        raise ValueError("Rust returned an unexpected number of results")

    values = tuple(_decimal(line, "Rust result") for line in lines)

    if any(value < 0 for value in values):
        raise ValueError("Rust returned a negative present value")

    return values
