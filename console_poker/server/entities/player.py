"""Game entities: Player, Room."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

from ..core.deck import Deck
from ..core.card import Card


# ─── Skill ────────────────────────────────────────────────────────────────────

@dataclass
class Skill:
    skill_id:    str
    name:        str
    description: str
    mana_cost:   int
    level:       int = 1
    is_class_skill: bool = False
    # on_use: callable(player, game_state) -> None
    on_use: object = field(default=None, repr=False)
    # on_upgrade: callable(skill) -> None
    on_upgrade: object = field(default=None, repr=False)

    def upgrade(self) -> None:
        self.level += 1
        if callable(self.on_upgrade):
            self.on_upgrade(self)


# ─── Chip ─────────────────────────────────────────────────────────────────────

@dataclass
class Chip:
    chip_id:     str
    name:        str
    description: str
    rarity:      int  # 1=common 2=rare 3=epic 4=legendary
    buy_price:   int
    durability:  int = -1   # -1 = permanent
    # hooks dict: event_name -> callable
    hooks: dict = field(default_factory=dict, repr=False)

    def sell_price(self) -> int:
        return self.buy_price // 2


# ─── Player ───────────────────────────────────────────────────────────────────

class Player:
    MAX_FREE_SKILL_SLOTS = 2
    MAX_CHIP_SLOTS_LIMIT = 9
    INITIAL_CHIP_SLOTS = 3
    INITIAL_COINS = 10
    MANA_MAX_DEFAULT = 10
    MANA_REGEN_DEFAULT = 1
    INITIAL_HAND_SIZE = 27

    # Chip slot unlock costs (cumulative purchases, 6 upgrades from 3→9)
    SLOT_UNLOCK_COSTS = [5, 10, 15, 25, 30, 50]

    def __init__(self, player_id: str, name: str, is_ai: bool = False) -> None:
        self.player_id = player_id
        self.name = name
        self.is_ai = is_ai
        self.is_connected = True
        self.is_ready = False

        # Class
        self.class_id: Optional[str] = None
        self.class_confirmed = False

        # Economy
        self.coins: int = self.INITIAL_COINS
        self.score: int = 0

        # Mana
        self.mana: int = 0
        self.mana_max: int = self.MANA_MAX_DEFAULT
        self.mana_regen: int = self.MANA_REGEN_DEFAULT

        # Skills: [class_skill] + up to 2 free
        self.class_skill: Optional[Skill] = None
        self.free_skills: list[Optional[Skill]] = [None, None]

        # Chips
        self.chip_slots: int = self.INITIAL_CHIP_SLOTS
        self.chips: list[Chip] = []

        # Deck & hand
        self.deck = Deck()
        self.hand: list[Card] = []

        # Shop reserved items (item_ids)
        self.reserved_items: set[str] = set()

    # ── Mana ──────────────────────────────────────────────────────────────

    def regen_mana(self) -> None:
        self.mana = min(self.mana + self.mana_regen, self.mana_max)

    def spend_mana(self, amount: int) -> bool:
        if self.mana < amount:
            return False
        self.mana -= amount
        return True

    # ── Skills ────────────────────────────────────────────────────────────

    @property
    def all_skills(self) -> list[Skill]:
        result: list[Skill] = []
        if self.class_skill:
            result.append(self.class_skill)
        result.extend(s for s in self.free_skills if s is not None)
        return result

    def find_skill(self, skill_id: str) -> Optional[Skill]:
        return next((s for s in self.all_skills if s.skill_id == skill_id), None)

    def equip_skill(self, skill: Skill) -> bool:
        """Try to equip a skill in an empty free slot. Returns True on success."""
        for i, slot in enumerate(self.free_skills):
            if slot is None:
                self.free_skills[i] = skill
                return True
        return False

    def upgrade_or_equip_skill(self, skill: Skill) -> str:
        """Buy a skill: upgrade if owned, else equip. Returns 'upgraded'/'equipped'/'no_slot'."""
        existing = self.find_skill(skill.skill_id)
        if existing:
            existing.upgrade()
            return "upgraded"
        ok = self.equip_skill(skill)
        return "equipped" if ok else "no_slot"

    # ── Chips ─────────────────────────────────────────────────────────────

    def has_chip_space(self) -> bool:
        return len(self.chips) < self.chip_slots

    def add_chip(self, chip: Chip) -> bool:
        if not self.has_chip_space():
            return False
        self.chips.append(chip)
        return True

    def remove_chip(self, chip_id: str) -> Optional[Chip]:
        for i, c in enumerate(self.chips):
            if c.chip_id == chip_id:
                return self.chips.pop(i)
        return None

    def unlock_chip_slot(self) -> Optional[int]:
        """Unlock next chip slot. Returns cost paid or None if at max."""
        unlocked = self.chip_slots - self.INITIAL_CHIP_SLOTS
        if unlocked >= len(self.SLOT_UNLOCK_COSTS):
            return None
        cost = self.SLOT_UNLOCK_COSTS[unlocked]
        if self.coins < cost:
            return None
        self.coins -= cost
        self.chip_slots += 1
        return cost

    # ── Economy ───────────────────────────────────────────────────────────

    def add_coins(self, amount: int) -> None:
        self.coins += amount

    def spend_coins(self, amount: int) -> bool:
        if self.coins < amount:
            return False
        self.coins -= amount
        return True

    def add_score(self, delta: int) -> None:
        self.score += delta

    # ── Hand management ───────────────────────────────────────────────────

    def draw_hand(self, hand_size: int | None = None) -> None:
        size = hand_size if hand_size is not None else self.INITIAL_HAND_SIZE
        self.hand = self.deck.shuffle_and_deal(size)

    def snapshot(self) -> dict:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "score": self.score,
            "coins": self.coins,
            "mana": self.mana,
            "mana_max": self.mana_max,
            "hand_count": len(self.hand),
            "class_id": self.class_id,
            "is_ready": self.is_ready,
            "is_ai": self.is_ai,
            "is_connected": self.is_connected,
        }


# ─── Room ─────────────────────────────────────────────────────────────────────

class Room:
    """Holds all players and overall game configuration."""

    def __init__(self, max_players: int = 8, min_players: int = 2) -> None:
        self.room_id = str(uuid.uuid4())
        self.players: dict[str, Player] = {}
        self.seat_order: list[str] = []  # ordered player IDs
        self.max_players = max_players
        self.min_players = min_players
        self.host_id: Optional[str] = None  # None in server mode

    def add_player(self, player: Player) -> bool:
        if len(self.players) >= self.max_players:
            return False
        self.players[player.player_id] = player
        self.seat_order.append(player.player_id)
        return True

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        if player_id in self.seat_order:
            self.seat_order.remove(player_id)

    def get_player(self, player_id: str) -> Optional[Player]:
        return self.players.get(player_id)

    def all_ready(self) -> bool:
        return bool(self.players) and all(p.is_ready for p in self.players.values())

    def all_class_confirmed(self) -> bool:
        return bool(self.players) and all(
            p.class_confirmed for p in self.players.values()
        )

    @property
    def player_list(self) -> list[Player]:
        return [self.players[pid] for pid in self.seat_order if pid in self.players]
