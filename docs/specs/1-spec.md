# Web mode with the existing terminal layout

GitHub issue [#1](https://github.com/sahilpatel09/ytm/issues/1)

Run ytm in a browser on the same computer with `uv run ytm --web`. Reuse the
existing Textual UI, application logic, services, and `mpv` player.

## User experience

- Standard setup includes web mode. `mpv` remains an external requirement.
- `uv run ytm --web` starts a loopback-only server at `http://localhost:8000`
  and prints a usable URL once it is ready.
- Opening the URL starts a session with the existing responsive layout,
  keyboard controls, search, queues, playback controls, lyrics, and Now Playing.
- Audio plays through `mpv` on the computer running ytm.
- Sessions load and save the existing named queues without changing their format.
- `uv run ytm` still launches the terminal interface. `--version` retains its behavior.
- Server startup failures, including an occupied port, are reported clearly and
  exit unsuccessfully.

## Sessions and cleanup

- Allow one active browser session per server. A second tab shows a
  session-in-use message without starting another app or player.
- Closing the active tab, refreshing it, or quitting in the UI ends the session,
  saves queues, stops its `mpv` process, and removes its IPC socket.
- The server remains available. A new session is admitted after cleanup finishes.
- Ctrl+C stops the server and cleans up the active session.
- Missing `mpv` preserves search and queue management and clearly reports that
  playback is unavailable.

## Approach and boundaries

Use Textual's browser-serving support through
[`textual-serve`](https://github.com/Textualize/textual-serve). Keep one UI and
one playback implementation, adding launch, serving, session admission, and
lifecycle behavior needed for web access.

The first version targets local desktop use. Browser audio, remote access,
shared sessions across tabs, and synchronization between independently launched
terminal and web instances are outside this feature.

## Acceptance checks

- Verify startup, ready URL, occupied-port failure, terminal launch, and version output.
- Exercise keyboard navigation, resizing, search, queues, playback, lyrics, and Now Playing.
- Verify second-tab rejection and admission after the active session closes.
- Check tab close, refresh, UI quit, and server shutdown for queue preservation,
  stopped child processes, and removed IPC sockets.
- Check missing `mpv`, failed requests, and rapid searches or track changes.
- Use temporary queue storage and mocked external services for automated checks;
  identify live browser and `mpv` checks separately.
