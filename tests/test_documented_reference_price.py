"""Offline tests for the explicit discount-bond quotation convention."""

import copy
import json
import unittest
from decimal import Decimal
from pathlib import Path

from portfolio_quant.documented_bond_flows import parse_documented_bond_flows
from portfolio_quant.documented_reference_price import (
    COUPON_BASIS,
    DISCOUNT_BASIS,
    documented_reference_price,
)


RESEARCH = (
    Path.home()
    / "investment-management-portfolio-quant-data"
    / "research"
)


class ReferencePriceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sber = json.loads(
            (RESEARCH / "sber_d10_2026-09-10.json").read_text(
                encoding="utf-8"
            ),
            parse_float=Decimal,
        )
        cls.gtlk = json.loads(
            (RESEARCH / "gtlk_002p_13_2026-09-10.json").read_text(
                encoding="utf-8"
            ),
            parse_float=Decimal,
        )

    def test_documented_discount_quotation(self):
        validated = parse_documented_bond_flows(self.sber)
        price, basis = documented_reference_price(
            self.sber,
            validated,
            core_close="49.43",
            core_accint=None,
        )
        self.assertEqual(price, Decimal("494.30"))
        self.assertEqual(basis, DISCOUNT_BASIS)
        self.assertIsNone(self.sber["market_reference"]["accrued_interest"])

    def test_discount_rejects_nonmissing_core_accint(self):
        with self.assertRaises(ValueError):
            documented_reference_price(
                self.sber,
                parse_documented_bond_flows(self.sber),
                core_close="49.43",
                core_accint="0",
            )

    def test_discount_rejects_modified_close(self):
        with self.assertRaises(ValueError):
            documented_reference_price(
                self.sber,
                parse_documented_bond_flows(self.sber),
                core_close="49.44",
                core_accint=None,
            )

    def test_discount_rejects_coupon_misclassification(self):
        document = copy.deepcopy(self.sber)
        document["instrument"]["coupon_frequency_per_year"] = 1
        with self.assertRaises(ValueError):
            documented_reference_price(
                document,
                parse_documented_bond_flows(document),
                core_close="49.43",
                core_accint=None,
            )

    def test_coupon_bond_preserves_normal_accint_rule(self):
        validated = parse_documented_bond_flows(self.gtlk)
        price, basis = documented_reference_price(
            self.gtlk,
            validated,
            core_close="97.44",
            core_accint="7.43",
        )
        self.assertEqual(price, Decimal("981.83"))
        self.assertEqual(basis, COUPON_BASIS)

    def test_coupon_bond_rejects_missing_accint(self):
        with self.assertRaises(ValueError):
            documented_reference_price(
                self.gtlk,
                parse_documented_bond_flows(self.gtlk),
                core_close="97.44",
                core_accint=None,
            )


if __name__ == "__main__":
    unittest.main()
