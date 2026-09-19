"""Offline tests for deterministic portfolio change explanations."""

import unittest

from portfolio_quant.change_explanations import explain_changes
from portfolio_quant.portfolio_changes import PortfolioChanges


def sample_changes(**overrides):
    values = {
        "previous_date": "2026-09-09",
        "current_date": "2026-09-10",
        "previous_position_count": 11,
        "current_position_count": 12,
        "added_count": 1,
        "removed_count": 0,
        "quantity_changed_count": 0,
        "value_changed_at_constant_quantity_count": 9,
        "accrued_changed_at_constant_quantity_count": 10,
        "source_only_changed_count": 0,
        "unchanged_count": 0,
    }
    values.update(overrides)
    return PortfolioChanges(**values)


class ChangeExplanationsTests(unittest.TestCase):
    def test_observations_do_not_invent_causes(self):
        result = explain_changes(sample_changes())
        text = " ".join(result.observations)

        self.assertIn("1 position(s) apparue(s)", text)
        self.assertIn("9 position(s)", text)
        self.assertIn("10 position(s)", text)
        self.assertIn("cause de cette apparition n'est pas établie", text)
        self.assertFalse(result.performance_measure)
        self.assertFalse(result.portfolio_risk_measure)

    def test_missing_changes_do_not_create_a_story(self):
        result = explain_changes(sample_changes(
            previous_position_count=11,
            current_position_count=11,
            added_count=0,
            value_changed_at_constant_quantity_count=0,
            accrued_changed_at_constant_quantity_count=0,
        ))
        self.assertEqual(
            result.observations,
            ("Aucun changement détecté dans les champs comparés.",),
        )

    def test_rejects_unexpected_input(self):
        with self.assertRaisesRegex(ValueError, "portfolio changes"):
            explain_changes(None)


if __name__ == "__main__":
    unittest.main()
