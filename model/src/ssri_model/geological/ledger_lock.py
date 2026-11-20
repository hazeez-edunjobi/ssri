"""Cross-platform exclusive lock for geological JSONL ledger appends."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import TracebackType
from typing import BinaryIO


class JsonlAppendLock:
    """Exclusive lock around append-only ledger writes (Windows + POSIX).

    Uses ``msvcrt.locking`` on Windows and ``fcntl.flock`` elsewhere. Not a
    distributed lock — only coordinates processes on a shared local filesystem.
    """

    def __init__(self, lock_path: Path | str, *, timeout_s: float = 30.0) -> None:
        self.lock_path = Path(lock_path)
        self.timeout_s = timeout_s
        self._fh: BinaryIO | None = None

    def __enter__(self) -> JsonlAppendLock:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.lock_path, "a+b")
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                self._acquire()
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self._fh.close()
                    self._fh = None
                    raise TimeoutError(
                        f"Timed out acquiring ledger lock: {self.lock_path}"
                    )
                time.sleep(0.02)

    def _acquire(self) -> None:
        assert self._fh is not None
        self._fh.seek(0)
        if sys.platform == "win32":
            import msvcrt

            # Ensure at least one byte exists to lock.
            self._fh.seek(0, 2)
            if self._fh.tell() == 0:
                self._fh.write(b"\0")
                self._fh.flush()
            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release(self) -> None:
        if self._fh is None:
            return
        try:
            self._fh.seek(0)
            if sys.platform == "win32":
                import msvcrt

                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._release()
