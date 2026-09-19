"""Offline tests for the local dashboard HTTP handler."""

import unittest
from unittest.mock import Mock, patch

from portfolio_quant import web_api


class WebApiTests(unittest.TestCase):
    def make_handler(self, *, host="127.0.0.1:8765", path="/api/overview"):
        # Construct a handler without opening a network socket.
        handler = object.__new__(web_api.DashboardHandler)
        handler.headers = {"Host": host}
        handler.path = path
        handler._respond = Mock()
        return handler

    def test_overview_returns_aggregates(self):
        expected = {
            "cycles": {"count": 1},
            "key_rates": {"observation_count": 33},
            "model": {"calibrated_to_market": False},
        }
        handler = self.make_handler()

        with patch.object(web_api, "read_overview", return_value=expected) as read:
            handler.do_GET()

        read.assert_called_once_with()
        handler._respond.assert_called_once_with(200, expected)

    def test_cycles_route_returns_metadata_only(self):
        expected = {
            "total": 1,
            "cycles": [{
                "identity_prefix": "a" * 16,
                "created_at_utc": "2026-09-19T07:00:00+00:00",
                "model_name": "fictional-known-coupon-paths",
                "calibrated_to_market": False,
                "complete_portfolio_valuation": False,
                "portfolio_risk_measure": False,
            }],
        }
        handler = self.make_handler(path="/api/cycles")

        with patch.object(web_api, "read_cycles", return_value=expected) as read:
            handler.do_GET()

        read.assert_called_once_with()
        handler._respond.assert_called_once_with(200, expected)

    def test_rates_route_returns_observations(self):
        expected = {
            "total": 1,
            "observations": [{
                "effective_date": "2026-09-18",
                "rate_percent": "16.00",
                "collected_at_utc": "2026-09-19T07:00:00+00:00",
            }],
        }
        handler = self.make_handler(path="/api/rates")

        with patch.object(web_api, "read_rates", return_value=expected) as read:
            handler.do_GET()

        read.assert_called_once_with()
        handler._respond.assert_called_once_with(200, expected)

    def test_weather_route_returns_descriptive_aggregates(self):
        expected = {
            "portfolio_date": "2026-09-10",
            "position_count": 2,
            "complete_cashflows": False,
            "portfolio_risk_measure": False,
        }
        handler = self.make_handler(path="/api/weather")

        with patch.object(
            web_api, "read_weather", return_value=expected
        ) as read:
            handler.do_GET()

        read.assert_called_once_with()
        handler._respond.assert_called_once_with(200, expected)

    def test_weather_failure_does_not_expose_exception(self):
        handler = self.make_handler(path="/api/weather")

        with patch.object(
            web_api,
            "read_weather",
            side_effect=RuntimeError("private CORE details"),
        ):
            handler.do_GET()

        handler._respond.assert_called_once_with(
            503, {"error": "Overview unavailable"}
        )

    def test_changes_route_returns_aggregates(self):
        expected = {
            "previous_date": "2026-09-09",
            "current_date": "2026-09-10",
            "added_count": 1,
            "performance_measure": False,
            "portfolio_risk_measure": False,
        }
        handler = self.make_handler(path="/api/changes")

        with patch.object(
            web_api, "read_changes", return_value=expected
        ) as read:
            handler.do_GET()

        read.assert_called_once_with()
        handler._respond.assert_called_once_with(200, expected)

    def test_changes_failure_does_not_expose_exception(self):
        handler = self.make_handler(path="/api/changes")

        with patch.object(
            web_api,
            "read_changes",
            side_effect=RuntimeError("private CORE details"),
        ):
            handler.do_GET()

        handler._respond.assert_called_once_with(
            503, {"error": "Overview unavailable"}
        )

    def test_homepage_uses_compiled_files(self):
        handler = self.make_handler(path="/")
        handler._respond_static = Mock()

        with patch.object(
            web_api,
            "read_static",
            return_value=("text/html", b"<h1>Quant</h1>"),
        ) as read:
            handler.do_GET()

        read.assert_called_once_with("/")
        handler._respond_static.assert_called_once_with(
            "text/html", b"<h1>Quant</h1>"
        )
        handler._respond.assert_not_called()

    def test_missing_compiled_asset_returns_404(self):
        handler = self.make_handler(path="/private.txt")

        with patch.object(
            web_api, "read_static", side_effect=FileNotFoundError()
        ):
            handler.do_GET()

        handler._respond.assert_called_once_with(
            404, {"error": "Not found"}
        )

    def test_missing_build_returns_503(self):
        handler = self.make_handler(path="/")

        with patch.object(
            web_api,
            "read_static",
            side_effect=RuntimeError("private path"),
        ):
            handler.do_GET()

        handler._respond.assert_called_once_with(
            503, {"error": "Dashboard unavailable"}
        )

    def test_unexpected_host_is_refused_before_database_read(self):
        handler = self.make_handler(host="example.com:8765")

        with patch.object(web_api, "read_overview") as read:
            handler.do_GET()

        read.assert_not_called()
        handler._respond.assert_called_once_with(
            403, {"error": "Forbidden"}
        )

    def test_unknown_route_does_not_read_database(self):
        handler = self.make_handler(path="/api/positions")

        with patch.object(web_api, "read_overview") as read:
            handler.do_GET()

        read.assert_not_called()
        handler._respond.assert_called_once_with(
            404, {"error": "Not found"}
        )

    def test_database_failure_does_not_expose_exception(self):
        handler = self.make_handler()

        with patch.object(
            web_api,
            "read_overview",
            side_effect=RuntimeError("private database details"),
        ):
            handler.do_GET()

        handler._respond.assert_called_once_with(
            503, {"error": "Overview unavailable"}
        )

    def test_query_string_does_not_change_route(self):
        handler = self.make_handler(path="/api/overview?refresh=1")

        with patch.object(
            web_api, "read_overview", return_value={"cycles": {"count": 0}}
        ):
            handler.do_GET()

        handler._respond.assert_called_once_with(
            200, {"cycles": {"count": 0}}
        )


if __name__ == "__main__":
    unittest.main()
