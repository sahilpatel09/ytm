import asyncio
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from aiohttp import ClientSession, WSServerHandshakeError, WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from ytm.web import YtmServer


FIXTURE = Path(__file__).parent / "fixtures" / "web_app.py"


class WebTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.state = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {
            "XDG_STATE_HOME": str(self.state), "XDG_RUNTIME_DIR": str(self.state),
        }))
        self.server = YtmServer(command=shlex.join([sys.executable, str(FIXTURE)]))
        self.client = TestClient(TestServer(await self.server._make_app()))
        self.addAsyncCleanup(self.client.close)
        await self.client.start_server()

    async def wait_for(self, predicate):
        async with asyncio.timeout(10):
            while not predicate():
                await asyncio.sleep(0.02)

    async def connect(self):
        return await self.client.ws_connect("/ws?width=120&height=36")

    async def read_until(self, ws, text):
        output = ""
        async with asyncio.timeout(10):
            while text not in output:
                message = await ws.receive()
                self.assertNotIn(message.type, (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR))
                if message.type == WSMsgType.BINARY:
                    output += message.data.decode("utf-8", errors="replace")
                elif message.type == WSMsgType.TEXT:
                    output += message.data
        return output

    async def test_serves_existing_interface_and_local_assets(self):
        response = await self.client.get("/")
        self.assertEqual(response.status, 200)
        self.assertIn("ytm", await response.text())
        response = await self.client.get("/static/js/textual.js")
        self.assertEqual(response.status, 200)
        ws = await self.connect()
        await self.read_until(ws, "Queue")
        await self.wait_for(lambda: (self.state / "started").exists())
        await ws.close()

    async def test_foreign_origin_and_host_are_rejected_before_startup(self):
        for headers in (
            {"Origin": "https://example.com"},
            {"Origin": "null"},
            {"Host": "example.com", "Origin": "http://example.com"},
        ):
            with self.subTest(headers=headers):
                with self.assertRaises(WSServerHandshakeError) as rejected:
                    await self.client.ws_connect("/ws", headers=headers)
                self.assertEqual(rejected.exception.status, 403)
                self.assertFalse(self.server.session_active)
                self.assertFalse((self.state / "started").exists())

    async def test_simultaneous_pages_can_detect_session_in_use(self):
        first = await self.client.get("/")
        second = await self.client.get("/")
        self.assertEqual(first.status, 200)
        self.assertEqual(second.status, 200)
        self.assertIn("/session-status", await second.text())
        ws = await self.connect()
        response = await self.client.get("/session-status")
        self.assertEqual(await response.json(), {"active": True})
        await ws.close()

    async def test_second_tab_is_rejected_until_cleanup_finishes(self):
        ws = await self.connect()
        await self.wait_for(lambda: (self.state / "started").exists())
        first_pid = int((self.state / "started").read_text())
        response = await self.client.get("/")
        self.assertEqual(response.status, 409)
        self.assertIn("session", (await response.text()).lower())
        with self.assertRaises(WSServerHandshakeError) as rejected:
            await self.connect()
        self.assertEqual(rejected.exception.status, 409)
        self.assertFalse((self.state / "closed").exists())
        await ws.close()
        await self.wait_for(lambda: (self.state / "closed").exists() and not self.server.session_active)
        self.assertFalse((self.state / f"ytm-mpv-{first_pid}.sock").exists())
        with self.assertRaises(ProcessLookupError):
            os.kill(first_pid, 0)
        next_ws = await self.connect()
        await self.wait_for(lambda: int((self.state / "started").read_text()) != first_pid)
        await next_ws.close()

    async def test_search_queue_save_and_ui_quit(self):
        ws = await self.connect()
        await self.read_until(ws, "Queue")
        await ws.send_json(["stdin", "test\r"])
        await self.read_until(ws, "Test song")
        await ws.send_json(["stdin", "a"])
        await self.wait_for(lambda: (self.state / "ytm" / "queues.json").exists())
        saved = json.loads((self.state / "ytm" / "queues.json").read_text())
        self.assertEqual(saved["queues"]["default"]["items"][0]["video_id"], "test")
        await ws.send_json(["stdin", "q"])
        await self.wait_for(lambda: (self.state / "closed").exists() and not self.server.session_active)
        response = await self.client.get("/")
        self.assertEqual(response.status, 200)
        reopened = await self.connect()
        await self.read_until(reopened, "Test song")
        await reopened.close()

    async def test_server_shutdown_cleans_up_active_session(self):
        ws = await self.connect()
        await self.wait_for(lambda: (self.state / "started").exists())
        pid = int((self.state / "started").read_text())
        await self.client.close()
        self.assertTrue((self.state / "closed").exists())
        self.assertFalse((self.state / f"ytm-mpv-{pid}.sock").exists())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    async def test_missing_mpv_preserves_search(self):
        with patch.dict(os.environ, {"YTM_TEST_MISSING_MPV": "1"}):
            ws = await self.connect()
            await self.read_until(ws, "mpv")
            await ws.send_json(["stdin", "test\r"])
            await self.read_until(ws, "Test song")
            await ws.close()

    async def test_startup_failure_releases_session(self):
        self.server.command = shlex.join([sys.executable, "-c", "raise SystemExit(2)"])
        with self.assertLogs("textual-serve", level="ERROR"):
            ws = await self.connect()
            async with asyncio.timeout(10):
                async for _ in ws:
                    pass
        await self.wait_for(lambda: not self.server.session_active)
        self.server.command = shlex.join([sys.executable, str(FIXTURE)])
        ws = await self.connect()
        await self.wait_for(lambda: (self.state / "started").exists())
        await ws.close()

    async def test_crashed_app_cleans_up_remaining_player(self):
        await self.check_crash_cleanup()

    async def test_crashed_app_with_stubborn_player_is_killed(self):
        with patch.dict(os.environ, {"YTM_TEST_IGNORE_TERM": "1"}):
            await self.check_crash_cleanup()

    async def check_crash_cleanup(self):
        self.server.command = shlex.join([
            sys.executable, str(FIXTURE.with_name("crashed_web_app.py")),
        ])
        ws = await self.connect()
        await self.wait_for(lambda: (self.state / "crash-pids").exists())
        app_pid, player_pid = json.loads((self.state / "crash-pids").read_text())
        try:
            await ws.send_json(["stdin", "x"])
            await self.wait_for(lambda: not self.server.session_active)
            self.assertFalse((self.state / f"ytm-mpv-{app_pid}.sock").exists())
            await self.wait_for(lambda: not process_exists(player_pid))
        finally:
            if process_exists(player_pid):
                os.kill(player_pid, signal.SIGKILL)
            await ws.close()

    async def test_timeout_includes_sending_quit(self):
        from ytm.web import YtmAppService

        release = asyncio.Event()
        original_send = YtmAppService.send_meta

        async def stalled_send(service, data):
            await release.wait()
            return await original_send(service, data)

        with (
            patch.object(YtmAppService, "send_meta", stalled_send),
            patch("ytm.web.STOP_TIMEOUT", 0.1),
            self.assertLogs("ytm.web", level="WARNING"),
        ):
            ws = await self.connect()
            await self.wait_for(lambda: (self.state / "started").exists())
            await ws.close()
            stopped = False
            try:
                await asyncio.wait_for(self.wait_for(lambda: not self.server.session_active), 2)
                stopped = True
            except asyncio.TimeoutError:
                pass
            finally:
                release.set()
                await self.wait_for(lambda: not self.server.session_active)
            self.assertTrue(stopped, "shutdown hung while sending quit")


def process_exists(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class ListenerTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_output_follows_successful_bind(self):
        output = StringIO()
        server = YtmServer(port=0)
        with redirect_stdout(output):
            await server.start()
        self.addAsyncCleanup(server.stop)
        self.assertIn(server.public_url, output.getvalue())
        self.assertNotIn(":0", server.public_url)
        async with ClientSession() as client:
            async with client.get(server.public_url) as response:
                self.assertEqual(response.status, 200)

    async def test_occupied_port_emits_no_ready_url(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            server = YtmServer(port=occupied.getsockname()[1])
            output = StringIO()
            with redirect_stdout(output), self.assertRaises(OSError):
                await server.start()
            self.assertEqual(output.getvalue(), "")
            await server.stop()
