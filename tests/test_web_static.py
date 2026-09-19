"""Offline tests for the compiled dashboard asset reader."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portfolio_quant import web_static


class WebStaticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        self.root = Path(temporary.name)
        self.dist = self.root / "dist"
        self.dist.mkdir()
        (self.dist / "assets").mkdir()

        (self.dist / "index.html").write_bytes(b"<h1>Quant</h1>")
        (self.dist / "assets" / "app.js").write_bytes(b"console.log(1)")
        (self.dist / "assets" / "app.css").write_bytes(b"body{}")
        (self.dist / "favicon.svg").write_bytes(b"<svg></svg>")
        (self.root / "secret.txt").write_text("PRIVATE", encoding="utf-8")

        directory_patch = patch.object(web_static, "DIST_DIR", self.dist)
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

    def test_homepage_and_explicit_index(self):
        for path in ("/", "/index.html"):
            content_type, body = web_static.read_static(path)
            self.assertEqual(content_type, "text/html")
            self.assertEqual(body, b"<h1>Quant</h1>")

    def test_compiled_assets_and_favicon(self):
        for path, expected_body in (
            ("/assets/app.js", b"console.log(1)"),
            ("/assets/app.css", b"body{}"),
            ("/favicon.svg", b"<svg></svg>"),
        ):
            content_type, body = web_static.read_static(path)
            self.assertTrue(content_type)
            self.assertEqual(body, expected_body)

    def test_unknown_paths_and_traversal_are_refused(self):
        for path in (
            "/secret.txt",
            "/assets/../index.html",
            "/assets/../../secret.txt",
            "/assets/nested/file.js",
            "/api/overview",
        ):
            with self.subTest(path=path):
                with self.assertRaises(FileNotFoundError):
                    web_static.read_static(path)

    def test_symlinked_asset_is_refused(self):
        (self.dist / "assets" / "leak.js").symlink_to(
            self.root / "secret.txt"
        )
        with self.assertRaises(FileNotFoundError):
            web_static.read_static("/assets/leak.js")

    def test_symlinked_dist_directory_is_refused(self):
        link = self.root / "linked-dist"
        link.symlink_to(self.dist, target_is_directory=True)
        with patch.object(web_static, "DIST_DIR", link):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                web_static.read_static("/")

    def test_missing_build_is_not_created(self):
        missing = self.root / "missing-dist"
        with patch.object(web_static, "DIST_DIR", missing):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                web_static.read_static("/")

        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
