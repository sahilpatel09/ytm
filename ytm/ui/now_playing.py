"""Full-screen track details, cover art, and live lyrics."""

from __future__ import annotations

from functools import partial
from io import BytesIO
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit
from urllib.request import urlopen

from PIL import Image
from rich.color import Color
from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ytm.services.music import Track
from ytm.ui.lyrics import LYRICS_REFRESH_INTERVAL, LyricsPane
from ytm.ui.playback_bar import PLAYBACK_SCREEN_BINDINGS, format_time

if TYPE_CHECKING:
    from textual.worker import Worker
    from textual_image.widget import TGPImage

    from ytm.app import YtmApp

MAX_COVER_BYTES = 4 * 1024 * 1024
MAX_COVER_CELLS = 32


def fetch_cover(url: str) -> Image.Image | None:
    if urlsplit(url).scheme not in {"http", "https"}:
        return None
    with urlopen(url, timeout=5) as response:
        data = response.read(MAX_COVER_BYTES + 1)
    if len(data) > MAX_COVER_BYTES:
        return None
    with Image.open(BytesIO(data)) as source:
        source.thumbnail((512, 512), Image.Resampling.LANCZOS)
        return source.convert("RGB")


class CoverArt(Vertical):
    def __init__(self, native_cover: type[TGPImage] | None, *, id: str) -> None:
        self._cells = CellCover()
        self._native = native_cover(id="now-playing-native-cover") if native_cover else None
        super().__init__(id=id)
        self._image: Image.Image | None = None

    def compose(self) -> ComposeResult:
        yield self._cells
        if self._native is not None:
            yield self._native

    def set_image(self, image: Image.Image | None, *, loading: bool = False) -> None:
        self._image = image
        if self._native is None:
            self._cells.set_image(image, loading=loading)
            return

        self._cells.display = image is None
        self._native.display = image is not None
        if image is None:
            self._cells.set_image(None, loading=loading)
        self.set_active(self.screen.is_current)

    def set_active(self, active: bool) -> None:
        if self._native is not None:
            image = self._image if active else None
            if self._native.image is not image:
                self._native.image = image

    def on_unmount(self) -> None:
        self.set_active(False)


class CellCover(Static):
    def __init__(self) -> None:
        super().__init__("Cover art unavailable", id="now-playing-cell-cover")
        self._image: Image.Image | None = None
        self._rendered_width = 0

    def set_image(self, image: Image.Image | None, *, loading: bool = False) -> None:
        self._image = image
        self._rendered_width = 0
        if image is None:
            self.update("Loading cover art…" if loading else "Cover art unavailable")
        else:
            self._render_image()

    def on_resize(self) -> None:
        self._render_image()

    def _render_image(self) -> None:
        image = self._image
        available = self.content_size.width
        if image is None or available <= 0 or available == self._rendered_width:
            return
        self._rendered_width = available
        aspect = image.width / image.height
        width = min(available, MAX_COVER_CELLS, max(1, round(MAX_COVER_CELLS * aspect)))
        rows = min(MAX_COVER_CELLS // 2, max(1, round(width / (2 * aspect))))
        pixels = image.resize((width, rows * 2), Image.Resampling.LANCZOS).load()

        art = Text(justify="center", no_wrap=True)
        for row in range(rows):
            if row:
                art.append("\n")
            for column in range(width):
                upper = Color.from_rgb(*pixels[column, row * 2])
                lower = Color.from_rgb(*pixels[column, row * 2 + 1])
                art.append("▀", Style(color=upper, bgcolor=lower))
        self.update(art)


class NowPlayingScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("s", "close", "Close", show=False),
        Binding("escape", "close", "Close", show=False),
        Binding("question_mark", "app.show_help", "Help", show=False),
        Binding("f1", "app.show_help", show=False),
        Binding("ctrl+up", "app.volume_up", show=False),
        Binding("ctrl+down", "app.volume_down", show=False),
        *PLAYBACK_SCREEN_BINDINGS,
    ]

    def __init__(self, *, native_cover: type[TGPImage] | None = None) -> None:
        super().__init__()
        self._cover = CoverArt(native_cover, id="now-playing-cover")
        self._track: Track | None = None
        self._cover_lookup: Worker[Image.Image | None] | None = None

    def compose(self) -> ComposeResult:
        yield Static("Now Playing", id="now-playing-heading")
        with Vertical(id="now-playing-body"):
            with VerticalScroll(id="now-playing-details"):
                yield Static(id="now-playing-title", markup=False)
                yield Static(id="now-playing-artist", markup=False)
                yield Static(id="now-playing-album", markup=False)
                yield Static(id="now-playing-status", markup=False)
                yield self._cover
            with Vertical(id="now-playing-lyrics"):
                yield Static("Lyrics", classes="now-playing-lyrics-title")
                yield LyricsPane(id="lyrics-scroll")
        yield Static("s / Esc close  ·  ? help", id="now-playing-controls")

    async def on_mount(self) -> None:
        self.query_one("#now-playing-details").focus()
        self._show_track(cast("YtmApp", self.app).bar.track)
        await self._refresh_playback()
        self.set_interval(LYRICS_REFRESH_INTERVAL, self._refresh_playback)

    def on_screen_suspend(self) -> None:
        self._cover.set_active(False)

    async def on_screen_resume(self) -> None:
        await self._refresh_playback()
        self._cover.set_active(self.is_current)

    async def _refresh_playback(self) -> None:
        bar = cast("YtmApp", self.app).bar
        track = bar.track
        if track != self._track:
            self._show_track(track)
        if self._cover_lookup is not None and self._cover_lookup.is_finished:
            self._cover.set_image(self._cover_lookup.result)
            self._cover_lookup = None
        if track is not None:
            elapsed = format_time(bar.position)
            total = (
                format_time(bar.duration) if bar.duration > 0 else track.duration or "--:--"
            )
            state = "Paused" if bar.paused else "Playing"
            text = f"{state}  ·  {elapsed} / {total}  ·  Vol {int(bar.volume)}%"
            status = self.query_one("#now-playing-status", Static)
            if status.content != text:
                status.update(text)

        lyrics = self.query_one(LyricsPane)
        await lyrics.update_track(track)
        if track != bar.track:
            return
        column = self.query_one("#now-playing-lyrics")
        if column.display != lyrics.has_lyrics:
            column.display = lyrics.has_lyrics
            if lyrics.has_lyrics:
                lyrics.focus()
            elif lyrics.has_focus:
                self.query_one("#now-playing-details").focus()
        lyrics.sync_position(bar.position)

    def _show_track(self, track: Track | None) -> None:
        self._track = track
        if self._cover_lookup is not None:
            self._cover_lookup.cancel()
            self._cover_lookup = None
        title = self.query_one("#now-playing-title", Static)
        title.update(track.title if track else "Nothing playing")
        for field in ("artist", "album"):
            widget = self.query_one(f"#now-playing-{field}", Static)
            value = getattr(track, field, "")
            widget.update(value)
            widget.display = bool(value)
        self.query_one("#now-playing-status").display = track is not None
        self._cover.display = track is not None
        thumbnail = track.thumbnail if track else ""
        self._cover.set_image(None, loading=bool(thumbnail))
        if thumbnail:
            self._cover_lookup = self.run_worker(
                partial(fetch_cover, thumbnail), thread=True, exit_on_error=False
            )

    def action_close(self) -> None:
        self.dismiss()
