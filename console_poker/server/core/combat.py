"""Combat state machine.

Controls a single combat round: turn order, fatigue, hand-play validation,
round-end detection.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from .card import Card
from .hand import Hand, HandType, recognize, beats


class CombatPhase(Enum):
    WAITING_TURN = auto()
    ROUND_OVER   = auto()


@dataclass
class TurnResult:
    valid: bool
    message: str = ""
    round_over: bool = False
    winner_id: Optional[str] = None


class CombatState:
    """Manages one combat round for all players.

    Attributes:
        player_ids: ordered seat list
        hands: each player's current hand cards
        current_idx: index in player_ids for whose turn it is
        last_hand: the last played Hand (None = free play)
        last_hand_player: player_id who played last_hand
        pass_count: consecutive passes since last_hand
        fatigue: fatigue countdown (starts at 12)
        round_number: which combat round this is
        is_first_round: determines first player selection
    """

    FATIGUE_INIT = 12

    def __init__(
        self,
        player_ids: list[str],
        hands: dict[str, list[Card]],
        scores: dict[str, int],
        round_number: int = 1,
    ) -> None:
        self.player_ids: list[str] = list(player_ids)
        self.hands: dict[str, list[Card]] = {p: list(h) for p, h in hands.items()}
        self.scores: dict[str, int] = dict(scores)
        self.round_number = round_number

        self.last_hand: Optional[Hand] = None
        self.last_hand_player: Optional[str] = None
        self.pass_count: int = 0
        self.fatigue: int = self.FATIGUE_INIT
        self.phase: CombatPhase = CombatPhase.WAITING_TURN

        # Skill/chip middleware pipeline: list of callables
        self._play_middlewares: list[Callable] = []

        # Determine first player
        if round_number == 1:
            first = random.choice(self.player_ids)
        else:
            # Lowest total score goes first
            first = min(self.player_ids, key=lambda p: self.scores.get(p, 0))
        self.current_idx: int = self.player_ids.index(first)

    # ── Middleware ────────────────────────────────────────────────────────

    def add_play_middleware(self, fn: Callable) -> None:
        """Add a middleware that may modify or reject a play."""
        self._play_middlewares.append(fn)

    # ── Helpers ───────────────────────────────────────────────────────────

    @property
    def current_player_id(self) -> str:
        return self.player_ids[self.current_idx]

    def _active_players(self) -> list[str]:
        """Players who still have cards."""
        return [p for p in self.player_ids if self.hands.get(p)]

    def _advance_turn(self) -> None:
        n = len(self.player_ids)
        for _ in range(n):
            self.current_idx = (self.current_idx + 1) % n
            # Skip players with no cards IF there is still more than one active
            if self.hands.get(self.current_player_id) or len(self._active_players()) <= 1:
                break

    def _apply_fatigue(self) -> list[tuple[str, list[Card]]]:
        """Apply fatigue discard. Returns list of (player_id, discarded_cards)."""
        discard_count = abs(self.fatigue)
        discarded: list[tuple[str, list[Card]]] = []
        for pid in self.player_ids:
            h = self.hands.get(pid, [])
            if not h:
                continue
            actual = min(discard_count, len(h))
            to_discard = random.sample(h, actual)
            for c in to_discard:
                h.remove(c)
            discarded.append((pid, to_discard))
        return discarded

    # ── Main actions ──────────────────────────────────────────────────────

    def play(self, player_id: str, cards: list[Card]) -> TurnResult:
        """A player plays a set of cards."""
        if self.phase == CombatPhase.ROUND_OVER:
            return TurnResult(False, "本轮已结束")
        if player_id != self.current_player_id:
            return TurnResult(False, "不是你的回合")

        hand = recognize(cards)
        if hand is None:
            return TurnResult(False, "无效牌型")

        # Validate cards belong to player's hand
        player_hand = self.hands.get(player_id, [])
        for c in cards:
            if c not in player_hand:
                return TurnResult(False, "手牌中没有该牌")

        # Must beat current hand (or free play if last_hand_player == self)
        if self.last_hand is not None and self.last_hand_player != player_id:
            if not beats(hand, self.last_hand):
                return TurnResult(False, "出牌必须大于当前最大牌型")

        # Run middlewares
        for mw in self._play_middlewares:
            ok, msg = mw(player_id, hand, self)
            if not ok:
                return TurnResult(False, msg)

        # Commit play
        for c in cards:
            player_hand.remove(c)
        self.last_hand = hand
        self.last_hand_player = player_id
        self.pass_count = 0

        return self._after_play(player_id)

    def do_pass(self, player_id: str) -> TurnResult:
        """A player passes."""
        if self.phase == CombatPhase.ROUND_OVER:
            return TurnResult(False, "本轮已结束")
        if player_id != self.current_player_id:
            return TurnResult(False, "不是你的回合")
        if self.last_hand_player == player_id:
            return TurnResult(False, "持有控牌权时不能 Pass")

        self.pass_count += 1

        # Check if all others passed → gain control
        active = self._active_players()
        others = [p for p in active if p != self.last_hand_player]
        if self.pass_count >= len(others):
            # Control gained
            self.fatigue -= 1
            discarded: list = []
            if self.fatigue < 0:
                discarded = self._apply_fatigue()
            # Reset for new round of play
            ctrl_holder = self.last_hand_player
            self.last_hand = None
            self.pass_count = 0
            # Control goes to the last player who played (if still active)
            if ctrl_holder and self.hands.get(ctrl_holder):
                self.current_idx = self.player_ids.index(ctrl_holder)
            else:
                self._advance_turn()
            return TurnResult(True, f"控牌权确认，疲劳值={self.fatigue}")
        else:
            self._advance_turn()
            return TurnResult(True)

    def _after_play(self, player_id: str) -> TurnResult:
        """Check for round-end conditions after a play."""
        player_hand = self.hands.get(player_id, [])

        if not player_hand:
            # Player finished their hand → round over
            self.phase = CombatPhase.ROUND_OVER
            return TurnResult(True, round_over=True, winner_id=player_id)

        # Only one player has cards left → give them control
        active = self._active_players()
        if len(active) == 1:
            sole = active[0]
            self.current_idx = self.player_ids.index(sole)
            self.last_hand = None
            self.pass_count = 0
        else:
            self._advance_turn()

        return TurnResult(True)

    # ── State snapshot ────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "player_ids": self.player_ids,
            "current_player_id": self.current_player_id,
            "hand_counts": {p: len(h) for p, h in self.hands.items()},
            "last_hand": self.last_hand,
            "last_hand_player": self.last_hand_player,
            "fatigue": self.fatigue,
            "round_number": self.round_number,
            "phase": self.phase.name,
        }
