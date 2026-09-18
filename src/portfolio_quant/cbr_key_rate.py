"""Parse official Bank of Russia KeyRateXML SOAP observations.

Pure parser: no network access, database writes, or coupon projections.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET


SOURCE_URL = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
SOURCE_METHOD = "KeyRateXML"


@dataclass(frozen=True)
class KeyRateObservation:
    effective_date: date
    source_timestamp: datetime
    rate_percent: Decimal
    rate_fraction: Decimal


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_key_rate_xml(
    xml_content: bytes | str,
) -> tuple[KeyRateObservation, ...]:
    """Parse a successful KeyRateXML SOAP response.

    Dates are preserved in the source's local timezone.
    Rates are returned both as percentage points and decimal fractions.
    """
    if not isinstance(xml_content, (bytes, str)) or not xml_content:
        raise ValueError("Expected non-empty SOAP XML")

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise ValueError("Invalid SOAP XML") from exc

    if _local_name(root.tag) != "Envelope":
        raise ValueError("Expected SOAP Envelope")

    if any(
        _local_name(element.tag) == "Fault"
        for element in root.iter()
    ):
        raise ValueError("SOAP service returned a fault")

    results = [
        element
        for element in root.iter()
        if _local_name(element.tag) == "KeyRateXMLResult"
    ]

    if len(results) != 1:
        raise ValueError("Expected exactly one KeyRateXMLResult")

    result = results[0]

    if len(result):
        data_root = result[0]
    elif result.text and result.text.strip():
        try:
            data_root = ET.fromstring(result.text.strip())
        except ET.ParseError as exc:
            raise ValueError("Invalid embedded KeyRate XML") from exc
    else:
        raise ValueError("Empty KeyRateXMLResult")

    if _local_name(data_root.tag) != "KeyRate":
        raise ValueError("Unexpected key-rate data root")

    records = [
        element
        for element in data_root
        if _local_name(element.tag) == "KR"
    ]

    if not records:
        raise ValueError("No key-rate observations")

    observations = []
    seen_dates = set()

    for index, record in enumerate(records):
        fields = {
            _local_name(child.tag): child.text
            for child in record
        }

        try:
            timestamp = datetime.fromisoformat(fields["DT"])
            rate_percent = Decimal(
                fields["Rate"].replace(",", ".")
            )
        except (
            KeyError,
            AttributeError,
            TypeError,
            ValueError,
            InvalidOperation,
        ) as exc:
            raise ValueError(
                f"Observation {index}: invalid date or rate"
            ) from exc

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(
                f"Observation {index}: timezone required"
            )

        if (
            not rate_percent.is_finite()
            or not Decimal("0") <= rate_percent <= Decimal("100")
        ):
            raise ValueError(
                f"Observation {index}: rate outside supported range"
            )

        effective_date = timestamp.date()

        if effective_date in seen_dates:
            raise ValueError("Duplicate key-rate observation date")

        seen_dates.add(effective_date)

        observations.append(
            KeyRateObservation(
                effective_date=effective_date,
                source_timestamp=timestamp,
                rate_percent=rate_percent,
                rate_fraction=rate_percent / Decimal("100"),
            )
        )

    return tuple(
        sorted(observations, key=lambda item: item.effective_date)
    )
