"""Lyrics widgets with live highlighting driven by mpv position."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ytm.services.lyrics import Lyrics
from ytm.services.music import Track
from ytm.ui.playback_bar import PLAYBACK_SCREEN_BINDINGS

if TYPE_CHECKING:
    from textual.worker import Worker

    from ytm.app import YtmApp

LYRICS_REFRESH_INTERVAL = 0.3


class LyricsPane(VerticalScroll):
    """Resolve, display, and scroll the lyrics for the current track."""

    BINDINGS = [
        Binding("j", "scroll_down", show=False),
        Binding("k", "scroll_up", show=False),
    ]

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(self._note("nothing playing"), id=id)
        self._track: Track | None = None
        self._lookup: Worker[Lyrics | None] | None = None
        self._lyrics: Lyrics | None = None
        self._lines: list[Static] = []
        self._current = -1
        self._last_pos = -1.0

    @property
    def has_lyrics(self) -> bool:
        return bool(self._lines)

    @property
    def heading(self) -> str:
        if self._track is None:
            return "lyrics"
        if self._lyrics is None:
            kind = "…"
        elif self._lyrics.instrumental:
            kind = "instrumental"
        elif self._lyrics.synced:
            kind = "synced"
        else:
            kind = "plain"
        return f"{self._track.title} — {self._track.artist}   [{kind}]"

    async def update_track(self, track: Track | None) -> None:
        if track != self._track:
            await self._load_track(track)
        elif track is not None and self._lookup is not None and self._lookup.is_finished:
            lookup, self._lookup = self._lookup, None
            if lookup.error is not None:
                await self._show_note(f"lyrics lookup failed ({type(lookup.error).__name__})")
            else:
                await self._show_lyrics(lookup.result, track)

    async def _load_track(self, track: Track | None) -> None:
        if self._lookup is not None:
            self._lookup.cancel()
            self._lookup = None
        self._track = track
        self._lyrics = None
        self._lines = []
        self._current = -1
        self._last_pos = -1.0
        self.scroll_home(animate=False)
        if track is None:
            await self._show_note("nothing playing")
            return

        service = cast("YtmApp", self.app).lyrics_service
        hit, cached = service.peek(track.video_id)
        if hit:
            await self._show_lyrics(cached, track)
            return
        await self._show_note(f"fetching lyrics — {track.title}…")
        self._lookup = self.run_worker(
            partial(service.fetch, track), thread=True, exit_on_error=False
        )

    async def _show_lyrics(self, lyrics: Lyrics | None, track: Track) -> None:
        self._lyrics = lyrics
        if lyrics is None or (not lyrics.instrumental and not lyrics.lines):
            await self._show_note(f"no lyrics found — {track.title}")
            return
        if lyrics.instrumental:
            await self._show_note("instrumental — no lyrics")
            return

        await self.remove_children()
        self._lines = [
            Static(Text(text if text.strip() else "♪"), classes="lyric-line")
            for _time, text in lyrics.lines
        ]
        await self.mount(*self._lines)

    @staticmethod
    def _note(message: str) -> Static:
        return Static(message, id="lyrics-note", markup=False)

    async def _show_note(self, message: str) -> None:
        await self.remove_children()
        await self.mount(self._note(message))

    def sync_position(self, position: float) -> None:
        if not self._lyrics or not self._lyrics.synced or not self._lines:
            return
        if abs(position - self._last_pos) < 1e-6:
            return
        self._last_pos = position
        current = -1
        for index, (start, _text) in enumerate(self._lyrics.lines):
            if start > position:
                break
            current = index
        if current == self._current:
            return
        self._current = current
        for index, line in enumerate(self._lines):
            line.set_class(index == current, "lyric-current")
            line.set_class(index < current, "lyric-past")
        if current < 0:
            self.scroll_home(animate=False)
        else:
            self._center_current(animate=True)

    def on_resize(self) -> None:
        self._center_current(animate=False)

    def _center_current(self, *, animate: bool) -> None:
        if self._current >= 0:
            self.call_after_refresh(
                self.scroll_to_widget,
                self._lines[self._current],
                center=True,
                animate=animate,
                duration=LYRICS_REFRESH_INTERVAL,
            )

    def action_scroll_down(self) -> None:
        self.scroll_relative(y=4, animate=False)

    def action_scroll_up(self) -> None:
        self.scroll_relative(y=-4, animate=False)

    def action_page_down(self) -> None:
        self.scroll_page_down(animate=False)

    def action_page_up(self) -> None:
        self.scroll_page_up(animate=False)

    def action_scroll_home(self) -> None:
        self.scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        self.scroll_end(animate=False)


class LyricsScreen(ModalScreen[None]):
    """Overlay showing lyrics for the current track, synced to playback."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("l", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        *PLAYBACK_SCREEN_BINDINGS,
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(id="lyrics-head", classes="dialog-title", markup=False),
            LyricsPane(id="lyrics-scroll"),
            id="lyrics-panel",
            classes="dialog",
        )

    async def on_mount(self) -> None:
        panel = self.query_one("#lyrics-panel", Vertical)
        panel.border_title = "Lyrics"
        panel.border_subtitle = "Esc close"
        self.query_one(LyricsPane).focus()
        await self._refresh_playback()
        self.set_interval(LYRICS_REFRESH_INTERVAL, self._refresh_playback)

    async def _refresh_playback(self) -> None:
        bar = cast("YtmApp", self.app).bar
        track = bar.track
        lyrics = self.query_one(LyricsPane)
        await lyrics.update_track(track)
        if track != bar.track:
            return
        heading = self.query_one("#lyrics-head", Static)
        if heading.content != lyrics.heading:
            heading.update(lyrics.heading)
        lyrics.sync_position(bar.position)

    def action_close(self) -> None:
        self.dismiss()
