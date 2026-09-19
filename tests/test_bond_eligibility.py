"""Synthetic tests for conservative bond eligibility."""

import unittest
from datetime import date

from portfolio_quant.bond_eligibility import evaluate_evidence


class BondEligibilityTests(unittest.TestCase):
    def example(self, **overrides):
        inputs = {
            "as_of": date(2026, 9, 10),
            "terms": {"FACEVALUE": "1000", "MATDATE": "2028-09-10"},
            "primary_boards": ["PRIMARY"],
            "accepted_closes": [(1,)],
            "actions": [
                ("COUPON", "2027-09-10", "100"),
                ("COUPON", "2028-09-10", "100"),
                ("AMORTIZATION", "2028-09-10", "1000"),
            ],
        }
        inputs.update(overrides)
        return evaluate_evidence(**inputs)

    def test_good_observed_rows_do_not_prove_completeness(self):
        result = self.example()
        self.assertFalse(result["determinable"])
        self.assertEqual(result["coupon_count"], 2)
        self.assertEqual(result["principal_count"], 1)
        self.assertEqual(
            result["reasons"],
            (
                "FIXED_COUPON_NOT_PROVEN",
                "FULL_COUPON_SCHEDULE_NOT_PROVEN",
            ),
        )

    def test_missing_coupon_amount_is_reported(self):
        result = self.example(actions=[
            ("COUPON", "2027-09-10", None),
            ("AMORTIZATION", "2028-09-10", "1000"),
        ])
        self.assertIn("COUPON_AMOUNTS_UNVERIFIED", result["reasons"])

    def test_principal_mismatch_is_reported(self):
        result = self.example(actions=[
            ("COUPON", "2027-09-10", "100"),
            ("AMORTIZATION", "2028-09-10", "900"),
        ])
        self.assertIn("PRINCIPAL_SCHEDULE_UNRECONCILED", result["reasons"])

    def test_primary_board_absence_is_reported(self):
        result = self.example(primary_boards=[], accepted_closes=[])
        self.assertIn("PRIMARY_BOARD_UNVERIFIED", result["reasons"])
        self.assertIn("CANONICAL_CLOSE_UNVERIFIED", result["reasons"])

    def test_conditional_offer_is_not_assumed_contractual(self):
        result = self.example(actions=[
            ("COUPON", "2027-09-10", "100"),
            ("AMORTIZATION", "2028-09-10", "1000"),
            ("OFFER", "2027-06-10", None),
        ])
        self.assertIn(
            "CONDITIONAL_OFFER_REQUIRES_MODEL", result["reasons"]
        )

    def test_invalid_maturity_is_reported(self):
        result = self.example(terms={"FACEVALUE": "1000"})
        self.assertIn("MATURITY_UNVERIFIED", result["reasons"])


if __name__ == "__main__":
    unittest.main()
