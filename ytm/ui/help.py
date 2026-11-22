from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

HELP = """
[bold cyan]SEARCH[/]
  /             jump to the search box (from anywhere)
  enter         search  ·  on a result: play it now
  a             enqueue the highlighted result
  esc           leave the search box, back to results
  ctrl+u/w/k    clear left / delete word / clear right
  ctrl+a  ctrl+e   start / end of line

[bold cyan]MOVING AROUND[/]
  tab  shift+tab    cycle panes: search → results → queue
  j / k             down / up        (arrows work too)
  pgup / pgdn       page down / up
  home / end        first / last item
  1 … 9, 0          play result #1–#10 instantly
                    (in the queue: jump to #1–#10)

[bold cyan]QUEUE[/]
  enter             play the highlighted track now
  x                 remove it from the queue
  [  ]              previous / next queue (saved between runs)
  N                 create a new named queue
  R                 rename the current queue

[bold cyan]PLAYBACK[/]  (works from any list)
  space             play / pause
  n  /  p           next / previous track
  +  /  -           volume
  l                 lyrics overlay (live-synced)
  q                 quit (stops playback)

  ?                 this help
"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("question_mark", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        Binding("f1", "close", "Close", show=False),
    ]

    CSS = """
    HelpScreen {
        align: center middle;
        background: $background 70%;
    }
    #help-box {
        width: 72;
        height: auto;
        max-height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }
    #help-title {
        width: 100%;
        text-style: bold;
        color: $accent;
        content-align: center middle;
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("ytm — keyboard help", id="help-title"),
            Static(HELP.strip() + "\n"),
            id="help-box",
        )

    def on_mount(self) -> None:
        self.query_one("#help-box").border_title = "press ? or esc to close"

    def action_close(self) -> None:
        self.dismiss()
