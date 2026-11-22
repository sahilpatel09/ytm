from __future__ import annotations

from rich.markup import escape
from textual.containers import Vertical
from textual.widgets import Input, Label, ListItem, ListView, Static

from ytm.services.music import Track


class SearchResultItem(ListItem):
    def __init__(self, track: Track) -> None:
        super().__init__()
        self.track = track

    def compose(self):
        yield Label(self._line())

    def _line(self) -> str:
        t = self.track
        line = f"{escape(t.title)}  —  {escape(t.artist)}"
        if t.album:
            line += f"  ·  {escape(t.album)}"
        if t.duration:
            line += f"  [{t.duration}]"
        return line


class SearchPane(Vertical):
    def compose(self):
        yield Input(placeholder="Search YouTube Music  (press / anywhere)", id="search-input")
        yield Static("Results", classes="pane-title")
        yield Static("No results yet — press / to search", id="results-empty", classes="empty-hint")
        yield ListView(id="results")
