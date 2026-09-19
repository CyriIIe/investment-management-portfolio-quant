"""Tests hors ligne du raccordement documentaire au moteur déterministe."""

import json
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from portfolio_quant.deterministic_total_return import calculate_total_return
from portfolio_quant.documented_bond_flows import (
    build_bond_case,
    parse_documented_bond_flows,
)


RESEARCH = (
    Path.home()
    / "investment-management-portfolio-quant-data"
    / "research"
)

DOCUMENTS = {
    "ofz": ("ofz_26252_2026-09-10.json", "925.52"),
    "sber": ("sber_d10_2026-09-10.json", "494.30"),
    "gtlk": ("gtlk_002p_13_2026-09-10.json", "981.83"),
}


class DocumentedTotalReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {}
        for name, (filename, price) in DOCUMENTS.items():
            document = json.loads(
                (RESEARCH / filename).read_text(encoding="utf-8"),
                parse_float=Decimal,
            )
            validated = parse_documented_bond_flows(document)
            cls.cases[name] = build_bond_case(
                validated,
                horizon_date=date(2027, 9, 10),
                verified_dirty_price=Decimal(price),
            )

    def test_three_types_can_be_calculated(self):
        for name, bond in self.cases.items():
            with self.subTest(name=name):
                results = calculate_total_return(
                    bond,
                    annual_market_yields=("0.10", "0.125", "0.15"),
                )
                self.assertEqual(len(results), 3)
                self.assertTrue(all(
                    result.terminal_wealth > 0 for result in results
                ))

    def test_sber_has_no_coupons(self):
        bond = self.cases["sber"]
        self.assertTrue(bond.zero_coupon_verified)
        self.assertFalse(bond.fixed_coupon_verified)
        self.assertTrue(all(
            flow.kind == "PRINCIPAL" for flow in bond.flows
        ))

    def test_gtlk_includes_five_principal_payments(self):
        bond = self.cases["gtlk"]
        principal = [
            flow for flow in bond.flows if flow.kind == "PRINCIPAL"
        ]
        self.assertEqual(len(principal), 5)
        self.assertEqual(
            sum((flow.amount for flow in principal), Decimal("0")),
            Decimal("1000"),
        )

    def test_zero_coupon_classification_cannot_be_forged(self):
        bond = self.cases["ofz"]
        with self.assertRaises(ValueError):
            calculate_total_return(
                replace(
                    bond,
                    fixed_coupon_verified=False,
                    zero_coupon_verified=True,
                ),
                annual_market_yields=("0.10",),
            )

    def test_fixed_coupon_classification_requires_coupons(self):
        bond = self.cases["sber"]
        with self.assertRaises(ValueError):
            calculate_total_return(
                replace(
                    bond,
                    fixed_coupon_verified=True,
                    zero_coupon_verified=False,
                ),
                annual_market_yields=("0.10",),
            )


if __name__ == "__main__":
    unittest.main()
