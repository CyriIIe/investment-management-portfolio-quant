"""Synthetic tests for unambiguous asset-to-cashflow association."""

import unittest
from datetime import date
from decimal import Decimal

from portfolio_quant.asset_cashflows import associate_asset_cashflows
from portfolio_quant.cashflow_adapter import (
    CashflowEvent,
    CashflowRun,
    UnknownSchedule,
)
from portfolio_quant.core_adapter import Position, PortfolioSnapshot
from portfolio_quant.core_readonly import CoreInputs


def position(isin, currency="RUB", section="TQCB"):
    return Position(
        isin=isin,
        security_code=None,
        market_section=section,
        currency=currency,
        quantity=Decimal("1"),
        market_value_ex_accrued=Decimal("100"),
        accrued_interest=Decimal("0"),
        source_observation_id=1,
    )


def inputs(positions, events=(), unknown=()):
    day = date(2026, 9, 10)
    return CoreInputs(
        snapshot=PortfolioSnapshot(
            as_of_date=day,
            source_hash="fictional",
            positions=tuple(positions),
        ),
        cashflows=CashflowRun(
            run_id=8,
            portfolio_date=day,
            snapshot_ids=frozenset({101}),
            events=tuple(events),
            coupon_coverage_pct=Decimal("50"),
            unknown_schedule_count=len(unknown),
            horizon_days=365,
            unknown_schedules=tuple(unknown),
        ),
    )


def coupon(isin, currency="RUB"):
    return CashflowEvent(
        event_id=501,
        event_date=date(2026, 10, 15),
        event_type="COUPON",
        currency=currency,
        gross_amount=Decimal("125.50"),
        certainty="CONTRACTUAL",
        isin=isin,
    )


class AssetCashflowsTests(unittest.TestCase):
    def test_unique_isin_and_currency_associate_event(self):
        result = associate_asset_cashflows(inputs(
            [position("RU000A000001")],
            [coupon("RU000A000001")],
        ))
        self.assertEqual(result.assets[0].known_event_count, 1)
        self.assertEqual(
            result.assets[0].next_known_event_date,
            date(2026, 10, 15),
        )
        self.assertEqual(result.unassigned_event_count, 0)
        self.assertFalse(result.complete_cashflows)

    def test_currency_mismatch_is_not_assigned(self):
        result = associate_asset_cashflows(inputs(
            [position("RU000A000001", "RUB")],
            [coupon("RU000A000001", "USD")],
        ))
        self.assertEqual(result.assets[0].known_event_count, 0)
        self.assertEqual(result.unassigned_event_count, 1)

    def test_ambiguous_identity_is_not_assigned(self):
        result = associate_asset_cashflows(inputs(
            [
                position("RU000A000001", section="TQCB"),
                position("RU000A000001", section="TQOD"),
            ],
            [coupon("RU000A000001")],
            [UnknownSchedule(
                isin="RU000A000001",
                secid=None,
                reasons=("MISSING_COUPON_SCHEDULE",),
            )],
        ))
        self.assertTrue(
            all(asset.known_event_count == 0 for asset in result.assets)
        )
        self.assertEqual(result.unassigned_event_count, 1)
        self.assertEqual(result.unassigned_schedule_count, 1)

    def test_unique_unknown_schedule_keeps_reasons(self):
        result = associate_asset_cashflows(inputs(
            [position("RU000A000001")],
            unknown=[UnknownSchedule(
                isin="RU000A000001",
                secid=None,
                reasons=("MISSING_COUPON_SCHEDULE",),
            )],
        ))
        self.assertEqual(
            result.assets[0].incomplete_reasons,
            ("MISSING_COUPON_SCHEDULE",),
        )
        self.assertIsNone(result.assets[0].next_known_event_date)
        self.assertFalse(result.complete_cashflows)

    def test_rejects_mismatched_portfolio_dates(self):
        source = inputs([position("RU000A000001")])
        mismatched = CoreInputs(
            snapshot=source.snapshot,
            cashflows=CashflowRun(
                run_id=8,
                portfolio_date=date(2026, 9, 9),
                snapshot_ids=frozenset({101}),
                events=(),
                coupon_coverage_pct=Decimal("50"),
                unknown_schedule_count=0,
                horizon_days=365,
            ),
        )
        with self.assertRaisesRegex(ValueError, "dates"):
            associate_asset_cashflows(mismatched)


if __name__ == "__main__":
    unittest.main()
