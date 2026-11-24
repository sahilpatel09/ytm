from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.theme import Theme
from textual.widgets import Footer, Header, Input, ListView, Static
from textual.widgets.input import Selection

from ytm.queue import PlayQueue
from ytm.services.lyrics import LyricsService
from ytm.services.music import MusicService, Track
from ytm.services.player import MpvPlayer
from ytm.services.resolver import StreamResolver
from ytm.store import QueueStore
from ytm.ui.help import HelpScreen
from ytm.ui.lyrics import LyricsScreen
from ytm.ui.name_prompt import NamePromptScreen
from ytm.ui.now_playing import NowPlayingScreen
from ytm.ui.playback_bar import PlaybackBar
from ytm.ui.queue_view import QueueItemWidget, QueuePane
from ytm.ui.search_view import SearchPane
from ytm.ui.track_item import TrackItem

if TYPE_CHECKING:
    from textual_image.widget import TGPImage

BINDINGS = [
    Binding("slash", "focus_search", "Search"),
    Binding("question_mark", "show_help", "Help"),
    Binding("f1", "show_help", show=False),
    Binding("space", "toggle_pause", "Play/Pause"),
    Binding("n", "next_track", "Next", show=False),
    Binding("p", "prev_track", "Prev", show=False),
    Binding("l", "toggle_lyrics", "Lyrics", show=False),
    Binding("s", "show_now_playing", "Now Playing", show=False),
    Binding("a", "add_to_queue", "Enqueue", show=False),
    Binding("x", "remove_from_queue", "Remove", show=False),
    Binding("[", "prev_queue", "Prev queue", show=False),
    Binding("]", "next_queue", "Next queue", show=False),
    Binding("N", "new_queue", "New queue", show=False),
    Binding("R", "rename_queue", "Rename queue", show=False),
    Binding("j", "cursor_down", show=False),
    Binding("k", "cursor_up", show=False),
    Binding("pagedown", "page_down", show=False),
    Binding("pageup", "page_up", show=False),
    Binding("home", "list_top", show=False),
    Binding("end", "list_bottom", show=False),
    Binding("escape", "leave_input", show=False),
    Binding("1", "select_nth(0)", show=False),
    Binding("2", "select_nth(1)", show=False),
    Binding("3", "select_nth(2)", show=False),
    Binding("4", "select_nth(3)", show=False),
    Binding("5", "select_nth(4)", show=False),
    Binding("6", "select_nth(5)", show=False),
    Binding("7", "select_nth(6)", show=False),
    Binding("8", "select_nth(7)", show=False),
    Binding("9", "select_nth(8)", show=False),
    Binding("0", "select_nth(9)", show=False),
    Binding("+", "volume_up", "Vol+", show=False),
    Binding("=", "volume_up", show=False),
    Binding("-", "volume_down", "Vol-", show=False),
    Binding("ctrl+up", "volume_up", show=False),
    Binding("ctrl+down", "volume_down", show=False),
    Binding("q", "quit", "Quit", show=False),
]

YTM_THEME = Theme(
    name="ytm",
    primary="#d58b80",
    accent="#f29b8b",
    foreground="#f2ebe8",
    background="#161518",
    surface="#1f1d21",
    panel="#29262b",
)


