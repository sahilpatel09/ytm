from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import ListView, Static

from ytm.services.music import Track
from ytm.ui.track_item import TrackItem


class QueueItemWidget(TrackItem):
    def __init__(self, track: Track, queue_index: int, playing: bool = False) -> None:
        super().__init__(track, marker="▶" if playing else f"{queue_index + 1}.")
        self.queue_index = queue_index
        self.set_class(playing, "-playing")


class QueuePane(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("Queue", classes="pane-title", id="queue-title", markup=False)
        yield Static("Press a on a result to add it", id="queue-empty", classes="empty-hint")
        yield ListView(id="queue-list")
