from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, ListView, Static


class SearchPane(Vertical):
    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search YouTube Music", id="search-input", compact=True)
        yield Static("Results", classes="pane-title")
        yield Static("Search for a song or artist", id="results-empty", classes="empty-hint")
        yield ListView(id="results")
