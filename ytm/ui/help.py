from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

HELP = """
[bold]SEARCH[/]
  /             jump to the search box (from anywhere)
  enter         search  ·  on a result: play it now
  a             enqueue the highlighted result
  esc           leave the search box, back to results
  ctrl+u/w/k    clear left / delete word / clear right
  ctrl+a  ctrl+e   start / end of line

[bold]MOVING AROUND[/]
  tab  shift+tab    cycle panes: search → results → queue
  j / k             down / up        (arrows work too)
  pgup / pgdn       page down / up
  home / end        first / last item
  1 … 9, 0          play result #1–#10 instantly
                    (in the queue: jump to #1–#10)

[bold]QUEUE[/]
  enter             play the highlighted track now
  x                 remove it from the queue
  [  ]              previous / next queue (saved between runs)
  N                 create a new named queue
  R                 rename the current queue

[bold]PLAYBACK[/]  (works from any list)
  space             play / pause
  n  /  p           next / previous track
  +  /  -           volume
  l                 lyrics overlay (live-synced)
  s                 full-screen Now Playing (s or Esc to close)
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

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Keyboard shortcuts", classes="dialog-title"),
            VerticalScroll(Static(HELP.strip()), id="help-scroll"),
            id="help-box",
            classes="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#help-box").border_subtitle = "Esc close"
        self.query_one("#help-scroll", VerticalScroll).focus()

    def action_close(self) -> None:
        self.dismiss()
