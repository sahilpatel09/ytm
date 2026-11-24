# Web mode implementation plan

Implement [the approved specification](1-spec.md) inline on `feat-web-ui`.
The user approved starting implementation in the current session.

## Task 1: Web entry point and dependency

Add `textual-serve` to normal dependencies. Test that standalone `--web`
launches the server without terminal probing or starting a player. Preserve
terminal launch and standalone `--version`. Implement the dispatch after
observing the new test fail.

## Task 2: Single-session server and lifecycle

Serve the existing app through the same Python environment. Bind only to
loopback on port 8000; announce the URL after binding succeeds. Test real
HTTP/WebSocket connections against an isolated subprocess fixture for session
admission, second-tab rejection, disconnect, refresh/reconnect, quit, and
server shutdown. Retain admission until the previous child finishes cleanup.
Ensure unexpected child exit and startup failure release session ownership.

Keep queue serialization and playback behavior shared. Add lifecycle tests
for cleanup before mount and partially started mpv processes if web integration
exposes gaps; fix those shared paths after observing failures.

## Task 3: Verification and documentation

Document the launch command, local audio, single active session, and shutdown.
Run `uv run --locked python -m unittest discover -s tests -v`; check failures
and skips. Verify a real server with mocked network services and temporary
`XDG_STATE_HOME`, including actual mpv startup/cleanup without playing audio.
Review the full diff and request an independent review against the spec.
Leave changes uncommitted unless requested.

## Review focus

Check child-process cleanup on disconnect and signals, ready output after
successful binding, startup errors, and races between refresh and cleanup.
Protect the user's queues and unrelated patch files throughout verification.
