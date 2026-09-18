"""Reproducible fictional rate paths for numerical R&D only."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from random import Random


@dataclass(frozen=True)
class RatePathSimulation:
    seed: int
    initial_rate: Decimal
    monthly_volatility: Decimal
    months: int
    paths: tuple[tuple[Decimal, ...], ...]
    calibrated_to_market: bool = False
    portfolio_risk_measure: bool = False


def _decimal(value, name: str) -> Decimal:
    if value is None or isinstance(value, (float, bool)):
        raise ValueError(f"{name}: expected Decimal or decimal string")

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name}: invalid decimal") from exc

    if not number.is_finite():
        raise ValueError(f"{name}: non-finite decimal")

    return number


def generate_rate_paths(
    *,
    initial_rate,
    monthly_volatility,
    months: int,
    path_count: int,
    seed: int,
) -> RatePathSimulation:
    """Generate illustrative monthly flat-rate paths.

    Independent Gaussian monthly changes; not a calibrated rate model.
    Paths outside the supported 0–100% range are rejected, not clipped.
    Each path includes its initial rate followed by monthly observations.
    """
    initial = _decimal(initial_rate, "initial rate")
    volatility = _decimal(monthly_volatility, "monthly volatility")

    if not Decimal("0") <= initial <= Decimal("1"):
        raise ValueError("Initial rate outside supported range")

    if not Decimal("0") <= volatility <= Decimal("1"):
        raise ValueError("Monthly volatility outside supported range")

    if type(months) is not int or not 1 <= months <= 120:
        raise ValueError("Months must be between 1 and 120")

    if type(path_count) is not int or not 1 <= path_count <= 10_000:
        raise ValueError("Path count must be between 1 and 10000")

    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("Seed must be a non-negative 64-bit integer")

    rng = Random(seed)
    paths = []

    for path_index in range(path_count):
        current = initial
        observations = [current]

        for month_index in range(months):
            change = Decimal(
                str(rng.gauss(0.0, float(volatility)))
            )
            current += change

            if not Decimal("0") <= current <= Decimal("1"):
                raise ValueError(
                    "Generated rate outside supported range "
                    f"(path {path_index}, month {month_index + 1}); "
                    "change the fictional parameters"
                )

            observations.append(current)

        paths.append(tuple(observations))

    return RatePathSimulation(
        seed=seed,
        initial_rate=initial,
        monthly_volatility=volatility,
        months=months,
        paths=tuple(paths),
    )
