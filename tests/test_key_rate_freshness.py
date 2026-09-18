"""Tests for the pure CBR key-rate freshness assessment."""

import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from portfolio_quant.key_rate_freshness import (
    assess_key_rate_freshness,
)


MOSCOW = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=MOSCOW)


def assess(
    *,
    collected=None,
    effective=None,
    now=NOW,
    **overrides,
):
    return assess_key_rate_freshness(
        latest_collection_at_utc=(
            collected if collected is not None
            else NOW.astimezone(timezone.utc) - timedelta(hours=12)
        ),
        latest_effective_date=(
            effective if effective is not None
            else date(2026, 9, 18)
        ),
        now=now,
        **overrides,
    )


class KeyRateFreshnessTests(unittest.TestCase):
    def test_recent_collection_and_observation_are_ok(self):
        result = assess()

        self.assertEqual(result.status, "OK")
        self.assertFalse(result.collection_overdue)
        self.assertFalse(result.observation_old)
        self.assertEqual(result.collection_age_hours, 12)
        self.assertEqual(result.observation_age_days, 1)

    def test_overdue_collection_is_distinct_from_old_observation(self):
        result = assess(
            collected=NOW - timedelta(hours=49),
        )

        self.assertEqual(result.status, "COLLECTION_OVERDUE")
        self.assertTrue(result.collection_overdue)
        self.assertFalse(result.observation_old)

    def test_old_observation_with_recent_collection_requires_review(self):
        result = assess(
            effective=date(2026, 9, 10),
        )

        self.assertEqual(result.status, "OBSERVATION_REVIEW")
        self.assertFalse(result.collection_overdue)
        self.assertTrue(result.observation_old)

    def test_both_conditions_require_review(self):
        result = assess(
            collected=NOW - timedelta(hours=49),
            effective=date(2026, 9, 10),
        )

        self.assertEqual(result.status, "REVIEW")
        self.assertTrue(result.collection_overdue)
        self.assertTrue(result.observation_old)

    def test_exact_thresholds_are_not_overdue(self):
        result = assess(
            collected=NOW - timedelta(hours=48),
            effective=date(2026, 9, 12),
        )

        self.assertEqual(result.status, "OK")

    def test_moscow_date_is_used_across_utc_midnight(self):
        now_utc = datetime(
            2026, 9, 18, 22, 30, tzinfo=timezone.utc
        )
        result = assess(
            collected=now_utc - timedelta(hours=1),
            effective=date(2026, 9, 18),
            now=now_utc,
        )

        self.assertEqual(result.observation_age_days, 1)
        self.assertEqual(result.status, "OK")

    def test_future_timestamps_are_rejected(self):
        cases = (
            {"collected": NOW + timedelta(seconds=1)},
            {"effective": date(2026, 9, 20)},
        )

        for parameters in cases:
            with self.subTest(parameters=parameters):
                with self.assertRaisesRegex(ValueError, "future"):
                    assess(**parameters)

    def test_naive_datetimes_are_rejected(self):
        naive = datetime(2026, 9, 19, 12, 0)

        for parameters in (
            {"collected": naive},
            {"now": naive},
        ):
            with self.subTest(parameters=parameters):
                with self.assertRaisesRegex(ValueError, "timezone"):
                    assess(**parameters)

    def test_invalid_thresholds_are_rejected(self):
        for parameters in (
            {"max_collection_age_hours": 0},
            {"max_collection_age_hours": True},
            {"observation_review_days": 0},
            {"observation_review_days": True},
        ):
            with self.subTest(parameters=parameters):
                with self.assertRaisesRegex(ValueError, "thresholds"):
                    assess(**parameters)


if __name__ == "__main__":
    unittest.main()
