"""Offline tests for the exclusive Portfolio Quant cycle lock."""

import os
import tempfile
import unittest
from pathlib import Path

from portfolio_quant.cycle_lock import exclusive_cycle_lock


class CycleLockTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data_dir = Path(temporary.name) / "quant-data"
        self.data_dir.mkdir()

    def test_lock_is_created_with_private_permissions(self):
        with exclusive_cycle_lock(self.data_dir):
            lock = self.data_dir / "cycles.lock"
            self.assertTrue(lock.is_file())
            self.assertEqual(lock.stat().st_mode & 0o777, 0o600)

    def test_second_holder_is_refused_and_lock_is_released(self):
        with exclusive_cycle_lock(self.data_dir):
            with self.assertRaisesRegex(
                RuntimeError, "already running"
            ):
                with exclusive_cycle_lock(self.data_dir):
                    self.fail("Concurrent lock was incorrectly acquired")

        with exclusive_cycle_lock(self.data_dir):
            pass

    def test_lock_released_after_exception(self):
        with self.assertRaisesRegex(ValueError, "test failure"):
            with exclusive_cycle_lock(self.data_dir):
                raise ValueError("test failure")

        with exclusive_cycle_lock(self.data_dir):
            pass

    def test_symlinked_directory_is_rejected(self):
        link = self.data_dir.parent / "quant-link"
        link.symlink_to(self.data_dir, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "Unsafe"):
            with exclusive_cycle_lock(link):
                self.fail("Symlinked directory was accepted")

    def test_symlinked_lock_file_is_rejected(self):
        target = self.data_dir / "target"
        target.write_text("unchanged", encoding="utf-8")
        (self.data_dir / "cycles.lock").symlink_to(target)

        with self.assertRaises(OSError):
            with exclusive_cycle_lock(self.data_dir):
                self.fail("Symlinked lock was accepted")

        self.assertEqual(target.read_text(encoding="utf-8"), "unchanged")

    def test_missing_directory_is_rejected(self):
        missing = self.data_dir / "missing"

        with self.assertRaisesRegex(RuntimeError, "missing"):
            with exclusive_cycle_lock(missing):
                self.fail("Missing directory was accepted")


if __name__ == "__main__":
    unittest.main()
