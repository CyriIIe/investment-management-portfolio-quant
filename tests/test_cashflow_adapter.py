import unittest
from copy import deepcopy
from decimal import Decimal

from portfolio_quant.cashflow_adapter import parse_core_cashflows


def sample_export():
    return {
        "schema_version": "1",
        "command": "cashflow.show",
        "generated_at_utc": "2026-09-18T12:00:00+00:00",
        "data": {
            "run_id": 8,
            "status": "SUCCESS",
            "as_of_date": "2026-09-10",
            "portfolio_snapshot_date": "2026-09-10",
            "portfolio_snapshot_ids": [101, 102],
            "details": {
                "coverage": {
                    "coupon_schedule_coverage_pct": "50.00",
                },
                "unknown_cashflow_schedules": [
                    {"reasons": ["coupon schedule unavailable"]},
                ],
                "horizon_days": 365,
            },
            "events": [
                {
                    "id": 501,
                    "event_date": "2026-10-15",
                    "event_type": "COUPON",
                    "currency_code": "RUB",
                    "certainty": "CONTRACTUAL",
                    "gross_amount_decimal": "125.50",
                },
            ],
        },
    }


class CashflowAdapterTests(unittest.TestCase):
    def test_valid_export_preserves_incomplete_coverage(self):
        result = parse_core_cashflows(
            sample_export(),
            expected_snapshot_ids=[102, 101],
        )

        self.assertEqual(result.run_id, 8)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].gross_amount, Decimal("125.50"))
        self.assertEqual(result.coupon_coverage_pct, Decimal("50.00"))
        self.assertEqual(result.unknown_schedule_count, 1)
        self.assertFalse(result.has_complete_cashflows)

    def test_different_positions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "snapshot IDs"):
            parse_core_cashflows(
                sample_export(),
                expected_snapshot_ids=[101, 999],
            )

    def test_wrong_command_is_rejected(self):
        payload = sample_export()
        payload["command"] = "cashflow.summary"

        with self.assertRaisesRegex(ValueError, "cashflow.show"):
            parse_core_cashflows(
                payload,
                expected_snapshot_ids=[101, 102],
            )

    def test_missing_unknown_schedule_information_is_rejected(self):
        payload = sample_export()
        del payload["data"]["details"]["unknown_cashflow_schedules"]

        with self.assertRaisesRegex(ValueError, "unknown-schedules"):
            parse_core_cashflows(
                payload,
                expected_snapshot_ids=[101, 102],
            )

    def test_duplicate_event_is_rejected(self):
        payload = sample_export()
        payload["data"]["events"].append(
            deepcopy(payload["data"]["events"][0])
        )

        with self.assertRaisesRegex(ValueError, "duplicate ID"):
            parse_core_cashflows(
                payload,
                expected_snapshot_ids=[101, 102],
            )


if __name__ == "__main__":
    unittest.main()
