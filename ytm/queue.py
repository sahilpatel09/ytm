from __future__ import annotations

from dataclasses import asdict

from ytm.services.music import Track


class PlayQueue:
    def __init__(self) -> None:
        self._items: list[Track] = []
        self._index: int = -1

    def to_state(self) -> dict:
        return {
            "index": self._index,
            "items": [asdict(t) for t in self._items],
        }

    @classmethod
    def from_state(cls, state: dict) -> PlayQueue:
        queue = cls()
        raw_items = state.get("items") or []
        for item in raw_items:
            try:
                queue._items.append(Track(**item))
            except TypeError:
                continue
        index = state.get("index", -1)
        queue._index = index if isinstance(index, int) else -1
        if not (-1 <= queue._index < len(queue._items)):
            queue._index = -1
        return queue

    @property
    def items(self) -> list[Track]:
        return list(self._items)

    @property
    def index(self) -> int:
        return self._index

    @property
    def current(self) -> Track | None:
        if 0 <= self._index < len(self._items):
            return self._items[self._index]
        return None

    def __len__(self) -> int:
        return len(self._items)

    def add(self, track: Track) -> None:
        self._items.append(track)

    def play_now(self, track: Track) -> Track:
        for i, t in enumerate(self._items):
            if t.video_id == track.video_id:
                self._index = i
                return t
        if self._index < 0:
            self._items.insert(0, track)
            self._index = 0
        else:
            self._items.insert(self._index + 1, track)
            self._index += 1
        return track

    def jump(self, index: int) -> Track | None:
        if 0 <= index < len(self._items):
            self._index = index
            return self._items[self._index]
        return None

    def next(self) -> Track | None:
        if self._index < 0 and self._items:
            self._index = 0
            return self._items[0]
        if self._index + 1 < len(self._items):
            self._index += 1
            return self._items[self._index]
        return None

    def prev(self) -> Track | None:
        if self._index < 0:
            if self._items:
                self._index = 0
                return self._items[0]
            return None
        if self._index == 0:
            return None
        self._index -= 1
        return self._items[self._index]

    def peek_next(self) -> Track | None:
        i = self._index + 1 if self._index >= 0 else 0
        if 0 <= i < len(self._items):
            return self._items[i]
        return None

    def remove(self, index: int, playing_id: str | None = None) -> bool:
        if not (0 <= index < len(self._items)):
            return False
        if playing_id is not None and self._items[index].video_id == playing_id:
            return False
        del self._items[index]
        if index < self._index:
            self._index -= 1
        elif index == self._index:
            self._index = -1 if not self._items else min(self._index, len(self._items) - 1)
        return True
