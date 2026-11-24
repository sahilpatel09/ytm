"""Serve the shared Textual application locally, with one player session."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import os
from pathlib import Path
import shlex
import signal
import sys

from aiohttp import web
from textual_serve.app_service import AppService
from textual_serve.server import Server, to_int


log = logging.getLogger(__name__)
STOP_TIMEOUT = 10

SESSION_STATUS_SCRIPT = """<script>
const sessionObserver = new MutationObserver(async () => {
    const body = document.body;
    if (!body.classList.contains('-closed') || body.classList.contains('-loaded')) return;
    sessionObserver.disconnect();
    try {
        const response = await fetch('/session-status', {cache: 'no-store'});
        if ((await response.json()).active) {
            document.querySelector('.closed-dialog .message').textContent =
                'A ytm session is already in use. Close the active tab, then retry.';
            body.classList.add('-first-byte');
        }
    } catch (error) {
        // The server may have stopped along with the session.
    }
});
sessionObserver.observe(document.body, {attributes: true, attributeFilter: ['class']});
</script>"""


class YtmAppService(AppService):
    """Own the app process until its player and queue cleanup finishes."""

    async def _open_app_process(self, width: int = 80, height: int = 24):
        # Execute directly so the process we wait for is Python, not a shell.
        self._process = await asyncio.create_subprocess_exec(
            *shlex.split(self.command),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._build_environment(width, height),
            start_new_session=True,
        )
        self._stdin = self._process.stdin
        return self._process

    async def run(self) -> None:
        try:
            await super().run()
        finally:
            await self.remote_close()

    async def on_data(self, payload: bytes) -> None:
        # Keep draining output during app cleanup after the browser disconnects.
        with suppress(ConnectionError, RuntimeError):
            await super().on_data(payload)

    async def stop(self) -> None:
        cleanup = asyncio.create_task(self._stop())
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            # HTTP handler cancellation must not release admission before cleanup.
            await cleanup
            raise

    async def _stop(self) -> None:
        process = self._process
        if process is None:
            return
        try:
            try:
                async with asyncio.timeout(STOP_TIMEOUT):
                    await self._download_manager.cancel_app_downloads(self.app_service_id)
                    with suppress(ConnectionError, RuntimeError):
                        await self.send_meta({"type": "quit"})
                    await process.wait()
            except asyncio.TimeoutError:
                log.warning("ytm session did not stop gracefully; terminating its processes")
        finally:
            # Reap any remaining player even if its app exited before cleanup.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    async with asyncio.timeout(2):
                        while True:
                            try:
                                os.killpg(process.pid, 0)
                            except PermissionError:
                                # Exiting macOS children may no longer be signalable.
                                break
                            await asyncio.sleep(0.02)
                except asyncio.TimeoutError:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
            socket_path = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
            (socket_path / f"ytm-mpv-{process.pid}.sock").unlink(missing_ok=True)
            if self._stdin is not None:
                self._stdin.close()
            if self._task is not None:
                self._task.cancel()
                await asyncio.gather(self._task, return_exceptions=True)
                self._task = None


class YtmServer(Server):
    def __init__(self, *, port: int = 8000, command: str | None = None) -> None:
        super().__init__(
            command or shlex.join([sys.executable, "-m", "ytm"]),
            host="127.0.0.1", port=port, title="ytm",
            public_url=f"http://localhost:{port}",
        )
        self._session_lock = asyncio.Lock()
        self._websocket: web.WebSocketResponse | None = None
        self._runner: web.AppRunner | None = None
        self._closing = False

    @property
    def session_active(self) -> bool:
        return self._session_lock.locked()

    async def _make_app(self) -> web.Application:
        app = await super()._make_app()
        app.router.add_get("/session-status", self.handle_session_status)
        return app

    async def on_startup(self, app: web.Application) -> None:
        # Announce readiness in start(), after the listening socket is bound.
        pass

    async def on_shutdown(self, app: web.Application) -> None:
        self._closing = True
        if self._websocket is not None and self._websocket.prepared:
            await self._websocket.close(code=1001, message=b"Server shutting down")
        async with self._session_lock:
            pass

    def _check_local_request(self, request: web.Request) -> None:
        if request.url.host not in {"localhost", "127.0.0.1"}:
            raise web.HTTPForbidden(text="ytm is available only through its local URL.")
        origin = request.headers.get("Origin")
        if origin is not None and origin != str(request.url.origin()):
            raise web.HTTPForbidden(text="ytm requires a same-origin connection.")

    def _check_admission(self, request: web.Request) -> None:
        self._check_local_request(request)
        if self._closing:
            raise web.HTTPServiceUnavailable(text="ytm is shutting down.")
        if self.session_active:
            raise web.HTTPConflict(text=(
                "A ytm session is already in use. Close the active tab, "
                "then refresh this page after its player finishes stopping."
            ))

    async def handle_index(self, request: web.Request):
        self._check_admission(request)
        response = await super().handle_index(request)
        response.text = response.text.replace("</body>", SESSION_STATUS_SCRIPT + "</body>")
        response.headers["Cache-Control"] = "no-store"
        return response

    async def handle_session_status(self, request: web.Request) -> web.Response:
        self._check_local_request(request)
        return web.json_response({"active": self.session_active}, headers={"Cache-Control": "no-store"})

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        self._check_admission(request)
        async with self._session_lock:
            websocket = self._websocket = web.WebSocketResponse(heartbeat=15)
            service = YtmAppService(
                self.command,
                write_bytes=websocket.send_bytes,
                write_str=websocket.send_str,
                close=websocket.close,
                download_manager=self.download_manager,
            )
            try:
                await websocket.prepare(request)
                await service.start(
                    to_int(request.query.get("width", "80"), 80),
                    to_int(request.query.get("height", "24"), 24),
                )
                await self._process_messages(websocket, service)
            except Exception:
                log.exception("ytm web session failed")
            finally:
                try:
                    await service.stop()
                finally:
                    if websocket.prepared:
                        await websocket.close()
                    self._websocket = None
            return websocket

    async def start(self) -> None:
        self._runner = web.AppRunner(await self._make_app())
        try:
            await self._runner.setup()
            await web.TCPSite(self._runner, self.host, self.port).start()
        except BaseException:
            await self.stop()
            raise
        port = self._runner.addresses[0][1]
        self.public_url = f"http://localhost:{port}"
        print(f"ytm is running at {self.public_url}", flush=True)
        print("Audio plays on this computer through mpv. Press Ctrl+C to stop.", flush=True)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None


async def _serve() -> None:
    server = YtmServer()
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)
    try:
        await server.start()
        await stopped.wait()
    finally:
        await server.stop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)


def serve() -> None:
    try:
        asyncio.run(_serve())
    except OSError as exc:
        print(f"ytm: could not start web server: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
