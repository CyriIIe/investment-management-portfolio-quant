"""Tests for the pure Bank of Russia KeyRateXML parser."""

import unittest
from decimal import Decimal
from xml.sax.saxutils import escape

from portfolio_quant.cbr_key_rate import parse_key_rate_xml


def soap(records, *, escaped=False):
    data = "<KeyRate>" + "".join(records) + "</KeyRate>"
    content = escape(data) if escaped else data

    return (
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/'
        'soap/envelope/">'
        "<soap:Body>"
        "<KeyRateXMLResponse>"
        f"<KeyRateXMLResult>{content}</KeyRateXMLResult>"
        "</KeyRateXMLResponse>"
        "</soap:Body>"
        "</soap:Envelope>"
    )


def observation(timestamp, rate):
    return (
        "<KR>"
        f"<DT>{timestamp}</DT>"
        f"<Rate>{rate}</Rate>"
        "</KR>"
    )


class CbrKeyRateTests(unittest.TestCase):
    def test_valid_observations_are_sorted_and_converted(self):
        payload = soap([
            observation("2026-09-18T00:00:00+03:00", "16.50"),
            observation("2026-09-17T00:00:00+03:00", "16.75"),
        ])

        result = parse_key_rate_xml(payload)

        self.assertEqual(len(result), 2)
        self.assertEqual(
            result[0].effective_date.isoformat(), "2026-09-17"
        )
        self.assertEqual(result[0].rate_percent, Decimal("16.75"))
        self.assertEqual(result[0].rate_fraction, Decimal("0.1675"))
        self.assertEqual(
            result[1].source_timestamp.utcoffset().total_seconds(),
            3 * 3600,
        )

    def test_escaped_xml_result_is_supported(self):
        payload = soap(
            [observation("2026-09-18T00:00:00+03:00", "16,50")],
            escaped=True,
        )

        result = parse_key_rate_xml(payload)

        self.assertEqual(result[0].rate_percent, Decimal("16.50"))

    def test_timezone_is_required(self):
        payload = soap([
            observation("2026-09-18T00:00:00", "16.50"),
        ])

        with self.assertRaisesRegex(ValueError, "timezone"):
            parse_key_rate_xml(payload)

    def test_invalid_rates_are_rejected(self):
        for rate in ("NaN", "Infinity", "-1", "101", "invalid"):
            with self.subTest(rate=rate):
                payload = soap([
                    observation("2026-09-18T00:00:00+03:00", rate),
                ])

                with self.assertRaises(ValueError):
                    parse_key_rate_xml(payload)

    def test_duplicate_dates_are_rejected(self):
        payload = soap([
            observation("2026-09-18T00:00:00+03:00", "16.50"),
            observation("2026-09-18T12:00:00+03:00", "16.75"),
        ])

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_key_rate_xml(payload)

    def test_soap_fault_is_rejected(self):
        payload = (
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/'
            'soap/envelope/">'
            "<soap:Body><soap:Fault>"
            "<faultcode>soap:Server</faultcode>"
            "</soap:Fault></soap:Body>"
            "</soap:Envelope>"
        )

        with self.assertRaisesRegex(ValueError, "fault"):
            parse_key_rate_xml(payload)

    def test_missing_result_is_rejected(self):
        payload = (
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/'
            'soap/envelope/"><soap:Body/></soap:Envelope>'
        )

        with self.assertRaisesRegex(ValueError, "KeyRateXMLResult"):
            parse_key_rate_xml(payload)


if __name__ == "__main__":
    unittest.main()
