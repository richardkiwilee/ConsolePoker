"""Battle screen — the main combat UI.

Layout (top to bottom):
  ┌─────────────────────────────────────────────────────────────┐
  │  顶栏：所有其他玩家概览（名称、金币、法力、手牌数量）        │
  ├─────────────────────────────────────────────────────────────┤
  │  选中玩家详情区                                              │
  ├─────────────────────────────────────────────────────────────┤
  │  操作区：当前牌面 | 出牌预览 | 出牌/Pass/技能               │
  ├─────────────────────────────────────────────────────────────┤
  │  我的手牌区                                    │ 日志面板   │
  └────────────────────────────────────────────────┴────────────┘
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Static, Label, Button, DataTable, RichLog
)
from textual.containers import Horizontal, Vertical, ScrollableContainer


RANK_DISPLAY = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
    8: "8", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K",
    14: "A", 15: "小王", 16: "大王",
}

SUIT_DISPLAY = {0: "", 1: "♠", 2: "♥", 3: "♦", 4: "♣"}


def _card_display(card_proto) -> str:
    rank = RANK_DISPLAY.get(card_proto.rank, "?")
    suit = SUIT_DISPLAY.get(card_proto.suit, "")
    if card_proto.rank in (15, 16):
        return rank
    return f"{rank}{suit}"


class BattleScreen(Screen):
    BINDINGS = [
        ("up",        "focus_up",     "上区域"),
        ("down",      "focus_down",   "下区域"),
        ("left",      "nav_left",     "左"),
        ("right",     "nav_right",    "右"),
        ("space",     "select_card",  "选/取消"),
        ("enter",     "action_enter", "确认"),
        ("p",         "do_pass",      "Pass"),
        ("c",         "clear_sel",    "清空选中"),
        ("h",         "hint",         "提示"),
        ("k",         "skill_mode",   "技能"),
        ("escape",    "escape",       "返回"),
    ]

    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        # Combat state
        self._state = None
        self._my_cards: list = []          # CardProto list (local cache)
        self._selected_ids: set[str] = set()
        self._viewed_player_idx: int = 0
        self._other_players: list = []
        self._focus_area: str = "hand"     # "top" | "detail" | "action" | "hand"
        self._skill_mode = False
        self._skill_idx = 0
        self._my_skills: list = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # Top bar: other players overview
        yield Static("", id="top_bar")
        # Viewed player detail
        yield Static("", id="player_detail")
        # Action area
        yield Horizontal(
            Static("当前牌面: —", id="last_hand_display"),
            Static("出牌预览: —", id="play_preview"),
            Vertical(
                Button("出牌 [Enter]", id="btn_play", variant="success"),
                Button("Pass [P]", id="btn_pass", variant="warning"),
                Button("技能 [K]", id="btn_skill"),
                id="action_buttons",
            ),
            id="action_area",
        )
        # Hand + log
        yield Horizontal(
            ScrollableContainer(Static("", id="hand_display"), id="hand_area"),
            RichLog(id="log_panel", wrap=True, markup=True),
            id="bottom_area",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.client.on("combat", self._on_combat)
        self.client.on("log",    self._on_log)
        self.client.on("error",  self._on_error)

    # ── Server event handlers ─────────────────────────────────────────────

    def _on_combat(self, evt) -> None:
        self._state = evt.state
        self.call_from_thread(self._refresh_ui)

    def _on_log(self, evt) -> None:
        style = "bold red" if evt.important else "dim"
        self.call_from_thread(
            lambda: self.query_one("#log_panel", RichLog).write(
                f"[{style}]{evt.message}[/{style}]"
            )
        )

    def _on_error(self, msg) -> None:
        self.call_from_thread(lambda: self.app.notify(str(msg), severity="error"))

    # ── UI refresh ────────────────────────────────────────────────────────

    def _refresh_ui(self) -> None:
        if self._state is None:
            return

        # Separate me from others
        my_id = self.client.player_id
        players = list(self._state.players)
        others = [p for p in players if p.player_id != my_id]
        me = next((p for p in players if p.player_id == my_id), None)
        self._other_players = others
        if me:
            self._my_skills = list(me.skills)

        # Top bar
        parts = []
        for p in others:
            status = "▶" if p.player_id == self._state.current_player_id else " "
            parts.append(f"{status}{p.name} 💰{p.coins} ✨{p.mana}/{p.mana_max} 🃏{p.hand_count}")
        self.query_one("#top_bar", Static).update("  |  ".join(parts) or "（无其他玩家）")

        # Viewed player detail
        if others and self._viewed_player_idx < len(others):
            vp = others[self._viewed_player_idx]
            detail_lines = [
                f"[bold]{vp.name}[/bold]  分数: {vp.score}  金币: {vp.coins}  法力: {vp.mana}/{vp.mana_max}",
                f"手牌: ?x{vp.hand_count}",
                f"技能: {', '.join(s.name for s in vp.skills) or '无'}",
                f"筹码: {', '.join(c.name for c in vp.chips) or '无'}",
            ]
            self.query_one("#player_detail", Static).update("\n".join(detail_lines))

        # Last hand display
        last = self._state.last_hand
        if last and last.cards:
            cards_str = " ".join(_card_display(c) for c in last.cards)
            player_name = next((p.name for p in players if p.player_id == self._state.last_hand_player_id), "?")
            self.query_one("#last_hand_display", Static).update(
                f"当前牌面: [{player_name}] {cards_str}"
            )
        else:
            self.query_one("#last_hand_display", Static).update("当前牌面: 自由出牌")

        # My hand (we get card info from server; for now show selected markers)
        my_turn = self._state.current_player_id == my_id
        turn_indicator = "【你的回合】" if my_turn else "【等待中…】"
        if me:
            mana_bar = f"法力: {me.mana}/{me.mana_max}  金币: {me.coins}  分数: {me.score}"
            fatigue = f"疲劳: {self._state.fatigue_counter}"
            self.query_one("#hand_display", Static).update(
                f"{turn_indicator}  {mana_bar}  {fatigue}\n"
                f"已选 {len(self._selected_ids)} 张  (Space=选牌 Enter=出牌 P=Pass K=技能 H=提示)"
            )

        # Preview
        sel_count = len(self._selected_ids)
        self.query_one("#play_preview", Static).update(
            f"出牌预览: {sel_count} 张" if sel_count > 0 else "出牌预览: —"
        )

        # Skill mode display
        if self._skill_mode and self._my_skills:
            skill = self._my_skills[self._skill_idx % len(self._my_skills)]
            self.query_one("#btn_skill", Button).label = (
                f"技能: {skill.name} (费:{skill.mana_cost}) [Enter]"
            )

    # ── Key bindings ──────────────────────────────────────────────────────

    def action_focus_up(self) -> None:
        areas = ["top", "detail", "action", "hand"]
        idx = areas.index(self._focus_area)
        self._focus_area = areas[max(0, idx - 1)]

    def action_focus_down(self) -> None:
        areas = ["top", "detail", "action", "hand"]
        idx = areas.index(self._focus_area)
        self._focus_area = areas[min(len(areas) - 1, idx + 1)]

    def action_nav_left(self) -> None:
        if self._focus_area == "detail" and self._other_players:
            self._viewed_player_idx = (self._viewed_player_idx - 1) % len(self._other_players)
            self._refresh_ui()
        elif self._skill_mode and self._my_skills:
            self._skill_idx = (self._skill_idx - 1) % len(self._my_skills)
            self._refresh_ui()

    def action_nav_right(self) -> None:
        if self._focus_area == "detail" and self._other_players:
            self._viewed_player_idx = (self._viewed_player_idx + 1) % len(self._other_players)
            self._refresh_ui()
        elif self._skill_mode and self._my_skills:
            self._skill_idx = (self._skill_idx + 1) % len(self._my_skills)
            self._refresh_ui()

    def action_select_card(self) -> None:
        # Without a real card widget we provide a placeholder notify
        self.app.notify("（使用命令栏输入卡牌ID或点击按钮出牌）", timeout=2)

    def action_action_enter(self) -> None:
        if self._skill_mode:
            self._use_current_skill()
        else:
            self._play_selected()

    def action_do_pass(self) -> None:
        self.client.send_pass()

    def action_clear_sel(self) -> None:
        self._selected_ids.clear()
        self._refresh_ui()

    def action_hint(self) -> None:
        self.app.notify("（AI推荐功能占位符）", timeout=2)

    def action_skill_mode(self) -> None:
        self._skill_mode = not self._skill_mode
        self._refresh_ui()

    def action_escape(self) -> None:
        self._skill_mode = False
        self._focus_area = "hand"
        self._refresh_ui()

    def _play_selected(self) -> None:
        if not self._selected_ids:
            self.app.notify("请先选择要出的牌", severity="warning")
            return
        self.client.send_play(list(self._selected_ids))
        self._selected_ids.clear()

    def _use_current_skill(self) -> None:
        if not self._my_skills:
            return
        skill = self._my_skills[self._skill_idx % len(self._my_skills)]
        self.client.send_use_skill(skill.skill_id)
        self._skill_mode = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_play":
            self._play_selected()
        elif event.button.id == "btn_pass":
            self.client.send_pass()
        elif event.button.id == "btn_skill":
            if self._skill_mode:
                self._use_current_skill()
            else:
                self._skill_mode = True
                self._refresh_ui()
