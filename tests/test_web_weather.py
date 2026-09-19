"""Offline tests for the read-only weather response."""

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

from portfolio_quant import web_weather
from portfolio_quant.portfolio_weather import PortfolioWeather


class WebWeatherTests(unittest.TestCase):
    def test_returns_only_descriptive_aggregates(self):
        inputs = object()
        weather = PortfolioWeather(
            portfolio_date=date(2026, 9, 10),
            cashflow_run_id=8,
            position_count=2,
            coupon_coverage_pct=Decimal("50.00"),
            unknown_schedule_count=1,
            cashflow_horizon_days=365,
            event_count=3,
            events_by_type=(("COUPON", 2), ("MATURITY_REDEMPTION", 1)),
            events_by_currency=(("RUB", 3),),
        )

        with (
            patch.object(
                web_weather, "load_core_inputs", return_value=inputs
            ) as load,
            patch.object(
                web_weather, "build_portfolio_weather",
                return_value=weather,
            ) as build,
        ):
            result = web_weather.read_weather()

        load.assert_called_once_with()
        build.assert_called_once_with(inputs)
        self.assertEqual(result, {
            "portfolio_date": "2026-09-10",
            "cashflow_run_id": 8,
            "position_count": 2,
            "coupon_coverage_pct": "50.00",
            "unknown_schedule_count": 1,
            "cashflow_horizon_days": 365,
            "event_count": 3,
            "events_by_type": {
                "COUPON": 2,
                "MATURITY_REDEMPTION": 1,
            },
            "events_by_currency": {"RUB": 3},
            "complete_cashflows": False,
            "portfolio_risk_measure": False,
        })
        for private_field in (
            "positions", "isin", "quantity", "market_value",
            "gross_amount", "cashflows",
        ):
            self.assertNotIn(private_field, result)

    def test_core_read_failure_propagates_to_api(self):
        with patch.object(
            web_weather,
            "load_core_inputs",
            side_effect=RuntimeError("Missing matching CORE cashflows"),
        ):
            with self.assertRaises(RuntimeError):
                web_weather.read_weather()


if __name__ == "__main__":
    unittest.main()
