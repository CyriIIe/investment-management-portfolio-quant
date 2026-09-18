import unittest
from copy import deepcopy

from portfolio_quant.core_adapter import parse_core_positions


def sample_export():
    return {
        "schema_version": "1",
        "command": "portfolio.positions",
        "generated_at_utc": "2026-09-18T12:00:00+00:00",
        "data": {
            "as_of_date": "2026-09-17",
            "positions": [{
                "isin": "RU000A000000",
                "security_code": "TESTBOND",
                "market_section": "TQCB",
                "currency_code": "RUB",
                "quantity_decimal": "3",
                "market_value_ex_accrued_decimal": "2850.00",
                "accrued_interest_decimal": "45.00",
                "source_observation_id": 1,
            }],
        },
    }


class CoreAdapterTests(unittest.TestCase):
    def test_valid_export(self):
        result = parse_core_positions(sample_export())
        self.assertEqual(len(result.positions), 1)
        self.assertEqual(str(result.positions[0].quantity), "3")
        self.assertEqual(len(result.source_hash), 64)

    def test_hash_is_reproducible(self):
        first = parse_core_positions(sample_export())
        second = parse_core_positions(sample_export())
        self.assertEqual(first.source_hash, second.source_hash)

    def test_missing_market_value_is_rejected(self):
        payload = sample_export()
        payload["data"]["positions"][0][
            "market_value_ex_accrued_decimal"
        ] = None

        with self.assertRaises(ValueError):
            parse_core_positions(payload)

    def test_duplicate_position_is_rejected(self):
        payload = sample_export()
        payload["data"]["positions"].append(
            deepcopy(payload["data"]["positions"][0])
        )

        with self.assertRaises(ValueError):
            parse_core_positions(payload)

    def test_missing_security_code_is_accepted(self):
        payload = sample_export()
        payload["data"]["positions"][0]["security_code"] = None

        result = parse_core_positions(payload)

        self.assertIsNone(result.positions[0].security_code)

    def test_wrong_command_is_rejected(self):
        payload = sample_export()
        payload["command"] = "portfolio.summary"

        with self.assertRaises(ValueError):
            parse_core_positions(payload)


    def test_export_time_does_not_change_snapshot_hash(self):
        first = sample_export()
        second = deepcopy(first)
        second["generated_at_utc"] = "2026-09-19T12:00:00+00:00"

        self.assertEqual(
            parse_core_positions(first).source_hash,
            parse_core_positions(second).source_hash,
        )


if __name__ == "__main__":
    unittest.main()
