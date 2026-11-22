from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from typing import Callable

EventCallback = Callable[[str, object], None]


class MpvPlayer:
    """One idle mpv process controlled through its JSON IPC socket."""

    def __init__(self, on_event: EventCallback) -> None:
        runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
        self.socket_path = os.path.join(runtime, f"ytm-mpv-{os.getpid()}.sock")
        self.on_event = on_event
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._request_seq = 0
        self._running = False
        self._last_time_sent = 0.0

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass

        env = os.environ.copy()
        env["LC_NUMERIC"] = "C"
        cmd = [
            "mpv",
            "--no-video",
            "--no-terminal",
            "--idle=yes",
            "--force-window=no",
            "--input-ipc-server=" + self.socket_path,
            "--volume=60",
        ]
        self._proc = subprocess.Popen(
            cmd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._connect_socket()
        self._running = True
        threading.Thread(target=self._read_loop, daemon=True).start()
        for prop in ("pause", "time-pos", "duration", "media-title", "volume"):
            self._send(["observe_property", self._next_request(), prop])

    def _connect_socket(self) -> None:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise RuntimeError("mpv exited during startup")
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(self.socket_path)
                self._sock = sock
                return
            except OSError:
                sock.close() if "sock" in dir() else None
                time.sleep(0.05)
        raise RuntimeError("timed out waiting for mpv IPC socket")

    def _next_request(self) -> int:
        self._request_seq += 1
        return self._request_seq

    def _send(self, command: list) -> None:
        sock = self._sock
        if sock is None:
            raise OSError("mpv ipc not connected")
        payload = (json.dumps({"command": command}) + "\n").encode()
        with self._send_lock:
            sock.sendall(payload)

    def _read_loop(self) -> None:
        buf = b""
        while self._running:
            sock = self._sock
            if sock is None:
                break
            try:
                chunk = sock.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        event = msg.get("event")
        if event == "property-change":
            name = msg.get("name")
            data = msg.get("data")
            if name == "time-pos" and data is not None:
                now = time.monotonic()
                if now - self._last_time_sent < 0.5:
                    return
                self._last_time_sent = now
            self.on_event("property", (name, data))
        elif event == "end-file":
            self.on_event("end-file", msg.get("reason", "eof"))

    # -- commands ---------------------------------------------------------

    def play(self, url: str) -> None:
        self._send(["loadfile", url, "replace"])

    def toggle_pause(self) -> None:
        self._send(["cycle", "pause"])

    def stop(self) -> None:
        self._send(["stop"])

    def adjust_volume(self, delta: int) -> None:
        self._send(["add", "volume", delta])

    def close(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._send(["quit"])
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._proc is not None:
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            self._proc = None
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError:
                pass
