from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView


class ConfirmModal(ModalScreen[bool]):
    """Generic confirmation dialog. Returns True/False via dismiss()."""

    def __init__(self, title: str, items: list[str], action_label: str) -> None:
        super().__init__()
        self._title = title
        self._items = items
        self._action_label = action_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self._title)
            with ListView(id="confirm-items"):
                for item in self._items:
                    yield ListItem(Label(item))
            yield Button(self._action_label, variant="error", id="btn-confirm")
            yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm")
