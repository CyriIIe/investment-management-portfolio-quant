"""Contrôles hors ligne sur les trois schémas documentaires privés."""

import copy
import json
import unittest
from decimal import Decimal
from pathlib import Path

from portfolio_quant.documented_bond_flows import (
    parse_documented_bond_flows,
)


RESEARCH = (
    Path.home()
    / "investment-management-portfolio-quant-data"
    / "research"
)

FILES = (
    "ofz_26252_2026-09-10.json",
    "sber_d10_2026-09-10.json",
    "gtlk_002p_13_2026-09-10.json",
)


class DocumentedBondFlowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {
            name: json.loads(
                (RESEARCH / name).read_text(encoding="utf-8"),
                parse_float=Decimal,
            )
            for name in FILES
        }

    def test_three_documented_bond_types(self):
        expected = {
            FILES[0]: ("FIXED_KNOWN", 15, 1),
            FILES[1]: ("DISCOUNT_NO_COUPON", 0, 1),
            FILES[2]: ("FIXED_AMORTIZING", 45, 5),
        }
        for filename, (kind, coupons, principal) in expected.items():
            with self.subTest(filename=filename):
                result = parse_documented_bond_flows(
                    self.documents[filename]
                )
                self.assertEqual(result.coupon_type, kind)
                self.assertEqual(result.coupon_count, coupons)
                self.assertEqual(result.principal_event_count, principal)
                self.assertFalse(result.historical_availability_proven)
                self.assertEqual(
                    sum(
                        (flow.amount for flow in result.flows
                         if flow.kind == "PRINCIPAL"),
                        Decimal("0"),
                    ),
                    result.face_value,
                )

    def test_missing_coupon_is_not_accepted_as_zero_coupon(self):
        doc = copy.deepcopy(self.documents[FILES[0]])
        doc["cashflows"] = []
        with self.assertRaises(ValueError):
            parse_documented_bond_flows(doc)

    def test_incomplete_principal_is_rejected(self):
        doc = copy.deepcopy(self.documents[FILES[2]])
        doc["principal_events"].pop()
        with self.assertRaises(ValueError):
            parse_documented_bond_flows(doc)

    def test_conditional_event_is_rejected(self):
        doc = copy.deepcopy(self.documents[FILES[1]])
        doc["conditional_events"] = [{"type": "OFFER"}]
        with self.assertRaises(ValueError):
            parse_documented_bond_flows(doc)

    def test_duplicate_coupon_is_rejected(self):
        doc = copy.deepcopy(self.documents[FILES[2]])
        doc["cashflows"].append(copy.deepcopy(doc["cashflows"][0]))
        doc["completeness"]["coupon_count_post_valuation_date"] += 1
        with self.assertRaises(ValueError):
            parse_documented_bond_flows(doc)


if __name__ == "__main__":
    unittest.main()
