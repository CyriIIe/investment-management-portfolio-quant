"""Fetch official Bank of Russia key-rate observations.

Network client only. No database access, filesystem writes, or CORE access.
"""

from datetime import date
import urllib.request

from portfolio_quant.cbr_key_rate import (
    SOURCE_URL,
    parse_key_rate_xml,
)


MAX_RESPONSE_BYTES = 2_000_000


def fetch_key_rates(
    *,
    from_date: date,
    to_date: date,
    timeout: int = 20,
) -> bytes:
    """Download and validate a bounded KeyRateXML SOAP response."""
    if (
        type(from_date) is not date
        or type(to_date) is not date
        or from_date > to_date
    ):
        raise ValueError("Invalid requested date range")

    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise ValueError("Invalid network timeout")

    payload = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <KeyRateXML xmlns="http://web.cbr.ru/">
      <fromDate>{from_date.isoformat()}T00:00:00</fromDate>
      <ToDate>{to_date.isoformat()}T00:00:00</ToDate>
    </KeyRateXML>
  </soap:Body>
</soap:Envelope>""".encode("utf-8")

    request = urllib.request.Request(
        SOURCE_URL,
        data=payload,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"http://web.cbr.ru/KeyRateXML"',
            "User-Agent": "PortfolioQuant/0.1",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").lower()

        if "xml" not in content_type:
            raise ValueError("CBR returned a non-XML content type")

        content = response.read(MAX_RESPONSE_BYTES + 1)

    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("CBR response exceeds maximum size")

    observations = parse_key_rate_xml(content)

    if any(
        not from_date <= item.effective_date <= to_date
        for item in observations
    ):
        raise ValueError("CBR observation outside requested date range")

    return content
