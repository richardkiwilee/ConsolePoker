"""Shop screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Static, Button, Label
from textual.containers import Horizontal, Vertical


class ShopScreen(Screen):
    BINDINGS = [
        ("up",    "move_up",   "上"),
        ("down",  "move_down", "下"),
        ("left",  "go_left",   "左栏"),
        ("right", "go_right",  "右栏"),
        ("enter", "buy_or_view", "购买/查看"),
        ("l",     "reserve",  "预留"),
        ("s",     "sell",     "出售"),
        ("f",     "refresh",  "刷新"),
        ("escape","leave",    "离开"),
    ]

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self._shop_state = None
        self._left_idx = 0
        self._right_idx = 0
        self._focus = "left"   # "left" | "right"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Label("货架", id="shelf_label"),
                DataTable(id="shelf_table"),
                id="left_panel",
            ),
            Vertical(
                Label("我的技能 & 筹码", id="owned_label"),
                DataTable(id="owned_table"),
                Static("", id="detail_box"),
                id="right_panel",
            ),
            id="shop_body",
        )
        yield Horizontal(
            Button("刷新 [F]", id="btn_refresh"),
            Button("预留 [L]", id="btn_reserve"),
            Button("出售 [S]", id="btn_sell"),
            Button("离开 [Esc]", id="btn_leave", variant="error"),
            id="shop_footer_btns",
        )
        yield Footer()

    def on_mount(self) -> None:
        shelf = self.query_one("#shelf_table", DataTable)
        shelf.add_columns("名称", "类型", "价格", "稀有", "预留")
        owned = self.query_one("#owned_table", DataTable)
        owned.add_columns("名称", "类型")
        self.client.on("shop", self._on_shop)

    def _on_shop(self, evt) -> None:
        self._shop_state = evt.state
        self.call_from_thread(self._refresh_ui)

    def _refresh_ui(self) -> None:
        if self._shop_state is None:
            return
        shelf = self.query_one("#shelf_table", DataTable)
        shelf.clear()
        rarity_names = {1: "普通", 2: "稀有", 3: "史诗", 4: "传说"}
        for item in self._shop_state.items:
            shelf.add_row(
                item.name,
                item.item_type,
                f"{item.price}G",
                rarity_names.get(item.rarity, ""),
                "✅" if item.reserved else "",
            )

        owned = self.query_one("#owned_table", DataTable)
        owned.clear()
        for s in self._shop_state.owned_skills:
            owned.add_row(s.name, "技能")
        for c in self._shop_state.owned_chips:
            owned.add_row(c.name, "筹码")

        coins = self._shop_state.player_coins
        refresh = self._shop_state.refresh_cost
        self.query_one("#shelf_label", Label).update(
            f"货架  (金币: {coins}G  刷新费: {refresh}G)"
        )

    def _selected_item(self):
        if self._shop_state is None:
            return None
        items = list(self._shop_state.items)
        if self._left_idx < len(items):
            return items[self._left_idx]
        return None

    def action_move_up(self) -> None:
        if self._focus == "left":
            self._left_idx = max(0, self._left_idx - 1)
        else:
            self._right_idx = max(0, self._right_idx - 1)

    def action_move_down(self) -> None:
        if self._focus == "left" and self._shop_state:
            self._left_idx = min(len(self._shop_state.items) - 1, self._left_idx + 1)
        else:
            self._right_idx = self._right_idx + 1  # bounded by owned list size

    def action_go_left(self) -> None:
        self._focus = "left"

    def action_go_right(self) -> None:
        self._focus = "right"

    def action_buy_or_view(self) -> None:
        item = self._selected_item()
        if self._focus == "left" and item:
            self.client.send_buy(item.item_id)
        else:
            # Show detail in detail_box
            self.app.notify("查看详情（占位符）", timeout=2)

    def action_reserve(self) -> None:
        item = self._selected_item()
        if item:
            # Toggle reserve via server (use buy flow as proxy; server handles)
            self.app.notify("预留功能（占位符）", timeout=2)

    def action_sell(self) -> None:
        if self._focus == "right" and self._shop_state:
            owned_chips = list(self._shop_state.owned_chips)
            idx = self._right_idx - len(self._shop_state.owned_skills)
            if 0 <= idx < len(owned_chips):
                self.client.send_sell(owned_chips[idx].chip_id)

    def action_refresh(self) -> None:
        self.client.send_refresh()

    def action_leave(self) -> None:
        self.client.send_confirm_result()
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_map = {
            "btn_refresh": self.action_refresh,
            "btn_reserve": self.action_reserve,
            "btn_sell":    self.action_sell,
            "btn_leave":   self.action_leave,
        }
        fn = btn_map.get(event.button.id)
        if fn:
            fn()
