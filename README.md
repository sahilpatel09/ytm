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

## Controls

- `/` search; `Enter` submit a search or play the selected track.
- `Tab` switch panes; arrows or `j` / `k` navigate lists.
- `a` add a search result to the queue; `x` remove a queued track.
- `Space` pause or resume; `n` / `p` next or previous track.
- `+` / `-` adjust volume; `l` show lyrics.
- `N` create a queue; `R` rename it; `[` / `]` switch queues.
- `?` show all shortcuts; `q` quit.
