from __future__ import annotations

from rich.markup import escape
from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, Static

from ytm.services.music import Track


class QueueItemWidget(ListItem):
    def __init__(self, track: Track, queue_index: int, playing: bool = False) -> None:
        super().__init__()
        self.track = track
        self.queue_index = queue_index
        self.playing = playing

    def compose(self):
        yield Label(self._line())

    def _line(self) -> str:
        marker = "▶ " if self.playing else f"{self.queue_index + 1:2d}."
        t = self.track
        line = f"{marker} {escape(t.title)}  —  {escape(t.artist)}"
        if t.duration:
            line += f"  [{t.duration}]"
        return line


class QueuePane(Vertical):
    def compose(self):
        yield Static("Queue", classes="pane-title", id="queue-title")
        yield Static("Queue is empty — press a on a result to add tracks", id="queue-empty", classes="empty-hint")
        yield ListView(id="queue-list")
