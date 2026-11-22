from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class NamePromptScreen(ModalScreen[str | None]):
    """Prompt for a queue name; dismisses with the name, or None on cancel."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CSS = """
    NamePromptScreen {
        align: center middle;
        background: $background 70%;
    }
    #name-box {
        width: 60;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #name-title {
        width: 100%;
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    #name-input {
        width: 100%;
    }
    """

    def __init__(self, title: str, value: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._value = value

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title, id="name-title"),
            Input(value=self._value, id="name-input", placeholder="queue name"),
            id="name-box",
        )

    def on_mount(self) -> None:
        inp = self.query_one("#name-input", Input)
        inp.focus()
        if self._value:
            inp.select_all()

    @on(Input.Submitted, "#name-input")
    def on_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if name:
            self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)
