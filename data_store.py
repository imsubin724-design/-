"""Validated, atomic file writes shared by collectors and the dashboard."""

import csv
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo


def today_kst():
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


@contextmanager
def file_lock(path, timeout=120):
    path = Path(path)
    with path.open("a+b") as file:
        file.seek(0, 2)
        if file.tell() == 0:
            file.write(b"0")
            file.flush()
        deadline = time.monotonic() + timeout
        while True:
            file.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"File lock timed out: {path}")
                time.sleep(0.1)
        try:
            yield
        finally:
            file.seek(0)
            if os.name == "nt":
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def atomic_text(path, content, encoding="utf-8"):
    path = Path(path)
    with NamedTemporaryFile(mode="w", encoding=encoding, newline="", dir=path.parent,
                            suffix=".tmp", delete=False) as file:
        temp = Path(file.name)
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    try:
        for attempt in range(10):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1)
    finally:
        temp.unlink(missing_ok=True)


def validate_ranking(rows):
    if len(rows) != 6 or sorted(int(row["rank"]) for row in rows) != list(range(1, 7)):
        raise ValueError("TOP 6 must contain ranks 1 through 6 exactly once")
    if any(not row.get("href", "").strip() or not row.get("product", "").strip() for row in rows):
        raise ValueError("Product name and URL are required")
    if len({row["href"] for row in rows}) != 6:
        raise ValueError("Duplicate products in TOP 6")


def save_ranking(filename, rows):
    import io
    fields = ["rank", "product", "href", "image_url", "eye_image_url"]
    validate_ranking([dict(zip(fields, row)) for row in rows])
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(fields)
    writer.writerows(rows)
    atomic_text(filename, output.getvalue(), encoding="utf-8-sig")
