"""Lobby screen — waiting room with player list and ready button."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, DataTable, Button, Label, Static
from textual.containers import Vertical, Horizontal


class LobbyScreen(Screen):
    """Shows all players in the room and a 'Ready' button."""

    BINDINGS = [("r", "ready", "准备")]

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self._players: list = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(f"ConsolePoker — 大厅  玩家: {self.client.player_name}", id="lobby_title")
        yield DataTable(id="player_table")
        yield Horizontal(
            Button("准备 [R]", id="ready_btn", variant="success"),
            Button("退出", id="quit_btn", variant="error"),
            id="lobby_buttons",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#player_table", DataTable)
        table.add_columns("名称", "状态", "是否AI")
        # Pull any already-received lobby event from the app's cache
        cached = getattr(self.app, "_last_lobby_evt", None)
        if cached:
            self.refresh_from_event(cached)

    def refresh_from_event(self, evt) -> None:
        """Update the player list from a lobby event (always called on main thread)."""
        self._players = list(evt.players)
        self._refresh_table()

    def _on_lobby(self, evt) -> None:
        # No longer used directly; routing is done via PokerApp._on_lobby
        pass

    def _refresh_table(self) -> None:
        table = self.query_one("#player_table", DataTable)
        table.clear()
        for p in self._players:
            status = "✅ 已准备" if p.is_ready else "⏳ 未准备"
            ai = "AI" if p.is_ai else ""
            table.add_row(p.name, status, ai)

    def action_ready(self) -> None:
        self.client.send_ready()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ready_btn":
            self.client.send_ready()
        elif event.button.id == "quit_btn":
            self.app.exit()
