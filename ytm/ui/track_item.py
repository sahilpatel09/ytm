from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, ListItem

from ytm.services.music import Track


class TrackItem(ListItem):
    def __init__(self, track: Track, marker: str = "") -> None:
        super().__init__(classes="track-item")
        self.track = track
        self.marker = marker

    def compose(self) -> ComposeResult:
        if self.marker:
            yield Label(self.marker, classes="track-marker")
        with Vertical(classes="track-details"):
            with Horizontal(classes="track-line"):
                yield Label(self.track.title, classes="track-title", markup=False)
                if self.track.duration:
                    yield Label(self.track.duration, classes="track-duration", markup=False)
            metadata = " · ".join(filter(None, (self.track.artist, self.track.album)))
            yield Label(metadata, classes="track-metadata", markup=False)
