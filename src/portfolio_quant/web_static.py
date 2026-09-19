"""Read only approved, compiled dashboard assets."""

import mimetypes
import re
from pathlib import Path


DIST_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"
ASSET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def read_static(path: str) -> tuple[str, bytes]:
    """Return an approved compiled asset; never browse directories."""
    if path in ("/", "/index.html"):
        relative = Path("index.html")
    elif path in ("/favicon.svg", "/icons.svg"):
        relative = Path(path.lstrip("/"))
    elif path.startswith("/assets/") and ASSET_NAME.fullmatch(path[8:]):
        relative = Path("assets") / path[8:]
    else:
        raise FileNotFoundError("Asset not found")

    if DIST_DIR.is_symlink() or not DIST_DIR.is_dir():
        raise RuntimeError("Compiled dashboard is unavailable")

    target = DIST_DIR / relative

    if target.is_symlink() or not target.is_file():
        raise FileNotFoundError("Asset not found")

    if target.resolve() != (DIST_DIR.resolve() / relative):
        raise FileNotFoundError("Asset not found")

    content_type = mimetypes.guess_type(target.name)[0]
    if content_type is None:
        raise FileNotFoundError("Unsupported asset type")

    return content_type, target.read_bytes()
