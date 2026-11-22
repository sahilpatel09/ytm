import os
import unittest
from io import BytesIO
from threading import Event
from unittest.mock import patch

from PIL import Image
from textual.widgets import Input, Static
from textual_image import renderable
from textual_image.widget import TGPImage

from ytm.__main__ import native_cover_widget
from ytm.app import YtmApp
from ytm.services.lyrics import Lyrics
from ytm.services.music import Track
from ytm.ui.help import HelpScreen
from ytm.ui.lyrics import LyricsPane, LyricsScreen
from ytm.ui.now_playing import CellCover, NowPlayingScreen


class NativeCoverSelectionTests(unittest.TestCase):
    def test_requires_supported_terminal_and_successful_probe(self):
        with (
            patch.dict(os.environ, {"TERM": "xterm-ghostty"}),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch.object(renderable, "Image", renderable.TGPImage),
        ):
            self.assertIs(native_cover_widget(), TGPImage)
            with patch.dict(os.environ, {"TERM": "xterm-kitty"}):
                self.assertIs(native_cover_widget(), TGPImage)
            with patch.object(renderable, "Image", renderable.HalfcellImage):
                self.assertIsNone(native_cover_widget())
            with patch("sys.stdout.isatty", return_value=False):
                self.assertIsNone(native_cover_widget())
            with patch.dict(os.environ, {"TERM": "xterm-256color"}):
                self.assertIsNone(native_cover_widget())


class NowPlayingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for target in ("QueueStore.load", "QueueStore.save", "MpvPlayer.start", "MpvPlayer.close"):
            self.enterContext(patch(f"ytm.app.{target}"))
        self.app = YtmApp()
        self.pilot = await self.enterAsyncContext(self.app.run_test(size=(120, 36)))
        self.addCleanup(self.app.cleanup)

    async def wait_for(self, predicate):
        for _ in range(30):
            if predicate():
                return
            await self.pilot.pause(0.1)
        self.assertTrue(predicate())

    async def open_now_playing(self):
        self.app.default_screen.set_focus(self.app.query_one("#queue-list"))
        await self.pilot.press("s")
        self.assertIsInstance(self.app.screen, NowPlayingScreen)
        return self.app.screen

    def tick(self, position):
        self.app._handle_player_event("property", ("time-pos", position))

    @staticmethod
    def active_line(pane):
        return next(iter(pane.query(".lyric-current")), None)

    async def test_shortcut_help_and_playback_actions(self):
        await self.pilot.press("s")
        self.assertEqual(self.app.query_one("#search-input", Input).value, "s")
        self.assertIs(self.app.screen, self.app.default_screen)

        queue = self.app.query_one("#queue-list")
        self.app.default_screen.set_focus(queue)
        with patch.object(self.app, "notify") as notify:
            await self.pilot.press("s")
            notify.assert_called_once_with("nothing playing yet", severity="warning")
        self.app.bar.set_track(Track("a", "Title", "Artist"))
        with patch.object(self.app.lyrics_service, "peek", return_value=(True, None)):
            await self.open_now_playing()
            await self.pilot.press("question_mark")
            self.assertIsInstance(self.app.screen, HelpScreen)
            help_text = self.app.screen.query_one("#help-scroll Static", Static).content
            self.assertIn("full-screen Now Playing", help_text)
            await self.pilot.press("escape")

            with (
                patch.object(self.app, "action_toggle_pause") as pause,
                patch.object(self.app, "action_next_track") as next_track,
                patch.object(self.app, "action_prev_track") as previous,
                patch.object(self.app, "action_volume_up") as volume_up,
                patch.object(self.app, "action_volume_down") as volume_down,
            ):
                await self.pilot.press("space", "n", "p", "+", "-")
                for action in (pause, next_track, previous, volume_up, volume_down):
                    action.assert_called_once_with()

            await self.pilot.press("s")
            self.assertIs(self.app.screen, self.app.default_screen)
            self.assertIs(self.app.focused, queue)
            await self.open_now_playing()
            await self.pilot.press("escape")
            self.assertIs(self.app.screen, self.app.default_screen)

    async def test_synced_lyrics_and_responsive_layout(self):
        track = Track("a", "[Title]", "Artist", "Album", duration_seconds=120)
        self.app.bar.set_track(track)
        self.tick(35)
        lyrics = Lyrics([(float(i), f"Line {i}") for i in range(50)], synced=True)
        with patch.object(self.app.lyrics_service, "peek", return_value=(True, lyrics)):
            screen = await self.open_now_playing()
            pane = screen.query_one(LyricsPane)
            self.assertEqual(self.active_line(pane).content.plain, "Line 35")
            self.assertEqual(screen.query_one("#now-playing-title", Static).content, "[Title]")
            self.assertEqual(screen.query_one("#now-playing-album", Static).content, "Album")
            self.assertIn("0:35 / 2:00", screen.query_one("#now-playing-status", Static).content)

            details = screen.query_one("#now-playing-details")
            column = screen.query_one("#now-playing-lyrics")
            self.assertEqual(details.region.width, 60)
            self.assertEqual(column.region.x, details.region.right)
            await self.pilot.resize_terminal(64, 24)
            await self.wait_for(
                lambda: column.region.y == details.region.bottom
                and pane.region.contains_region(self.active_line(pane).region)
            )
            self.tick(4)
            await self.wait_for(lambda: self.active_line(pane).content.plain == "Line 4")
            await self.pilot.press("s", "l")
            self.assertIsInstance(self.app.screen, LyricsScreen)
            pane = self.app.screen.query_one(LyricsPane)
            self.assertEqual(self.active_line(pane).content.plain, "Line 4")
            self.tick(35)
            await self.wait_for(lambda: self.active_line(pane).content.plain == "Line 35")

    async def test_plain_and_missing_lyrics_with_valid_and_failed_artwork(self):
        image = BytesIO()
        Image.new("RGB", (16, 16), (20, 60, 100)).save(image, "PNG")
        plain = Lyrics([(0.0, f"Line {i}") for i in range(50)])
        self.app.bar.set_track(Track("plain", "Plain", "Artist", thumbnail="https://example.com/a"))
        with (
            patch.object(
                self.app.lyrics_service, "peek",
                side_effect=lambda video_id: (True, plain if video_id == "plain" else None),
            ),
            patch("ytm.ui.now_playing.urlopen", side_effect=[BytesIO(image.getvalue()), BytesIO(b"invalid")]),
        ):
            screen = await self.open_now_playing()
            pane = screen.query_one(LyricsPane)
            cover = screen.query_one(CellCover)
            await self.wait_for(lambda: not isinstance(cover.content, str))
            self.assertIn("▀", cover.content.plain)
            self.assertEqual(cover.content.spans[0].style.color.triplet, (20, 60, 100))
            self.tick(20)
            await self.pilot.press("end")
            await self.wait_for(lambda: pane.scroll_y > 0)
            self.assertIsNone(self.active_line(pane))

            self.app.bar.set_track(Track("missing", "Missing", "Artist", thumbnail="https://example.com/b"))
            column = screen.query_one("#now-playing-lyrics")
            details = screen.query_one("#now-playing-details")
            await self.wait_for(
                lambda: not column.display and cover.content == "Cover art unavailable"
            )
            self.assertEqual(details.region.width, 120)
            self.app.bar.set_track(Track("no-art", "No artwork", "Artist"))
            title = screen.query_one("#now-playing-title", Static)
            await self.wait_for(lambda: title.content == "No artwork")
            self.assertEqual(cover.content, "Cover art unavailable")

    async def test_track_change_discards_slow_lyrics_and_cover(self):
        old_lyrics_started, old_cover_started, release_old = Event(), Event(), Event()
        old = Track("old", "Old title", "Artist", thumbnail="https://example.com/old")
        new = Track("new", "New title", "Artist", thumbnail="https://example.com/new")
        self.app.bar.set_track(old)

        def fetch_lyrics(track):
            if track == old:
                old_lyrics_started.set()
                release_old.wait(5)
            return Lyrics([(0, track.title)], synced=True)

        def fetch_cover(url):
            if url == old.thumbnail:
                old_cover_started.set()
                release_old.wait(5)
            color = "red" if url == old.thumbnail else "blue"
            return Image.new("RGB", (16, 16), color)

        with (
            patch.object(self.app.lyrics_service, "fetch", side_effect=fetch_lyrics),
            patch("ytm.ui.now_playing.fetch_cover", side_effect=fetch_cover),
        ):
            try:
                screen = await self.open_now_playing()
                await self.wait_for(lambda: old_lyrics_started.is_set() and old_cover_started.is_set())
                self.app.bar.set_track(new)
                pane = screen.query_one(LyricsPane)
                cover = screen.query_one(CellCover)
                await self.wait_for(
                    lambda: self.active_line(pane) is not None
                    and not isinstance(cover.content, str)
                )
            finally:
                release_old.set()
            await self.pilot.pause(0.4)
            self.assertEqual(self.active_line(pane).content.plain, new.title)
            self.assertEqual(cover.content.spans[0].style.color.triplet, (0, 0, 255))

    async def test_native_image_clears_for_help_track_changes_and_close(self):
        first_image = Image.new("RGB", (512, 512), "red")
        second_image = Image.new("RGB", (512, 512), "blue")
        self.app._native_cover = TGPImage
        self.app.bar.set_track(Track("a", "First", "Artist", thumbnail="https://example.com/a"))
        with (
            patch.object(self.app.lyrics_service, "peek", return_value=(True, None)),
            patch("ytm.ui.now_playing.fetch_cover", side_effect=[first_image, second_image]),
            patch("textual_image.renderable.tgp._send_tgp_message") as send,
        ):
            screen = await self.open_now_playing()
            native = screen.query_one(TGPImage)
            await self.wait_for(lambda: native.image is first_image)
            await self.wait_for(lambda: any(call.kwargs.get("U") == 1 for call in send.call_args_list))
            self.assertFalse(screen.query_one(CellCover).display)

            await self.pilot.press("question_mark")
            self.assertIsInstance(self.app.screen, HelpScreen)
            self.assertIsNone(native.image)
            self.assertTrue(any(call.kwargs.get("a") == "d" for call in send.call_args_list))
            await self.pilot.press("escape")
            await self.wait_for(lambda: native.image is first_image)

            self.app.bar.set_track(Track("b", "Second", "Artist", thumbnail="https://example.com/b"))
            await self.wait_for(lambda: native.image is second_image)
            await self.pilot.press("escape")
            self.assertIsNone(native.image)
            self.assertIs(self.app.screen, self.app.default_screen)
