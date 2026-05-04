"""Game session entity — orchestrates the entire game lifecycle."""

from __future__ import annotations

import random
from enum import Enum, auto
from typing import Callable, Optional

from ..core.combat import CombatState
from ..core.phase import PhaseEngine, NodeType
from ..core.scoring import calc_round_scores, calc_coin_settlement
from ..core.card import Card
from .player import Player, Room


class GameStatus(Enum):
    LOBBY        = auto()
    CLASS_SELECT = auto()
    RUNNING      = auto()
    GAME_OVER    = auto()


class GameSession:
    """One complete game instance."""

    def __init__(self, room: Room, phase_engine: PhaseEngine) -> None:
        self.room = room
        self.phase_engine = phase_engine
        self.status = GameStatus.LOBBY
        self.current_combat: Optional[CombatState] = None
        self.combat_round = 0  # which combat round overall
        self._event_handlers: dict[str, list[Callable]] = {}

    # ── Event system ──────────────────────────────────────────────────────

    def on(self, event: str, handler: Callable) -> None:
        self._event_handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, *args, **kwargs) -> None:
        for fn in self._event_handlers.get(event, []):
            fn(*args, **kwargs)

    # ── Lobby ─────────────────────────────────────────────────────────────

    def player_ready(self, player_id: str) -> bool:
        player = self.room.get_player(player_id)
        if player is None:
            return False
        player.is_ready = True
        if self.room.all_ready() and len(self.room.players) >= self.room.min_players:
            self._start_class_select()
        return True

    def _start_class_select(self) -> None:
        self.status = GameStatus.CLASS_SELECT
        self.emit("class_select_started")

    def player_select_class(self, player_id: str, class_id: str) -> bool:
        player = self.room.get_player(player_id)
        if player is None or self.status != GameStatus.CLASS_SELECT:
            return False
        player.class_id = class_id
        player.class_confirmed = True
        # All confirmed → start phases
        if self.room.all_class_confirmed():
            self._apply_class_effects()
            self._start_next_phase()
        self.emit("class_confirmed", player_id)
        return True

    def _apply_class_effects(self) -> None:
        """Apply class initial skills and chip pools (placeholder)."""
        from ..registry.class_registry import CLASS_REGISTRY
        for player in self.room.player_list:
            cls = CLASS_REGISTRY.get(player.class_id or "")
            if cls:
                cls.apply_start(player)

    # ── Phase engine ──────────────────────────────────────────────────────

    def _start_next_phase(self) -> None:
        if self.phase_engine.is_done:
            self._end_game()
            return
        self.status = GameStatus.RUNNING
        node = self.phase_engine.current
        if node is None:
            self._end_game()
            return
        if node.node_type == NodeType.COMBAT:
            self._start_combat(node.config)
        elif node.node_type == NodeType.SHOP:
            self._start_shop(node.config)
        elif node.node_type == NodeType.REWARD:
            self._start_reward(node.config)

    def advance_phase(self) -> None:
        self.phase_engine.advance()
        self._start_next_phase()

    # ── Combat ────────────────────────────────────────────────────────────

    def _start_combat(self, config: dict) -> None:
        self.combat_round += 1
        # Deal hands
        hand_size = config.get("hand_size", Player.INITIAL_HAND_SIZE)
        hands: dict[str, list[Card]] = {}
        for player in self.room.player_list:
            player.regen_mana()
            player.draw_hand(hand_size)
            hands[player.player_id] = list(player.hand)

        scores = {p.player_id: p.score for p in self.room.player_list}
        self.current_combat = CombatState(
            player_ids=[p.player_id for p in self.room.player_list],
            hands=hands,
            scores=scores,
            round_number=self.combat_round,
        )
        self.emit("combat_started", self.current_combat)

    def resolve_combat_round(self, winner_id: str) -> None:
        if self.current_combat is None:
            return
        cs = self.current_combat
        remaining = {pid: len(h) for pid, h in cs.hands.items()}
        scores_before = {p.player_id: p.score for p in self.room.player_list}
        results = calc_round_scores(
            cs.player_ids, remaining, winner_id, scores_before
        )
        # Apply scores
        score_map = {r.player_id: r.score_delta for r in results}
        for pid, delta in score_map.items():
            player = self.room.get_player(pid)
            if player:
                player.add_score(delta)

        # Coin settlement
        current_coins = {p.player_id: p.coins for p in self.room.player_list}
        current_scores = {p.player_id: p.score for p in self.room.player_list}
        coin_deltas = calc_coin_settlement(
            cs.player_ids, current_coins, current_scores, winner_id
        )
        for pid, delta in coin_deltas.items():
            player = self.room.get_player(pid)
            if player:
                player.add_coins(delta)

        self.emit("combat_round_over", winner_id, results, coin_deltas)
        self.current_combat = None

    # ── Shop ──────────────────────────────────────────────────────────────

    def _start_shop(self, config: dict) -> None:
        self.emit("shop_started", config)

    def _start_reward(self, config: dict) -> None:
        self.emit("reward_started", config)

    # ── Game over ─────────────────────────────────────────────────────────

    def _end_game(self) -> None:
        self.status = GameStatus.GAME_OVER
        players_sorted = sorted(
            self.room.player_list, key=lambda p: p.score, reverse=True
        )
        self.emit("game_over", players_sorted)
