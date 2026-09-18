import unittest
from datetime import date
from decimal import Decimal

from portfolio_quant.cashflows import fixed_bond_cashflows


class FixedBondCashFlowTests(unittest.TestCase):
    def test_two_coupons_and_principal(self):
        flows = fixed_bond_cashflows(
            valuation_date=date(2026, 9, 18),
            maturity_date=date(2027, 9, 18),
            coupon_dates=[date(2027, 3, 18), date(2027, 9, 18)],
            coupon_per_bond=Decimal("50.00"),
            nominal_per_bond=Decimal("1000.00"),
            quantity=3,
        )

        self.assertEqual(len(flows), 3)
        self.assertEqual(
            sum((flow.amount for flow in flows), Decimal("0")),
            Decimal("3300.00"),
        )
        self.assertEqual(
            [flow.kind for flow in flows],
            ["coupon", "coupon", "principal"],
        )

    def test_past_coupon_is_excluded(self):
        flows = fixed_bond_cashflows(
            valuation_date=date(2026, 9, 18),
            maturity_date=date(2027, 3, 18),
            coupon_dates=[date(2026, 3, 18), date(2027, 3, 18)],
            coupon_per_bond=Decimal("40"),
            nominal_per_bond=Decimal("1000"),
            quantity=1,
        )

        self.assertEqual(len(flows), 2)

    def test_duplicate_dates_rejected(self):
        with self.assertRaises(ValueError):
            fixed_bond_cashflows(
                valuation_date=date(2026, 9, 18),
                maturity_date=date(2027, 3, 18),
                coupon_dates=[date(2027, 3, 18)] * 2,
                coupon_per_bond=Decimal("40"),
                nominal_per_bond=Decimal("1000"),
                quantity=1,
            )


if __name__ == "__main__":
    unittest.main()
