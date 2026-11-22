from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual.binding import Binding
from textual.widgets import Static

from ytm.services.music import Track


PLAYBACK_SCREEN_BINDINGS = [
    Binding("space", "app.toggle_pause", "Play/pause", show=False),
    Binding("n", "app.next_track", "Next", show=False),
    Binding("p", "app.prev_track", "Prev", show=False),
    Binding("+", "app.volume_up", show=False),
    Binding("=", "app.volume_up", show=False),
    Binding("-", "app.volume_down", show=False),
]


def format_time(seconds: float) -> str:
    total = int(max(0, seconds))
    return f"{total // 60}:{total % 60:02d}"


class PlaybackBar(Static):
    COMPONENT_CLASSES = {"playback--accent", "playback--muted"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.track: Track | None = None
        self.position = 0.0
        self.duration = 0.0
        self.paused = False
        self.volume = 60.0
        self.status = "Nothing playing"

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
        muted = self.get_component_rich_style("playback--muted")
        if self.track is None:
            return Text(self.status, style=muted, overflow="ellipsis", no_wrap=True)

        width = self.content_size.width
        accent = self.get_component_rich_style("playback--accent")
        marker = "⏸" if self.paused else "▶"
        title = Text.assemble((f"{marker} ", accent), (self.track.title, "bold"))
        if self.track.artist:
            title.append(f" · {self.track.artist}", style=muted)
        volume = f" Vol {int(self.volume)}%"
        if width >= cell_len(volume) + 8:
            title.truncate(width - cell_len(volume), overflow="ellipsis", pad=True)
            title.append(volume, style=muted)
        else:
            title.truncate(width, overflow="ellipsis")

        elapsed = format_time(self.position)
        total = format_time(self.duration) if self.duration > 0 else "--:--"
        bar_width = max(0, width - cell_len(elapsed) - cell_len(total) - 2)
        filled = 0
        if self.duration > 0:
            fraction = min(1.0, max(0.0, self.position / self.duration))
            filled = int(bar_width * fraction)
        progress = Text.assemble(
            (f"{elapsed} ", muted),
            ("━" * filled, accent),
            ("─" * (bar_width - filled), muted),
            (f" {total}", muted),
        )
        progress.truncate(width, overflow="ellipsis")
        return Text("\n", no_wrap=True).join((title, progress))
