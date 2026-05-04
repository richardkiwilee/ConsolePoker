"""Reward screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Label, Button, Static
from textual.containers import Horizontal, Vertical


class RewardScreen(Screen):
    BINDINGS = [
        ("up",    "move_up",   "上"),
        ("down",  "move_down", "下"),
        ("enter", "select",    "选取"),
        ("escape","skip",      "跳过"),
    ]

    def __init__(self, client, picks_allowed: int = 1, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.picks_allowed = picks_allowed
        self._items: list = []
        self._idx = 0
        self._picks_left = picks_allowed

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Label(f"奖励阶段  剩余选择次数: {self._picks_left}", id="reward_label"),
                DataTable(id="reward_table"),
                id="reward_left",
            ),
            Static("", id="reward_detail"),
            id="reward_body",
        )
        yield Horizontal(
            Button("选取 [Enter]", id="btn_select", variant="success"),
            Button("跳过 [Esc]", id="btn_skip"),
            id="reward_footer",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#reward_table", DataTable)
        table.add_columns("名称", "类型", "描述")
        self.client.on("reward", self._on_reward)

    def _on_reward(self, evt) -> None:
        self._items = list(evt.state.items)
        self.picks_allowed = evt.state.picks_allowed
        self._picks_left = self.picks_allowed
        self.call_from_thread(self._refresh_ui)

    def _refresh_ui(self) -> None:
        label = self.query_one("#reward_label", Label)
        label.update(f"奖励阶段  剩余选择次数: {self._picks_left}")
        table = self.query_one("#reward_table", DataTable)
        table.clear()
        for item in self._items:
            table.add_row(item.name, item.item_type, item.description[:30])

    def action_move_up(self) -> None:
        self._idx = max(0, self._idx - 1)

    def action_move_down(self) -> None:
        self._idx = min(len(self._items) - 1, self._idx + 1)

    def action_select(self) -> None:
        if not self._items or self._picks_left <= 0:
            return
        item = self._items[self._idx]
        self.client.send_buy(item.item_id)
        self._picks_left -= 1
        self._refresh_ui()
        if self._picks_left <= 0:
            self.client.send_confirm_result()
            self.app.pop_screen()

    def action_skip(self) -> None:
        self.client.send_confirm_result()
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_select":
            self.action_select()
        elif event.button.id == "btn_skip":
            self.action_skip()
