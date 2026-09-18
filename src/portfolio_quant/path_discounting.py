"""Reference discounting along fictional monthly rate paths."""

from decimal import Decimal, InvalidOperation


DAYS_PER_YEAR = Decimal("365")
MONTHS = 12


def _decimal(value, name: str) -> Decimal:
    if value is None or isinstance(value, (float, bool)):
        raise ValueError(f"{name}: expected Decimal or decimal string")

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name}: invalid decimal") from exc

    if not number.is_finite():
        raise ValueError(f"{name}: non-finite decimal")

    return number


def discount_coupon_on_path(
    gross_amount,
    days_until_payment: int,
    monthly_rates,
) -> Decimal:
    """Discount one known coupon along a fictional rate path.

    Uses 12 equal intervals over 365 days and continuous compounding.
    monthly_rates contains 13 observations; the final one is an endpoint.

    This is not a bond price or a portfolio risk measure.
    """
    amount = _decimal(gross_amount, "gross amount")

    if amount < 0:
        raise ValueError("Negative coupon amount")

    if (
        type(days_until_payment) is not int
        or not 1 <= days_until_payment <= 365
    ):
        raise ValueError("Payment outside supported 365-day horizon")

    if not isinstance(monthly_rates, (list, tuple)):
        raise ValueError("Monthly rates must be a sequence")

    if len(monthly_rates) != MONTHS + 1:
        raise ValueError("Expected 13 rate observations")

    rates = tuple(
        _decimal(value, f"rate {index}")
        for index, value in enumerate(monthly_rates)
    )

    if any(not Decimal("0") <= rate <= Decimal("1") for rate in rates):
        raise ValueError("Rate outside supported range")

    payment_day = Decimal(days_until_payment)
    interval_days = DAYS_PER_YEAR / Decimal(MONTHS)
    accumulated_rate_days = Decimal("0")

    for month in range(MONTHS):
        start = Decimal(month) * interval_days
        end = Decimal(month + 1) * interval_days

        duration = min(payment_day, end) - start

        if duration <= 0:
            break

        accumulated_rate_days += rates[month] * duration

    return amount * (
        -accumulated_rate_days / DAYS_PER_YEAR
    ).exp()
