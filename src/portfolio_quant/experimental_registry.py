"""Explicit allowlist for documentary experimental pilots.

Adding an entry does not bypass the instrument-specific source and
result validation performed by its reader.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PilotRegistration:
    isin: str
    label: str
    coupon_type: str
    reader_name: str


PILOT_REGISTRY = (
    PilotRegistration(
        isin="RU000A10D4Y2",
        label="OFZ 26252",
        coupon_type="FIXED_KNOWN",
        reader_name="ofz",
    ),
    PilotRegistration(
        isin="RU000A10F801",
        label="GTLK 002P-13",
        coupon_type="FIXED_AMORTIZING",
        reader_name="gtlk",
    ),
)


def validate_registry(registry=PILOT_REGISTRY):
    if not registry:
        raise ValueError("Empty experimental pilot registry")

    isins = [entry.isin for entry in registry]
    names = [entry.reader_name for entry in registry]

    if len(isins) != len(set(isins)):
        raise ValueError("Duplicate instrument in pilot registry")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate reader in pilot registry")

    for entry in registry:
        if (
            not isinstance(entry, PilotRegistration)
            or len(entry.isin) != 12
            or not entry.label.strip()
            or not entry.coupon_type.strip()
            or not entry.reader_name.strip()
        ):
            raise ValueError("Invalid experimental pilot registration")

    return registry
