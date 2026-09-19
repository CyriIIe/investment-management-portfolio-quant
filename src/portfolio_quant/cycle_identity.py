"""Stable identity for an explicitly experimental Quant calculation."""

import hashlib
import json
from decimal import Decimal, InvalidOperation


IDENTITY_VERSION = 1


def _digest(value, name):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name}: expected lowercase SHA-256")
    return value


def _decimal(value, name):
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError(f"{name}: expected a decimal string")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name}: invalid decimal") from exc
    if not result.is_finite() or not Decimal("0") <= result <= Decimal("1"):
        raise ValueError(f"{name}: outside supported range")
    return format(result.normalize(), "f")


def cycle_identity(
    *,
    positions_sha256,
    cashflow_input_sha256,
    cashflow_result_sha256,
    cashflow_policy_sha256,
    rust_binary_sha256,
    initial_rate,
    monthly_volatility,
    months,
    path_count,
    seed,
):
    """Return a deterministic SHA-256; no IO, market calibration or writes."""
    if type(months) is not int or months != 12:
        raise ValueError("Expected 12 monthly intervals")
    if type(path_count) is not int or not 1 <= path_count <= 10_000:
        raise ValueError("Invalid path count")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("Invalid seed")

    payload = {
        "identity_version": IDENTITY_VERSION,
        "model": "fictional-known-coupon-paths",
        "positions_sha256": _digest(positions_sha256, "positions"),
        "cashflow_input_sha256": _digest(
            cashflow_input_sha256, "cashflow input"
        ),
        "cashflow_result_sha256": _digest(
            cashflow_result_sha256, "cashflow result"
        ),
        "cashflow_policy_sha256": _digest(
            cashflow_policy_sha256, "cashflow policy"
        ),
        "rust_binary_sha256": _digest(rust_binary_sha256, "Rust binary"),
        "initial_rate": _decimal(initial_rate, "initial rate"),
        "monthly_volatility": _decimal(
            monthly_volatility, "monthly volatility"
        ),
        "months": months,
        "path_count": path_count,
        "seed": seed,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
