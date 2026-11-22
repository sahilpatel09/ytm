from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from ytm.services.music import Track


def _fmt(seconds: float) -> str:
    total = int(max(0, seconds))
    return f"{total // 60}:{total % 60:02d}"


class PlaybackBar(Static):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.track: Track | None = None
        self.position = 0.0
        self.duration = 0.0
        self.paused = False
        self.volume = 60.0
        self.status = "press / to search"

    def set_track(self, track: Track | None) -> None:
        self.track = track
        self.position = 0.0
        self.duration = float(track.duration_seconds) if track else 0.0
        self.refresh()

    def set_status(self, status: str) -> None:
        self.status = status
        self.refresh()

    def on_property(self, name: str, data) -> None:
        if name == "time-pos" and data is not None:
            self.position = float(data)
            self.refresh()
        elif name == "duration" and data is not None:
            self.duration = float(data)
            self.refresh()
        elif name == "pause" and data is not None:
            self.paused = bool(data)
            self.refresh()
        elif name == "volume" and data is not None:
            self.volume = float(data)
            self.refresh()

    def render(self) -> Text:
        width = self.size.width or 100
        if self.track is None:
            return Text(f" {self.status}", style="dim")

        marker = "⏸" if self.paused else "▶"
        total = self.duration or float(self.track.duration_seconds or 0)
        bar_width = 24 if width >= 90 else 12
        if total > 0:
            filled = min(bar_width, max(0, int(bar_width * self.position / total)))
        else:
            filled = 0
        bar = "█" * filled + "░" * (bar_width - filled)
        right = f" {_fmt(self.position)}/{_fmt(total)} [{bar}] vol {int(self.volume)} "

        title = f"{self.track.title} — {self.track.artist}"
        space = width - len(right) - 4
        if space < 8:
            return Text(f" {marker} {right.strip()}")
        if len(title) > space:
            title = title[: space - 1] + "…"
        return Text(f" {marker} {title}{right.rjust(width - len(title) - 3)}")
