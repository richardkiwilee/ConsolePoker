"""AI placeholder — random decision-making for all game actions."""

from __future__ import annotations

import random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.player import Player
    from ..core.combat import CombatState
    from ..core.hand import Hand


class AIAgent:
    """Placeholder AI that makes random valid decisions.

    All methods are designed so that a smarter strategy can replace the body
    without changing the interface.
    """

    def __init__(self, player_id: str) -> None:
        self.player_id = player_id

    # ── Combat decisions ──────────────────────────────────────────────────

    def choose_play(
        self,
        hand: list,         # list[Card]
        current: Optional["Hand"],
        state: "CombatState",
    ) -> tuple[list, bool]:
        """Return (cards_to_play, should_pass).

        Returns ([], True) to pass, or a valid card list to play.
        """
        from ..core.hand import suggest_plays
        options = suggest_plays(hand, current)
        if not options:
            return [], True
        # Randomly decide to pass ~30% of the time when we have options
        if current is not None and random.random() < 0.3:
            return [], True
        return random.choice(options), False

    def choose_skill(self, player: "Player") -> Optional[str]:
        """Return skill_id to use, or None to skip."""
        usable = [s for s in player.all_skills if s.mana_cost <= player.mana]
        if not usable or random.random() < 0.7:
            return None
        return random.choice(usable).skill_id

    # ── Class selection ───────────────────────────────────────────────────

    def choose_class(self, available_classes: list[str]) -> str:
        return random.choice(available_classes) if available_classes else "warrior"

    # ── Shop decisions ────────────────────────────────────────────────────

    def shop_actions(self, player: "Player", shop) -> list[tuple[str, str]]:
        """Return list of (action, item_id) tuples: 'buy' or 'sell'."""
        actions: list[tuple[str, str]] = []
        for item in shop.items:
            if player.coins >= item.price and random.random() < 0.4:
                actions.append(("buy", item.item_id))
        return actions
