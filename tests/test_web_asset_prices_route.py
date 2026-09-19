"""Offline HTTP routing tests using fictional asset-price data."""

import unittest
from unittest.mock import Mock, patch

from portfolio_quant import web_api


class AssetPricesRouteTests(unittest.TestCase):
    def make_handler(self, *, host="127.0.0.1:8765"):
        handler = object.__new__(web_api.DashboardHandler)
        handler.headers = {"Host": host}
        handler.path = "/api/asset-prices"
        handler._respond = Mock()
        return handler

    def test_asset_prices_route_returns_reader_result(self):
        fictional = {
            "as_of_date": "2026-09-10",
            "assets": [],
            "performance_measure": False,
            "portfolio_risk_measure": False,
        }
        handler = self.make_handler()

        with patch.object(
            web_api, "read_asset_prices", return_value=fictional
        ) as reader:
            handler.do_GET()

        reader.assert_called_once_with()
        handler._respond.assert_called_once_with(200, fictional)

    def test_asset_prices_route_rejects_other_host(self):
        handler = self.make_handler(host="example.invalid:8765")

        with patch.object(web_api, "read_asset_prices") as reader:
            handler.do_GET()

        reader.assert_not_called()
        handler._respond.assert_called_once_with(
            403, {"error": "Forbidden"}
        )


if __name__ == "__main__":
    unittest.main()
