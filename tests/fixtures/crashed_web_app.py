"""Simulate a player child left behind when its Textual app exits abruptly."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


state = Path(os.environ["XDG_STATE_HOME"])
runtime = Path(os.environ["XDG_RUNTIME_DIR"])
sock = socket.socket(socket.AF_UNIX)
sock.bind(str(runtime / f"ytm-mpv-{os.getpid()}.sock"))
child = subprocess.Popen(
    [sys.executable, "-c", (
        "import os,signal; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN) if os.environ.get('YTM_TEST_IGNORE_TERM') else None; "
        "Path(os.environ['XDG_STATE_HOME'], 'child-ready').touch(); signal.pause()"
    )],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
while not (state / "child-ready").exists():
    time.sleep(0.01)
(state / "crash-pids").write_text(json.dumps([os.getpid(), child.pid]))
print("__GANGLION__", flush=True)
os.read(sys.stdin.fileno(), 4096)
os._exit(2)
