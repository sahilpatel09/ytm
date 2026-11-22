from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ytm.queue import PlayQueue

DEFAULT_QUEUE = "default"


def default_state_path() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    if not state_home:
        state_home = str(Path.home() / ".local" / "state")
    return Path(state_home) / "ytm" / "queues.json"


class QueueStore:
    """Named play queues persisted as a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_state_path()
        self._queues: dict[str, PlayQueue] = {DEFAULT_QUEUE: PlayQueue()}
        self._active: str = DEFAULT_QUEUE

    @property
    def active(self) -> PlayQueue:
        return self._queues[self._active]

    @property
    def active_name(self) -> str:
        return self._active

    @property
    def names(self) -> list[str]:
        return sorted(self._queues)

    def load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        queues = data.get("queues")
        if not isinstance(queues, dict) or not queues:
            return
        loaded: dict[str, PlayQueue] = {}
        for name, state in queues.items():
            if not isinstance(name, str) or not name or not isinstance(state, dict):
                continue
            loaded[name] = PlayQueue.from_state(state)
        if not loaded:
            return
        self._queues = loaded
        active = data.get("active")
        if isinstance(active, str) and active in loaded:
            self._active = active
        else:
            self._active = DEFAULT_QUEUE if DEFAULT_QUEUE in loaded else sorted(loaded)[0]

    def save(self) -> None:
        data = {
            "version": 1,
            "active": self._active,
            "queues": {name: q.to_state() for name, q in self._queues.items()},
        }
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=parent, prefix=".queues-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def switch(self, name: str) -> PlayQueue:
        if name not in self._queues:
            raise KeyError(name)
        self._active = name
        return self._queues[name]

    def cycle(self, delta: int) -> PlayQueue:
        names = self.names
        if not names:
            return self.active
        i = names.index(self._active) if self._active in names else 0
        self._active = names[(i + delta) % len(names)]
        return self._queues[self._active]

    def create(self, name: str) -> PlayQueue:
        name = name.strip()
        if not name:
            raise ValueError("empty queue name")
        if name not in self._queues:
            self._queues[name] = PlayQueue()
        self._active = name
        return self._queues[name]

    def rename(self, new_name: str) -> PlayQueue:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("empty queue name")
        if new_name == self._active:
            return self.active
        if new_name in self._queues:
            raise ValueError(f"queue “{new_name}” already exists")
        self._queues[new_name] = self._queues.pop(self._active)
        self._active = new_name
        return self.active
