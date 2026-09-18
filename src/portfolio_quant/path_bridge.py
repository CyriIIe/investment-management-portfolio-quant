"""Python bridge to Rust batch discounting of fictional rate paths.

One currency per invocation. Known coupons only; no portfolio valuation.
"""

import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATHS_BINARY = ROOT / "rust/quant_core/target/release/quant_paths"

MAX_COUPONS = 10_000
MAX_PATHS = 10_000
MAX_CALCULATIONS = 2_000_000


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


def discount_paths_rust(coupons, paths, *, binary_path=None):
    """Return one known-coupon present-value total per fictional rate path.

    coupons: sequence of (gross_amount, days_until_payment)
    paths: sequence of 13-observation annual-rate sequences

    All coupons must belong to the same currency. Currency grouping is
    the responsibility of the caller; this function does no conversion.
    """
    if not isinstance(coupons, (list, tuple)) or not coupons:
        raise ValueError("Provide a non-empty coupon sequence")

    if not isinstance(paths, (list, tuple)) or not paths:
        raise ValueError("Provide a non-empty path sequence")

    if (
        len(coupons) > MAX_COUPONS
        or len(paths) > MAX_PATHS
        or len(coupons) * len(paths) > MAX_CALCULATIONS
    ):
        raise ValueError("Path batch exceeds Rust limits")

    coupon_records = []

    for index, coupon in enumerate(coupons):
        if not isinstance(coupon, (list, tuple)) or len(coupon) != 2:
            raise ValueError(f"Coupon {index}: expected amount and days")

        amount = _decimal(coupon[0], f"coupon {index} amount")
        days = coupon[1]

        if amount < 0:
            raise ValueError(f"Coupon {index}: negative amount")

        if type(days) is not int or not 1 <= days <= 365:
            raise ValueError(f"Coupon {index}: days outside supported horizon")

        coupon_records.append(f"{amount},{days}\n")

    rate_records = []

    for path_index, path in enumerate(paths):
        if not isinstance(path, (list, tuple)) or len(path) != 13:
            raise ValueError(f"Path {path_index}: expected 13 observations")

        for rate_index, value in enumerate(path):
            rate = _decimal(value, f"path {path_index} rate {rate_index}")

            if not Decimal("0") <= rate <= Decimal("1"):
                raise ValueError(
                    f"Path {path_index} rate {rate_index}: outside supported range"
                )

            rate_records.append(f"{rate}\n")

    payload = (
        f"{len(coupons)},{len(paths)}\n"
        + "".join(rate_records)
        + "".join(coupon_records)
    )

    binary = Path(binary_path) if binary_path is not None else PATHS_BINARY

    if not binary.is_file():
        raise FileNotFoundError(
            "Rust executable missing; build quant_paths in release mode"
        )

    result = subprocess.run(
        [str(binary)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Rust path calculation failed (exit code {result.returncode})"
        )

    lines = result.stdout.splitlines()

    if len(lines) != len(paths):
        raise ValueError("Rust returned an unexpected number of path totals")

    totals = tuple(
        _decimal(line, "Rust path total")
        for line in lines
    )

    if any(total < 0 for total in totals):
        raise ValueError("Rust returned a negative path total")

    return totals
