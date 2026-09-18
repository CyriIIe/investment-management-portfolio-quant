"""Offline tests for the Bank of Russia key-rate network client."""

import io
import unittest
import urllib.error
from datetime import date
from unittest.mock import patch

from portfolio_quant.cbr_key_rate_client import (
    MAX_RESPONSE_BYTES,
    fetch_key_rates,
)


FROM_DATE = date(2026, 9, 1)
TO_DATE = date(2026, 9, 18)


def soap(observation_date="2026-09-17"):
    return (
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/'
        'soap/envelope/">'
        "<soap:Body><KeyRateXMLResponse><KeyRateXMLResult>"
        "<KeyRate>"
        f"<KR><DT>{observation_date}T00:00:00+03:00</DT>"
        "<Rate>16.50</Rate></KR>"
        "</KeyRate>"
        "</KeyRateXMLResult></KeyRateXMLResponse></soap:Body>"
        "</soap:Envelope>"
    ).encode("utf-8")


class FakeResponse(io.BytesIO):
    def __init__(self, content, content_type="text/xml; charset=utf-8"):
        super().__init__(content)
        self.headers = {"Content-Type": content_type}


class CbrKeyRateClientTests(unittest.TestCase):
    def fetch(self):
        return fetch_key_rates(
            from_date=FROM_DATE,
            to_date=TO_DATE,
        )

    def test_valid_response_is_returned_unchanged(self):
        content = soap()

        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen",
            return_value=FakeResponse(content),
        ) as mocked:
            result = self.fetch()

        self.assertEqual(result, content)
        self.assertEqual(mocked.call_count, 1)

        request = mocked.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn(b"KeyRateXML", request.data)

    def test_invalid_date_range_is_rejected_before_network(self):
        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen"
        ) as mocked:
            with self.assertRaisesRegex(ValueError, "date range"):
                fetch_key_rates(
                    from_date=TO_DATE,
                    to_date=FROM_DATE,
                )

            mocked.assert_not_called()

    def test_invalid_timeout_is_rejected_before_network(self):
        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen"
        ) as mocked:
            with self.assertRaisesRegex(ValueError, "timeout"):
                fetch_key_rates(
                    from_date=FROM_DATE,
                    to_date=TO_DATE,
                    timeout=0,
                )

            mocked.assert_not_called()

    def test_non_xml_content_type_is_rejected(self):
        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen",
            return_value=FakeResponse(soap(), "text/html"),
        ):
            with self.assertRaisesRegex(ValueError, "non-XML"):
                self.fetch()

    def test_oversized_response_is_rejected(self):
        content = b"x" * (MAX_RESPONSE_BYTES + 1)

        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen",
            return_value=FakeResponse(content),
        ):
            with self.assertRaisesRegex(ValueError, "maximum size"):
                self.fetch()

    def test_invalid_xml_is_rejected(self):
        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen",
            return_value=FakeResponse(b"<invalid"),
        ):
            with self.assertRaises(ValueError):
                self.fetch()

    def test_observation_outside_requested_range_is_rejected(self):
        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen",
            return_value=FakeResponse(soap("2026-08-31")),
        ):
            with self.assertRaisesRegex(ValueError, "outside"):
                self.fetch()

    def test_network_error_is_propagated(self):
        with patch(
            "portfolio_quant.cbr_key_rate_client.urllib.request.urlopen",
            side_effect=urllib.error.URLError("simulated outage"),
        ):
            with self.assertRaises(urllib.error.URLError):
                self.fetch()


if __name__ == "__main__":
    unittest.main()
