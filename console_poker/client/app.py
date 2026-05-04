"""Client application — top-level Textual App."""

from __future__ import annotations

import sys
import os
import threading

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, Button, Label, Static
from textual.containers import Vertical, Center

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from .client import PokerClient
from .ui.lobby import LobbyScreen
from .ui.class_select import ClassSelectScreen
from .ui.battle import BattleScreen
from .ui.shop import ShopScreen
from .ui.reward import RewardScreen


class ConnectScreen(Screen):
    """Initial connection screen — enter server address and player name."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Center(
            Vertical(
                Label("ConsolePoker", id="title"),
                Label("服务器地址 (host:port)", classes="field_label"),
                Input(value="127.0.0.1:50051", id="server_addr", placeholder="127.0.0.1:50051"),
                Label("玩家昵称", classes="field_label"),
                Input(id="player_name", placeholder="请输入昵称"),
                Button("加入游戏", id="join_btn", variant="success"),
                id="connect_form",
            )
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "join_btn":
            addr = self.query_one("#server_addr", Input).value.strip()
            name = self.query_one("#player_name", Input).value.strip()
            if not name:
                self.app.notify("请输入昵称", severity="error")
                return
            # Disable button to prevent double-click
            self.query_one("#join_btn", Button).disabled = True
            self.query_one("#join_btn", Button).label = "连接中…"
            # Run blocking gRPC call in background thread to avoid freezing UI
            threading.Thread(
                target=self.app.connect_and_join,
                args=(addr, name),
                daemon=True,
            ).start()


CSS = """
#title {
    text-align: center;
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}
#connect_form {
    width: 50;
    height: auto;
    padding: 2;
    border: solid $accent;
}
.field_label {
    margin-top: 1;
}
#top_bar {
    background: $panel;
    padding: 0 1;
    height: 3;
}
#player_detail {
    height: 6;
    border: solid $accent;
    padding: 0 1;
}
#action_area {
    height: 7;
    border: solid $warning;
}
#bottom_area {
    height: 1fr;
}
#hand_area {
    width: 3fr;
    border: solid $success;
}
#log_panel {
    width: 1fr;
    border: solid $primary;
}
#shop_body {
    height: 1fr;
}
#left_panel, #right_panel {
    width: 1fr;
    border: solid $accent;
}
#reward_body {
    height: 1fr;
}
#reward_left {
    width: 1fr;
    border: solid $accent;
}
#reward_detail {
    width: 1fr;
    border: solid $primary;
    padding: 1;
}
"""


class PokerApp(App):
    CSS = CSS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client: PokerClient | None = None
        self._last_lobby_evt = None   # cached so LobbyScreen can pull on mount

    def on_mount(self) -> None:
        self.push_screen(ConnectScreen())

    def connect_and_join(self, addr: str, name: str) -> None:
        """Runs in a background thread — must use call_from_thread for all UI."""
        parts = addr.rsplit(":", 1)
        host = parts[0] if len(parts) == 2 else addr
        port = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 50051

        self.client = PokerClient(host=host, port=port)

        # Wire up server events before connecting
        self.client.on("lobby",        self._on_lobby)
        self.client.on("class_select", self._on_class_select)
        self.client.on("combat",       self._on_combat)
        self.client.on("shop",         self._on_shop)
        self.client.on("reward",       self._on_reward)
        self.client.on("result",       self._on_result)
        self.client.on("game_over",    self._on_game_over)
        self.client.on("error",        self._on_error)

        ok = self.client.connect(name=name)
        if not ok:
            def on_fail():
                self.notify("连接失败", severity="error")
                try:
                    btn = self.query_one("#join_btn", Button)
                    btn.disabled = False
                    btn.label = "加入游戏"
                except Exception:
                    pass
            self.call_from_thread(on_fail)
            return

        def navigate():
            self.pop_screen()
            self.push_screen(LobbyScreen(self.client))
        self.call_from_thread(navigate)

    # ── Navigation handlers (called from client thread) ───────────────────

    def _on_lobby(self, evt) -> None:
        # Cache the latest lobby state so LobbyScreen can pull it on mount
        self._last_lobby_evt = evt
        def update():
            if isinstance(self.screen, LobbyScreen):
                self.screen.refresh_from_event(evt)
        self.call_from_thread(update)

    def _on_class_select(self, evt) -> None:
        def push():
            # Only push if not already on class select
            if not isinstance(self.screen, ClassSelectScreen):
                self.push_screen(ClassSelectScreen(
                    self.client,
                    available_classes=list(evt.available_classes),
                ))
        self.call_from_thread(push)

    def _on_combat(self, evt) -> None:
        def push():
            if not isinstance(self.screen, BattleScreen):
                self.push_screen(BattleScreen(self.client))
        self.call_from_thread(push)

    def _on_shop(self, evt) -> None:
        def push():
            if not isinstance(self.screen, ShopScreen):
                self.push_screen(ShopScreen(self.client))
        self.call_from_thread(push)

    def _on_reward(self, evt) -> None:
        def push():
            if not isinstance(self.screen, RewardScreen):
                self.push_screen(RewardScreen(self.client, picks_allowed=evt.state.picks_allowed))
        self.call_from_thread(push)

    def _on_result(self, evt) -> None:
        def show():
            result = evt.result
            lines = ["本轮结算：\n"]
            for i, pid in enumerate(result.player_ids):
                score = result.score_delta[i] if i < len(result.score_delta) else 0
                coin  = result.coin_delta[i]  if i < len(result.coin_delta) else 0
                total = result.total_scores[i] if i < len(result.total_scores) else 0
                lines.append(f"  {pid[:8]}…  得分+{score}  金币+{coin}  总分={total}")
            self.notify("\n".join(lines), timeout=8)
        self.call_from_thread(show)

    def _on_game_over(self, evt) -> None:
        def show():
            result = evt.result
            lines = ["游戏结束！最终排名：\n"]
            for i, name in enumerate(result.player_names):
                score = result.total_scores[i] if i < len(result.total_scores) else 0
                lines.append(f"  {i+1}. {name}  {score} 分")
            self.notify("\n".join(lines), timeout=15)
        self.call_from_thread(show)

    def _on_error(self, msg) -> None:
        self.call_from_thread(lambda: self.notify(str(msg), severity="error"))
