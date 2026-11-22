"""Full-screen lyrics overlay with live line highlighting driven by mpv position."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ytm.services.lyrics import Lyrics
from ytm.services.music import Track

if TYPE_CHECKING:
    from ytm.app import YtmApp


class LyricsScreen(ModalScreen[None]):
    """Overlay showing lyrics for the current track, synced to playback."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("l", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        Binding("j", "scroll_down", "Scroll", show=False),
        Binding("k", "scroll_up", "Scroll up", show=False),
        Binding("down", "scroll_down", show=False),
        Binding("up", "scroll_up", show=False),
        Binding("pagedown", "page_down", show=False),
        Binding("pageup", "page_up", show=False),
        Binding("home", "scroll_home", show=False),
        Binding("end", "scroll_end", show=False),
        Binding("space", "app.toggle_pause", "Play/pause", show=False),
        Binding("n", "app.next_track", "Next", show=False),
        Binding("p", "app.prev_track", "Prev", show=False),
        Binding("+", "app.volume_up", show=False),
        Binding("=", "app.volume_up", show=False),
        Binding("-", "app.volume_down", show=False),
    ]

    CSS = """
    LyricsScreen {
        background: $background 90%;
        align: center middle;
    }
    #lyrics-panel {
        width: 92%;
        height: 92%;
        max-width: 120;
        border: round $accent;
        background: $surface;
        padding: 0 2;
    }
    #lyrics-head {
        width: 100%;
        height: auto;
        padding: 1 0;
        text-style: bold;
        color: $accent;
        content-align: center middle;
        border-bottom: solid $primary;
    }
    #lyrics-scroll {
        height: 1fr;
        padding: 1 0;
    }
    #lyrics-note {
        width: 100%;
        height: 3;
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
    }
    .lyric-line {
        width: 100%;
        text-align: center;
        color: $text;
    }
    .lyric-line.lyric-past {
        color: $text-muted;
    }
    .lyric-line.lyric-current {
        color: $accent;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._track: Track | None = None
        self._lyrics: Lyrics | None = None
        self._lines: list[Static] = []
        self._current: int = -1
        self._last_pos: float = -1.0
        self._fetching = False

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(id="lyrics-head"),
            VerticalScroll(Static("…", id="lyrics-note"), id="lyrics-scroll"),
            id="lyrics-panel",
        )

    async def on_mount(self) -> None:
        panel = self.query_one("#lyrics-panel", Vertical)
        panel.border_title = "l / esc close"
        panel.border_subtitle = "space n p +/−"
        await self._refresh_track()
        self.set_interval(0.3, self._on_tick)

    async def _on_tick(self) -> None:
        await self._refresh_track()
        self._sync_position()

    async def _refresh_track(self) -> None:
        app = self.app  # YtmApp
        track = app.bar.track
        if track is None:
            if self._track is not None:
                self._track = None
                self._set_head(None, None)
                await self._show_note("nothing playing")
            return
        if self._track is not None and track.video_id == self._track.video_id:
            return
        if self._fetching:
            return  # previous fetch will re-dispatch when it completes
        self._track = track
        self._lyrics = None
        self._lines = []
        self._current = -1
        self._last_pos = -1.0
        self._set_head(track, None)
        hit, cached = app.lyrics_service.peek(track.video_id)
        if hit:
            await self._show_lyrics(cached, track)
            return
        await self._show_note(f"fetching lyrics — {track.title}…")
        self._fetching = True
        error: Exception | None = None
        try:
            lyrics = await asyncio.to_thread(app.lyrics_service.fetch, track)
        except Exception as exc:  # noqa: BLE001 - shown in the overlay
            lyrics = None
            error = exc
        finally:
            self._fetching = False
        current = app.bar.track
        if current is None or current.video_id != track.video_id:
            await self._refresh_track()  # track changed mid-fetch
            return
        if error is not None:
            await self._show_note(f"lyrics lookup failed ({type(error).__name__})")
            return
        await self._show_lyrics(lyrics, track)

    async def _show_lyrics(self, lyrics: Lyrics | None, track: Track) -> None:
        if lyrics is None:
            await self._show_note(f"no lyrics found — {track.title}")
            return
        if lyrics.instrumental:
            await self._show_note("instrumental — no lyrics")
            return
        if not lyrics.lines:
            await self._show_note(f"no lyrics found — {track.title}")
            return
        body = self.query_one("#lyrics-scroll", VerticalScroll)
        await body.remove_children()
        self._lines = [
            Static(Text(text if text.strip() else "♪"), classes="lyric-line")
            for _time, text in lyrics.lines
        ]
        await body.mount(*self._lines)
        self._lyrics = lyrics
        self._set_head(track, lyrics)
        if lyrics.synced:
            self._current = -1
            self._last_pos = -1.0
            self._sync_position()
        else:
            body.scroll_home(animate=False)

    async def _show_note(self, message: str) -> None:
        body = self.query_one("#lyrics-scroll", VerticalScroll)
        await body.remove_children()
        self._lines = []
        self._lyrics = None
        self._current = -1
        await body.mount(Static(message, id="lyrics-note", markup=False))

    def _set_head(self, track: Track | None, lyrics: Lyrics | None) -> None:
        head = self.query_one("#lyrics-head", Static)
        if track is None:
            head.update(Text("lyrics", justify="center"))
            return
        if lyrics is None:
            kind = "…"
        elif lyrics.instrumental:
            kind = "instrumental"
        elif lyrics.synced:
            kind = "synced"
        else:
            kind = "plain"
        head.update(
            Text(f"{track.title} — {track.artist}   [{kind}]", justify="center")
        )

    def _sync_position(self) -> None:
        if not self._lyrics or not self._lyrics.synced or not self._lines:
            return
        app = self.app  # YtmApp
        pos = float(app.bar.position or 0.0)
        if abs(pos - self._last_pos) < 1e-6:
            return
        self._last_pos = pos
        idx = -1
        for i, (start, _text) in enumerate(self._lyrics.lines):
            if start <= pos:
                idx = i
            else:
                break
        if idx == self._current:
            return
        self._current = idx
        for i, widget in enumerate(self._lines):
            widget.set_class(i == idx, "lyric-current")
            widget.set_class(i < idx, "lyric-past")
        if 0 <= idx < len(self._lines):
            body = self.query_one("#lyrics-scroll", VerticalScroll)
            body.scroll_to_widget(
                self._lines[idx], center=True, animate=True, duration=0.3
            )

    # --- manual scrolling -------------------------------------------------

    def action_close(self) -> None:
        self.dismiss()

    def action_scroll_down(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_relative(
            y=4, animate=False
        )

    def action_scroll_up(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_relative(
            y=-4, animate=False
        )

    def action_page_down(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_page_down(
            animate=False
        )

    def action_page_up(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_page_up(animate=False)

    def action_scroll_home(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        self.query_one("#lyrics-scroll", VerticalScroll).scroll_end(animate=False)
