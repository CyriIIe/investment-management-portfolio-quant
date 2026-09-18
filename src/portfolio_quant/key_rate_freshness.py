"""Read-only freshness assessment for Portfolio Quant key-rate data.

No network, database access, writes, or assumptions about publication days.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class KeyRateFreshness:
    status: str
    collection_age_hours: float
    observation_age_days: int
    collection_overdue: bool
    observation_old: bool
    reason: str


def assess_key_rate_freshness(
    *,
    latest_collection_at_utc: datetime,
    latest_effective_date: date,
    now: datetime,
    max_collection_age_hours: int = 48,
    observation_review_days: int = 7,
) -> KeyRateFreshness:
    """Assess collection health separately from observation age.

    An old observation is a review signal, not proof that the
    published rate is incorrect or that the CBR service has failed.
    """
    for name, timestamp in (
        ("latest collection", latest_collection_at_utc),
        ("current time", now),
    ):
        if (
            not isinstance(timestamp, datetime)
            or timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError(f"{name}: timezone-aware datetime required")

    if type(latest_effective_date) is not date:
        raise ValueError("Effective date must be a date")

    if (
        type(max_collection_age_hours) is not int
        or max_collection_age_hours < 1
        or type(observation_review_days) is not int
        or observation_review_days < 1
    ):
        raise ValueError("Freshness thresholds must be positive integers")

    collection_utc = latest_collection_at_utc.astimezone(timezone.utc)
    now_utc = now.astimezone(timezone.utc)

    if collection_utc > now_utc:
        raise ValueError("Collection timestamp is in the future")

    today_moscow = now.astimezone(MOSCOW).date()

    if latest_effective_date > today_moscow:
        raise ValueError("Effective date is in the future")

    collection_age_hours = (
        now_utc - collection_utc
    ).total_seconds() / 3600

    observation_age_days = (
        today_moscow - latest_effective_date
    ).days

    collection_overdue = (
        collection_age_hours > max_collection_age_hours
    )
    observation_old = (
        observation_age_days > observation_review_days
    )

    if collection_overdue and observation_old:
        status = "REVIEW"
        reason = "Collection overdue and observation date requires review"
    elif collection_overdue:
        status = "COLLECTION_OVERDUE"
        reason = "Collector has not completed a recent collection"
    elif observation_old:
        status = "OBSERVATION_REVIEW"
        reason = "Collection is recent; publication date requires review"
    else:
        status = "OK"
        reason = "Collection recent; observation within review threshold"

    return KeyRateFreshness(
        status=status,
        collection_age_hours=collection_age_hours,
        observation_age_days=observation_age_days,
        collection_overdue=collection_overdue,
        observation_old=observation_old,
        reason=reason,
    )
