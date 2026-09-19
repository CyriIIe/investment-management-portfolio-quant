"""Offline freshness and MOEX observation parsing tests."""

import hashlib
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from portfolio_quant.deterministic_total_return import BondFlow
from portfolio_quant.documented_bond_flows import DocumentedBondFlows
from portfolio_quant.experimental_weather import (
    MarketObservation, calculate_weather, weather_is_fresh,
)
from portfolio_quant.experimental_weather_refresh import (
    PILOT_DOCUMENTS, parse_market_observation,
)


class ExperimentalWeatherTests(unittest.TestCase):
    def observation(self, *, collected=None, trade=None):
        return MarketObservation(
            isin="RU000A10DCH3", board="TQCB",
            trade_date=trade or date(2026, 9, 19),
            collected_at_utc=collected or datetime(2026, 9, 19, 12, tzinfo=timezone.utc),
            source_url="https://iss.moex.com/example",
            source_sha256="a" * 64, legal_close_price_pct=Decimal("49.43"),
            accrued_interest=None,
        )

    def test_old_observation_is_not_current(self):
        now = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
        self.assertFalse(weather_is_fresh(self.observation(trade=date(2026, 9, 14)), now=now))
        self.assertFalse(weather_is_fresh(self.observation(collected=now - timedelta(hours=49)), now=now))

    def test_moex_parser_keeps_missing_accint_missing(self):
        raw = b'{"marketdata":{"columns":["SECID","BOARDID","LASTDATE","LEGALCLOSEPRICE","ACCINT"],"data":[["RU000A10DCH3","TQCB","2026-09-19",49.43,null]]}}'
        result = parse_market_observation(
            raw=raw, isin="RU000A10DCH3", board="TQCB",
            collected_at_utc=datetime(2026, 9, 19, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(result.legal_close_price_pct, Decimal("49.43"))
        self.assertIsNone(result.accrued_interest)
        self.assertEqual(result.source_sha256, hashlib.sha256(raw).hexdigest())

    def test_documentary_boards_are_fixed_per_pilot(self):
        self.assertEqual(PILOT_DOCUMENTS["ofz"][1], "TQOB")
        self.assertEqual(PILOT_DOCUMENTS["gtlk"][1], "TQCB")
        self.assertEqual(PILOT_DOCUMENTS["sber_d10"][1], "TQCB")

    def test_post_amortization_uses_remaining_nominal_and_excludes_paid_flows(self):
        documented = DocumentedBondFlows(
            isin="RU000A10F801", secid="GTLK", coupon_type="FIXED_AMORTIZING",
            valuation_date=date(2026, 9, 10), maturity_date=date(2028, 1, 1),
            observation_date=date(2026, 9, 19), currency="RUB", primary_board="TQCB",
            face_value=Decimal("1000"), coupon_count=2, principal_event_count=2,
            flows=(
                BondFlow(date(2026, 10, 1), "COUPON", Decimal("10")),
                BondFlow(date(2026, 10, 10), "PRINCIPAL", Decimal("200")),
                BondFlow(date(2027, 6, 1), "COUPON", Decimal("10")),
                BondFlow(date(2028, 1, 1), "PRINCIPAL", Decimal("800")),
            ),
        )
        observation = MarketObservation(
            isin=documented.isin, board="TQCB", trade_date=date(2026, 10, 15),
            collected_at_utc=datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
            source_url="https://iss.moex.com/example", source_sha256="b" * 64,
            legal_close_price_pct=Decimal("97.44"), accrued_interest=Decimal("7.43"),
        )
        with patch("portfolio_quant.experimental_weather.parse_documented_bond_flows", return_value=documented):
            result = calculate_weather({}, observation)
        self.assertEqual(result["dirty_price_rub_per_bond"], "786.95")
        self.assertEqual(result["scenarios"][0]["received_through_horizon_rub_per_bond"], "10")
