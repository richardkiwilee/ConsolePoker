"""Class selection screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, ListView, ListItem, Label, Button, Static
from textual.containers import Horizontal, Vertical


CLASS_DESCRIPTIONS = {
    "warrior": ("战士", "擅长强力出牌，技能增强筹码效果。"),
    "mage":    ("法师", "法力充沛，奥术爆发瞬间获得额外法力。"),
    "rogue":   ("刺客", "规则破坏者，可无视出牌规则约束。"),
    "priest":  ("牧师", "丰厚的金币收益，经济型职业。"),
    "paladin": ("圣骑士", "坚韧防御，免疫疲劳惩罚。"),
}


class ClassSelectScreen(Screen):
    BINDINGS = [
        ("up",    "move_up",   "上移"),
        ("down",  "move_down", "下移"),
        ("enter", "confirm",   "确认"),
    ]

    def __init__(self, client, available_classes: list[str], **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.available = available_classes
        self._selected_idx = 0
        self._confirmed = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("选择你的职业（所有人确认后公示）", id="cls_title")
        yield Horizontal(
            ListView(*[
                ListItem(Label(CLASS_DESCRIPTIONS.get(c, (c, ""))[0]), id=f"cls_{c}")
                for c in self.available
            ], id="cls_list"),
            Vertical(
                Static("", id="cls_detail"),
                id="cls_right",
            ),
            id="cls_body",
        )
        yield Button("确认选择 [Enter]", id="confirm_btn", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self._update_detail()
        self.client.on("class_select", self._on_class_select)

    def _update_detail(self) -> None:
        if not self.available:
            return
        cls_id = self.available[self._selected_idx]
        name, desc = CLASS_DESCRIPTIONS.get(cls_id, (cls_id, ""))
        self.query_one("#cls_detail", Static).update(f"[bold]{name}[/bold]\n\n{desc}")

    def action_move_up(self) -> None:
        self._selected_idx = max(0, self._selected_idx - 1)
        self._update_detail()

    def action_move_down(self) -> None:
        self._selected_idx = min(len(self.available) - 1, self._selected_idx + 1)
        self._update_detail()

    def action_confirm(self) -> None:
        if self._confirmed:
            return
        self._confirmed = True
        cls_id = self.available[self._selected_idx]
        self.client.send_select_class(cls_id)
        self.query_one("#confirm_btn", Button).label = "等待其他玩家…"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm_btn":
            self.action_confirm()

    def _on_class_select(self, evt) -> None:
        if evt.all_confirmed:
            # Advance to battle or whatever comes next (handled by app)
            self.call_from_thread(self._all_confirmed)

    def _all_confirmed(self) -> None:
        self.app.notify("职业选择完成，游戏即将开始！")
        self.app.pop_screen()
