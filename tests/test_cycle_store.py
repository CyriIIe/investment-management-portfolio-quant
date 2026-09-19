"""Offline tests for independent experimental cycle storage."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from portfolio_quant.cycle_store import (
    initialize_cycle_store,
    save_experimental_cycle,
)


IDENTITY = "a" * 64


class CycleStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.database = Path(temporary.name) / "cycles.sqlite3"
        self.connection = sqlite3.connect(self.database)
        self.addCleanup(self.connection.close)
        initialize_cycle_store(self.connection)

    def save(self, *, identity=IDENTITY, inputs=None, results=None):
        return save_experimental_cycle(
            self.connection,
            identity_sha256=identity,
            inputs={"scenario": "fictional"} if inputs is None else inputs,
            results={"path_count": 10} if results is None else results,
        )

    def test_new_cycle_is_inserted(self):
        self.assertTrue(self.save())

        row = self.connection.execute(
            """
            SELECT model_name, calibrated_to_market,
                   complete_portfolio_valuation,
                   portfolio_risk_measure
            FROM experimental_cycles
            WHERE identity_sha256 = ?
            """,
            (IDENTITY,),
        ).fetchone()

        self.assertEqual(row, (
            "fictional-known-coupon-paths", 0, 0, 0
        ))

    def test_duplicate_does_not_overwrite_result(self):
        self.assertTrue(self.save())
        self.assertFalse(self.save())

        stored = self.connection.execute(
            """
            SELECT results_json
            FROM experimental_cycles
            WHERE identity_sha256 = ?
            """,
            (IDENTITY,),
        ).fetchone()[0]

        self.assertEqual(stored, '{"path_count":10}')

        count = self.connection.execute(
            "SELECT COUNT(*) FROM experimental_cycles"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_same_identity_with_different_data_is_rejected(self):
        self.assertTrue(self.save())

        for changes in (
            {"inputs": {"scenario": "changed"}},
            {"results": {"path_count": 999}},
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(RuntimeError, "different data"):
                    self.save(**changes)

        stored = self.connection.execute(
            """
            SELECT inputs_json, results_json
            FROM experimental_cycles
            WHERE identity_sha256 = ?
            """,
            (IDENTITY,),
        ).fetchone()

        self.assertEqual(stored, (
            '{"scenario":"fictional"}',
            '{"path_count":10}',
        ))

    def test_different_identity_can_be_inserted(self):
        self.assertTrue(self.save())
        self.assertTrue(self.save(identity="b" * 64))

        count = self.connection.execute(
            "SELECT COUNT(*) FROM experimental_cycles"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_initialization_is_idempotent(self):
        initialize_cycle_store(self.connection)
        self.assertTrue(self.save())
        initialize_cycle_store(self.connection)

        count = self.connection.execute(
            "SELECT COUNT(*) FROM experimental_cycles"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_invalid_identity_is_rejected(self):
        for identity in ("invalid", "A" * 64, None):
            with self.subTest(identity=identity):
                with self.assertRaises(ValueError):
                    self.save(identity=identity)

        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM experimental_cycles"
            ).fetchone()[0],
            0,
        )

    def test_invalid_json_is_rejected(self):
        for inputs, results in (
            ([], {}),
            ({}, []),
            ({"invalid": float("nan")}, {}),
            ({}, {"invalid": object()}),
        ):
            with self.subTest(inputs=inputs, results=results):
                with self.assertRaises(ValueError):
                    self.save(inputs=inputs, results=results)

        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM experimental_cycles"
            ).fetchone()[0],
            0,
        )

    def test_database_rejects_full_valuation_flags(self):
        self.assertTrue(self.save())

        for column in (
            "calibrated_to_market",
            "complete_portfolio_valuation",
            "portfolio_risk_measure",
        ):
            with self.subTest(column=column):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        f"UPDATE experimental_cycles SET {column} = 1 "
                        "WHERE identity_sha256 = ?",
                        (IDENTITY,),
                    )

        row = self.connection.execute(
            """
            SELECT calibrated_to_market,
                   complete_portfolio_valuation,
                   portfolio_risk_measure
            FROM experimental_cycles
            WHERE identity_sha256 = ?
            """,
            (IDENTITY,),
        ).fetchone()
        self.assertEqual(row, (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
