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

    def __init__(self, title: str, value: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._value = value

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title, classes="dialog-title"),
            Input(value=self._value, id="name-input", placeholder="queue name"),
            id="name-box",
            classes="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#name-box").border_subtitle = "Enter save · Esc cancel"
        self.query_one("#name-input", Input).focus()

    @on(Input.Submitted, "#name-input")
    def on_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if name:
            self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)