class YtmApp(App):
    TITLE = "ytm"
    SUB_TITLE = "youtube music"
    CSS_PATH = "ytm.tcss"
    HORIZONTAL_BREAKPOINTS = [(80, "-wide")]
    BINDINGS = BINDINGS

    # -- lifecycle --------------------------------------------------------

    def __init__(self, *, native_cover: type[TGPImage] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._native_cover = native_cover
        self._cleaned = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main"):
            yield SearchPane()
            yield QueuePane()
        yield PlaybackBar(id="playback")
        footer = Footer(show_command_palette=False)
        footer.compact = True
        yield footer

    async def on_mount(self) -> None:
        import atexit

        self.register_theme(YTM_THEME)
        preferred_theme = self.get_theme(os.environ.get("TEXTUAL_THEME", YTM_THEME.name))
        self.theme = (preferred_theme or YTM_THEME).name
        self.music = MusicService()
        self.resolver = StreamResolver()
        self.lyrics_service = LyricsService()
        self.store = QueueStore()
        try:
            self.store.load()
        except Exception:
            pass
        self.results: list[Track] = []
        self._player_ok = False
        self.bar = self.query_one("#playback", PlaybackBar)
        self.player = MpvPlayer(self._on_player_event)
        try:
            self.player.start()
            self._player_ok = True
        except FileNotFoundError:
            self.notify("mpv not found — search works, playback needs mpv", severity="warning")
        except Exception as exc:
            self.notify(f"mpv failed to start: {exc}", severity="error")
        atexit.register(self.cleanup)
        await self._rebuild_queue()
        self.query_one("#search-input", Input).focus()

    def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        try:
            self.store.save()
        except Exception:
            pass
        if hasattr(self, "player"):
            try:
                self.player.close()
            except Exception:
                pass

    # -- queue store -------------------------------------------------------

    @property
    def queue(self) -> PlayQueue:
        return self.store.active

    def _persist(self) -> None:
        try:
            self.store.save()
        except Exception as exc:
            self.notify(f"failed to save queues: {exc}", severity="warning")

    def _update_queue_title(self) -> None:
        title = self.query_one("#queue-title", Static)
        title.update(f"Queue · {self.store.active_name} · {len(self.queue)}")

    # -- search -----------------------------------------------------------

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if query.startswith("/"):
            query = query[1:].strip()
        if query:
            self.run_search(query)

    @work(exclusive=True, group="search")
    async def run_search(self, query: str) -> None:
        self.sub_title = f"searching “{query}”…"
        try:
            tracks = await asyncio.to_thread(self.music.search, query)
        except Exception as exc:
            self.sub_title = "search failed"
            self.notify(f"search failed: {exc}", severity="error")
            return
        self.results = tracks
        self.query_one("#results-empty", Static).update("No tracks found")
        await self._rebuild_results()
        results = self.query_one("#results", ListView)
        results.focus()
        if results.index is None and tracks:
            results.index = 0
        self.sub_title = f"{len(tracks)} results for “{query}”"

    async def _rebuild_results(self) -> None:
        results = self.query_one("#results", ListView)
        await results.clear()
        await results.extend([TrackItem(t) for t in self.results])
        if self.results:
            results.index = 0
        self.query_one("#results-empty", Static).display = not bool(self.results)

    @on(ListView.Selected, "#results")
    def on_result_selected(self, event: ListView.Selected) -> None:
        track = getattr(event.item, "track", None)
        if track is not None:
            self.queue.play_now(track)
            self._persist()
            self.start_current()

    # -- queue ------------------------------------------------------------

    @on(ListView.Selected, "#queue-list")
    def on_queue_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, QueueItemWidget) and self.queue.jump(item.queue_index):
            self._persist()
            self.start_current()

    async def _rebuild_queue(self) -> None:
        qlist = self.query_one("#queue-list", ListView)
        playing_id = self.bar.track.video_id if self.bar.track is not None else None
        items = [
            QueueItemWidget(t, i, playing=(playing_id is not None and t.video_id == playing_id))
            for i, t in enumerate(self.queue.items)
        ]
        await qlist.clear()
        await qlist.extend(items)
        current = self.queue.index
        if 0 <= current < len(items):
            qlist.index = current
        elif items and qlist.index is None:
            qlist.index = 0
        self.query_one("#queue-empty", Static).display = not bool(self.queue.items)
        self._update_queue_title()

    def start_current(self) -> None:
        track = self.queue.current
        if track is not None:
            self._start_track(track)

    @work(exclusive=True, group="resolve")
    async def _start_track(self, track: Track) -> None:
        self.bar.set_track(track)
        self.sub_title = f"resolving {track.title}…"
        await self._rebuild_queue()
        if not self._player_ok or not self.player.running:
            self.sub_title = "mpv unavailable"
            self.notify("mpv unavailable — cannot play", severity="warning")
            return
        try:
            url = await asyncio.to_thread(self.resolver.resolve, track.video_id)
        except Exception as exc:
            self.notify(f"resolve failed ({exc}); using direct url", severity="warning")
            url = track.watch_url
        try:
            self.player.play(url)
        except OSError as exc:
            self.sub_title = "playback error"
            self.notify(f"playback error: {exc}", severity="error")
            return
        self.sub_title = self.SUB_TITLE
        self._prefetch_next()
        self._prefetch_lyrics(track)

    @work(group="prefetch", exclusive=True)
    async def _prefetch_next(self) -> None:
        nxt = self.queue.peek_next()
        if nxt is None:
            return
        try:
            await asyncio.to_thread(self.resolver.resolve, nxt.video_id)
        except Exception:
            pass

    @work(group="prefetch-lyrics", exclusive=True)
    async def _prefetch_lyrics(self, track: Track) -> None:
        try:
            await asyncio.to_thread(self.lyrics_service.fetch, track)
        except Exception:
            pass

    # -- playback events (mpv reader thread -> ui thread) -----------------

    def _on_player_event(self, name: str, data: object) -> None:
        try:
            self.call_from_thread(self._handle_player_event, name, data)
        except Exception:
            pass

    def _handle_player_event(self, name: str, data: object) -> None:
        if name == "property":
            prop, value = data  # type: ignore[misc]
            self.bar.on_property(prop, value)
        elif name == "end-file":
            reason = str(data)
            if reason == "eof":
                self.action_next_track()
            elif reason == "error":
                self.notify("track failed to play — skipping", severity="error")
                self.action_next_track()

    # -- navigation helpers -----------------------------------------------

    def _focused_list(self) -> ListView | None:
        focused = self.focused
        return focused if isinstance(focused, ListView) else None

    def _move(self, delta: int) -> None:
        lv = self._focused_list()
        if lv is None or not lv.children:
            return
        base = lv.index if lv.index is not None else 0
        lv.index = base + delta

    def _focus_list(self, widget_id: str) -> ListView | None:
        lv = self.query_one(f"#{widget_id}", ListView)
        if lv.children:
            lv.focus()
            if lv.index is None:
                lv.index = 0
            return lv
        return None

    # -- actions ----------------------------------------------------------

    def action_focus_search(self) -> None:
        inp = self.query_one("#search-input", Input)
        inp.focus()
        inp.selection = Selection(0, len(inp.value))

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_leave_input(self) -> None:
        if isinstance(self.focused, Input):
            self._focus_list("results") or self._focus_list("queue-list")

    def action_cursor_down(self) -> None:
        self._move(1)

    def action_cursor_up(self) -> None:
        self._move(-1)

    def action_page_down(self) -> None:
        self._move(10)

    def action_page_up(self) -> None:
        self._move(-10)

    def action_list_top(self) -> None:
        lv = self._focused_list()
        if lv is not None and lv.children:
            lv.index = 0

    def action_list_bottom(self) -> None:
        lv = self._focused_list()
        if lv is not None and lv.children:
            lv.index = len(lv.children) - 1

    async def action_select_nth(self, n: int) -> None:
        focused = self.focused
        if focused is None:
            return
        if focused.id == "results":
            if 0 <= n < len(self.results):
                self.queue.play_now(self.results[n])
                self._persist()
                self.start_current()
        elif focused.id == "queue-list":
            if self.queue.jump(n):
                self._persist()
                self.start_current()

    def action_toggle_pause(self) -> None:
        if not (self._player_ok and self.player.running):
            self.notify("mpv unavailable", severity="warning")
            return
        try:
            self.player.toggle_pause()
        except OSError as exc:
            self.notify(str(exc), severity="error")

    def action_next_track(self) -> None:
        track = self.queue.next()
        if track is None:
            self.sub_title = "end of queue"
            self.bar.set_track(None)
            self.bar.set_status("end of queue — press / to search")
            return
        self._persist()
        self._start_track(track)

    def action_toggle_lyrics(self) -> None:
        if isinstance(self.screen, LyricsScreen):
            self.pop_screen()
            return
        if self.bar.track is None:
            self.notify("nothing playing yet", severity="warning")
            return
        self.push_screen(LyricsScreen())

    def action_show_now_playing(self) -> None:
        if self.bar.track is None:
            self.notify("nothing playing yet", severity="warning")
            return
        self.push_screen(NowPlayingScreen(native_cover=self._native_cover))

    def action_prev_track(self) -> None:
        track = self.queue.prev()
        if track is not None:
            self._persist()
            self._start_track(track)

    async def action_add_to_queue(self) -> None:
        track = self._focused_result()
        if track is None:
            self.notify("no result highlighted")
            return
        self.queue.add(track)
        self._persist()
        await self._rebuild_queue()
        self.notify(f"queued: {track.title}")

    async def action_remove_from_queue(self) -> None:
        qlist = self.query_one("#queue-list", ListView)
        idx = qlist.index
        if idx is None or idx < 0:
            return
        playing_id = self.bar.track.video_id if self.bar.track is not None else None
        if not self.queue.remove(idx, playing_id):
            self.notify("can't remove the playing track")
            return
        self._persist()
        await self._rebuild_queue()

    # -- named queues -----------------------------------------------------

    async def action_prev_queue(self) -> None:
        await self._switch_queue(-1)

    async def action_next_queue(self) -> None:
        await self._switch_queue(1)

    async def _switch_queue(self, delta: int) -> None:
        if len(self.store.names) < 2:
            self.notify("only one queue — press N to create another")
            return
        self.store.cycle(delta)
        self._persist()
        await self._rebuild_queue()
        self.notify(f"queue: {self.store.active_name}")

    def action_new_queue(self) -> None:
        def handle(result: str | None) -> None:
            if not result:
                return
            try:
                self.store.create(result)
            except ValueError as exc:
                self.notify(str(exc), severity="error")
                return
            self._persist()
            self.call_next(self._rebuild_queue)
            self.notify(f"queue: {self.store.active_name}")

        self.push_screen(NamePromptScreen("new queue"), handle)

    def action_rename_queue(self) -> None:
        current = self.store.active_name

        def handle(result: str | None) -> None:
            if not result or result == current:
                return
            try:
                self.store.rename(result)
            except ValueError as exc:
                self.notify(str(exc), severity="error")
                return
            self._persist()
            self.call_next(self._rebuild_queue)
            self.notify(f"renamed to: {self.store.active_name}")

        self.push_screen(NamePromptScreen("rename queue", value=current), handle)

    def action_volume_up(self) -> None:
        self._adjust_volume(5)

    def action_volume_down(self) -> None:
        self._adjust_volume(-5)

    def _adjust_volume(self, delta: int) -> None:
        if not (self._player_ok and self.player.running):
            return
        try:
            self.player.adjust_volume(delta)
        except OSError:
            pass

    def action_quit(self) -> None:
        self.exit()

    # -- helpers ----------------------------------------------------------

    def _focused_result(self) -> Track | None:
        results = self.query_one("#results", ListView)
        idx = results.index
        if idx is None or not (0 <= idx < len(self.results)):
            return None
        return self.results[idx]
