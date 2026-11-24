# ytm

A terminal YouTube Music player with search, saved queues, and live lyrics.

## Setup

Requires Python 3.11+, `uv`, and `mpv` on your `PATH`. Search, playback, and
lyrics require an internet connection.

From the repository root:

```sh
uv sync --locked
uv run --locked ytm
```

Alternatively, use `make setup-macos` or `make setup-linux` to install `mpv`
and Python dependencies, then `make start`. These require `uv` and either
Homebrew (macOS) or apt (Linux) if `mpv` is not already installed.

## Web mode

```sh
uv run --locked ytm --web
```

Open the printed link, `http://localhost:8000`, in a browser on the same
computer. Web mode uses the same layout and keyboard controls as the terminal
interface. Audio plays on that computer through `mpv`.

Only one browser session can be active at a time. Closing or refreshing its
tab, or pressing `q` in the app, saves queues and stops playback. The server
stays available for a new session; if a refresh reports that the session is
still in use, refresh again after cleanup finishes. Press Ctrl+C in the
launching terminal to stop the server and its active player.


## Controls

- `/` search; `Enter` submit a search or play the selected track.
- `Tab` switch panes; arrows or `j` / `k` navigate lists.
- `a` add a search result to the queue; `x` remove a queued track.
- `Space` pause or resume; `n` / `p` next or previous track.
- `+` / `-` adjust volume; `l` show lyrics.
- `N` create a queue; `R` rename it; `[` / `]` switch queues.
- `?` show all shortcuts; `q` quit.
