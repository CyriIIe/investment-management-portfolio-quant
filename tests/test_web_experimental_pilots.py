"""Tests hors ligne de la réponse API expérimentale commune."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portfolio_quant import web_experimental_pilots as module


class ExperimentalPilotsTests(unittest.TestCase):
    def test_three_validated_pilots(self):
        data = module.read_experimental_pilots()
        self.assertEqual(
            [item["instrument_isin"] for item in data["instruments"]],
            ["RU000A10D4Y2", "RU000A10F801", "RU000A10DCH3"],
        )
        self.assertFalse(data["historical_backtest_validated"])
        self.assertFalse(data["portfolio_risk_measure"])
        self.assertEqual(len(data["instruments"][1]["scenarios"]), 3)
        self.assertEqual(len(data["instruments"][2]["scenarios"]), 3)

    def test_sber_confirms_no_coupons_and_discount_quotation(self):
        sber = module.read_experimental_pilots()["instruments"][2]

        self.assertEqual(sber["coupon_type"], "DISCOUNT_NO_COUPON")
        self.assertEqual(sber["coupon_count"], 0)
        self.assertEqual(sber["received_coupon_rub_per_bond"], "0")
        self.assertEqual(
            sber["price_basis"],
            "MOEX_DISCOUNT_CLOSE_NO_COUPON_ACCRUAL",
        )
        self.assertEqual(
            sber["reference_price_label"],
            "Clôture MOEX à escompte, sans ajout d’intérêts courus",
        )

    def test_modified_gtlk_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            source.write_text(
                '{"instrument":{"isin":"RU000A10F801"}}',
                encoding="utf-8",
            )
            with patch.object(module, "GTLK_SOURCE", source):
                with self.assertRaises(ValueError):
                    module.read_experimental_pilots()

    def test_modified_gtlk_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            original = json.loads(
                module.GTLK_RESULT.read_text(encoding="utf-8")
            )
            modified = copy.deepcopy(original)
            modified["scenarios"][0]["gross_total_return_decimal"] = "999"
            result_path.write_text(
                json.dumps(modified), encoding="utf-8"
            )
            with patch.object(module, "GTLK_RESULT", result_path):
                with self.assertRaises(ValueError):
                    module.read_experimental_pilots()

    def test_modified_sber_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            modified = json.loads(
                module.SBER_SOURCE.read_text(encoding="utf-8")
            )
            modified["market_reference"]["canonical_close_price_pct"] = 49.44
            source.write_text(json.dumps(modified), encoding="utf-8")
            with patch.object(module, "SBER_SOURCE", source):
                with self.assertRaises(ValueError):
                    module.read_experimental_pilots()

    def test_modified_sber_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            original = json.loads(
                module.SBER_RESULT.read_text(encoding="utf-8")
            )
            modified = copy.deepcopy(original)
            modified["scenarios"][0]["gross_total_return_decimal"] = "999"
            result_path.write_text(
                json.dumps(modified), encoding="utf-8"
            )
            with patch.object(module, "SBER_RESULT", result_path):
                with self.assertRaises(ValueError):
                    module.read_experimental_pilots()


if __name__ == "__main__":
    unittest.main()
