"""Exclusive process lock for Portfolio Quant experimental cycles."""

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive_cycle_lock(data_dir: Path):
    """Prevent concurrent calculations across CLI and systemd processes."""
    data_dir = Path(data_dir)

    if data_dir.is_symlink() or not data_dir.is_dir():
        raise RuntimeError("Unsafe or missing Quant data directory")

    lock_path = data_dir / "cycles.lock"
    flags = os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(lock_path, flags, 0o600)

    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError("Unsafe Quant cycle lock file")

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "Another Portfolio Quant cycle is already running"
            ) from exc

        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
