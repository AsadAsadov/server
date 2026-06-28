from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from typing import Any


@dataclass(frozen=True)
class RamShot:
    agent_name: str
    filename: str
    data: bytes
    created_at: datetime
    metadata: dict[str, Any]


class RamScreenshotStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._shots: dict[str, deque[RamShot]] = defaultdict(deque)
        self._by_filename: dict[str, RamShot] = {}
        self._last: dict[str, RamShot] = {}
        self._last_metadata: dict[str, dict[str, Any]] = {}

    def put(self, agent_name: str, filename: str, data: bytes, created_at: datetime, metadata: dict[str, Any], keep_minutes: int, max_per_agent: int) -> RamShot:
        shot = RamShot(agent_name=agent_name, filename=filename, data=data, created_at=created_at, metadata=dict(metadata))
        with self._lock:
            q = self._shots[agent_name]
            q.appendleft(shot)
            self._by_filename[filename] = shot
            self._last[agent_name] = shot
            self._last_metadata[agent_name] = dict(metadata)
            self.cleanup(keep_minutes, max_per_agent)
            return shot

    def get_by_filename(self, filename: str) -> RamShot | None:
        with self._lock:
            return self._by_filename.get(filename)

    def get_last(self, agent_name: str) -> RamShot | None:
        with self._lock:
            return self._last.get(agent_name)

    def get_last_metadata(self, agent_name: str) -> dict[str, Any] | None:
        with self._lock:
            meta = self._last_metadata.get(agent_name)
            return dict(meta) if meta is not None else None

    def list_recent(self, agent_name: str, since: datetime, offset: int = 0, limit: int = 60) -> list[RamShot]:
        with self._lock:
            shots = [s for s in self._shots.get(agent_name, ()) if s.created_at >= since]
            return shots[offset:offset + limit]

    def count_by_minute(self, agent_name: str, since: datetime) -> dict[str, int]:
        with self._lock:
            buckets: dict[str, int] = {}
            for shot in self._shots.get(agent_name, ()):
                if shot.created_at < since:
                    break
                key = shot.created_at.strftime('%H:%M')
                buckets[key] = buckets.get(key, 0) + 1
            return buckets

    def cleanup(self, keep_minutes: int, max_per_agent: int) -> None:
        limit = datetime.utcnow() - timedelta(minutes=keep_minutes)
        with self._lock:
            for agent_name in list(self._shots.keys()):
                q = self._shots[agent_name]
                while q and (q[-1].created_at < limit or len(q) > max_per_agent):
                    old = q.pop()
                    self._by_filename.pop(old.filename, None)
                if q:
                    self._last[agent_name] = q[0]
                else:
                    self._shots.pop(agent_name, None)
                    self._last.pop(agent_name, None)
                    self._last_metadata.pop(agent_name, None)


ram_screens = RamScreenshotStore()
