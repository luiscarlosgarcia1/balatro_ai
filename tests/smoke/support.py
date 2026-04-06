from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


@contextmanager
def temporary_test_root(prefix: str):
    base = Path("tests_tmp")
    base.mkdir(exist_ok=True)
    root = base / f"{prefix}_{uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
        try:
            base.rmdir()
        except OSError:
            pass
