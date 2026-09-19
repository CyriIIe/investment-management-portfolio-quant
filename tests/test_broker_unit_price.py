"""Synthetic tests for descriptive broker valuation per bond."""

import unittest
from datetime import date
from decimal import Decimal

from portfolio_quant.broker_unit_price import calculate_broker_unit_price
from portfolio_quant.core_adapter import Position


def position(*, quantity="3", clean_value="2850.00", accrued="45.00"):
    return Position(
        isin="RU000A000001",
        security_code="TEST",
        market_section="TQCB",
        currency="RUB",
        quantity=Decimal(quantity),
        market_value_ex_accrued=Decimal(clean_value),
        accrued_interest=Decimal(accrued),
        source_observation_id=501,
    )


class BrokerUnitPriceTests(unittest.TestCase):
    def test_divides_existing_broker_values_by_quantity(self):
        result = calculate_broker_unit_price(
            position(),
            as_of_date=date(2026, 9, 10),
        )

        self.assertEqual(result.as_of_date, date(2026, 9, 10))
        self.assertEqual(result.currency, "RUB")
        self.assertEqual(result.clean_price_per_unit, Decimal("950.00"))
        self.assertEqual(result.accrued_interest_per_unit, Decimal("15.00"))
        self.assertEqual(result.dirty_price_per_unit, Decimal("965.00"))

    def test_zero_accrued_interest_is_not_missing(self):
        result = calculate_broker_unit_price(
            position(quantity="2", clean_value="1900", accrued="0"),
            as_of_date=date(2026, 9, 10),
        )

        self.assertEqual(result.accrued_interest_per_unit, Decimal("0"))
        self.assertEqual(result.dirty_price_per_unit, Decimal("950"))

    def test_rejects_nonpositive_quantity(self):
        with self.assertRaises(ValueError):
            calculate_broker_unit_price(
                position(quantity="0"),
                as_of_date=date(2026, 9, 10),
            )


if __name__ == "__main__":
    unittest.main()
