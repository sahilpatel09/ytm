import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ytm.app import YtmApp
from ytm.services.player import MpvPlayer
from ytm.store import QueueStore


class LifecycleTests(unittest.TestCase):
    def test_cleanup_before_mount_is_safe(self):
        app = YtmApp()
        app.cleanup()
        app.cleanup()

    def test_cleanup_closes_player_after_partial_startup(self):
        with tempfile.TemporaryDirectory() as state:
            app = YtmApp()
            app._cleaned = False
            app._player_ok = False
            app.store = QueueStore(Path(state) / "queues.json")
            app.player = MpvPlayer(lambda *_: None)
            with patch.object(app.player, "close") as close:
                app.cleanup()
                close.assert_called_once_with()
            self.assertTrue(app.store.path.exists())
