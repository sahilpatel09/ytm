"""Run the real app without external network requests or audible playback."""

import os
import socket
from pathlib import Path
from unittest.mock import patch

from ytm.__main__ import main
from ytm.services.music import Track


STATE = Path(os.environ["XDG_STATE_HOME"])


class RecordingPlayer:
    def __init__(self, callback):
        self.running = False
        self.socket_path = STATE / f"ytm-mpv-{os.getpid()}.sock"
        self.sock = None

    def start(self):
        if os.environ.get("YTM_TEST_MISSING_MPV"):
            raise FileNotFoundError("mpv")
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(self.socket_path))
        self.running = True
        (STATE / "started").write_text(str(os.getpid()))

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.socket_path.unlink(missing_ok=True)
        self.running = False
        (STATE / "closed").write_text(str(os.getpid()))

    def play(self, url):
        (STATE / "played").write_text(url)

    def toggle_pause(self):
        pass

    def adjust_volume(self, delta):
        pass


with (
    patch("ytm.app.MpvPlayer", RecordingPlayer),
    patch("ytm.app.MusicService.search", return_value=[Track("test", "Test song", "Artist")]),
    patch("ytm.app.StreamResolver.resolve", return_value="https://example.test/audio"),
    patch("ytm.app.LyricsService.fetch", return_value=None),
):
    main()
