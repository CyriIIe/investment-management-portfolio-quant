"""Offline tests for explicit experimental pilot registration."""

import unittest
from dataclasses import replace
from unittest.mock import patch

from portfolio_quant.experimental_registry import (
    PILOT_REGISTRY,
    validate_registry,
)
from portfolio_quant import web_experimental_pilots


class ExperimentalRegistryTests(unittest.TestCase):
    def test_registered_pilots_are_unique(self):
        self.assertEqual(len(validate_registry()), 3)

    def test_duplicate_isin_is_rejected(self):
        duplicate = replace(
            PILOT_REGISTRY[1],
            isin=PILOT_REGISTRY[0].isin,
        )
        with self.assertRaises(ValueError):
            validate_registry((PILOT_REGISTRY[0], duplicate))

    def test_duplicate_reader_is_rejected(self):
        duplicate = replace(
            PILOT_REGISTRY[1],
            reader_name=PILOT_REGISTRY[0].reader_name,
        )
        with self.assertRaises(ValueError):
            validate_registry((PILOT_REGISTRY[0], duplicate))

    def test_unimplemented_reader_is_rejected(self):
        unknown = replace(
            PILOT_REGISTRY[0],
            reader_name="unimplemented",
        )
        with patch.object(
            web_experimental_pilots,
            "validate_registry",
            return_value=(unknown,),
        ):
            with self.assertRaises(ValueError):
                web_experimental_pilots.read_experimental_pilots()

    def test_registered_readers_return_expected_instruments(self):
        result = web_experimental_pilots.read_experimental_pilots()
        self.assertEqual(
            [item["instrument_isin"] for item in result["instruments"]],
            [entry.isin for entry in PILOT_REGISTRY],
        )
        self.assertFalse(result["historical_backtest_validated"])


if __name__ == "__main__":
    unittest.main()
