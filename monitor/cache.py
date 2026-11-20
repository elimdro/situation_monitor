"""Small JSON cache and in-flight de-duplication."""

from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from pathlib import Path

from .xclient import XError


class DiskCache:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data: dict = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def get(self, key: str, ttl: float):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if time.time() - item.get("saved", 0) > ttl:
                return None
            return deepcopy(item.get("value"))

    def put(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = {"saved": time.time(), "value": value}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._data), encoding="utf-8")
            temporary.replace(self.path)


class Flights:
    """One producer per key. Later callers wait for that result."""

    def __init__(self):
        self._lock = threading.Lock()
        self._waiters: dict[str, tuple[threading.Event, dict]] = {}

    def do(self, key: str, producer):
        with self._lock:
            existing = self._waiters.get(key)
            if existing:
                event, box = existing
                owner = False
            else:
                event = threading.Event()
                box = {}
                self._waiters[key] = (event, box)
                owner = True
        if not owner:
            event.wait(90)
            if "error" in box:
                raise box["error"]
            if "value" not in box:
                raise XError("Timed out waiting for X.")
            return deepcopy(box["value"])
        try:
            value = producer()
            box["value"] = value
            return deepcopy(value)
        except Exception as exc:
            box["error"] = exc
            raise
        finally:
            event.set()
            with self._lock:
                self._waiters.pop(key, None)
