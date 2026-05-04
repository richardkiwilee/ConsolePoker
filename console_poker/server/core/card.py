"""Card and Enchantment definitions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable


class Rank(IntEnum):
    TWO         = 2
    THREE       = 3
    FOUR        = 4
    FIVE        = 5
    SIX         = 6
    SEVEN       = 7
    EIGHT       = 8
    NINE        = 9
    TEN         = 10
    JACK        = 11
    QUEEN       = 12
    KING        = 13
    ACE         = 14
    SMALL_JOKER = 15
    BIG_JOKER   = 16

    def display(self) -> str:
        names = {
            10: "10", 11: "J", 12: "Q", 13: "K", 14: "A",
            15: "小王", 16: "大王",
        }
        return names.get(self.value, str(self.value))


class Suit(IntEnum):
    NONE    = 0
    SPADE   = 1  # ♠
    HEART   = 2  # ♥
    DIAMOND = 3  # ♦
    CLUB    = 4  # ♣

    def display(self) -> str:
        return {0: "", 1: "♠", 2: "♥", 3: "♦", 4: "♣"}.get(self.value, "")


class EnchantmentTrigger(IntEnum):
    ON_PLAY       = 1   # triggered when card is played
    PASSIVE       = 2   # always active while held
    ON_ENTER_DECK = 3   # when card enters deck
    ON_LEAVE_DECK = 4   # when card leaves deck


@dataclass
class Enchantment:
    enchant_id:  str
    name:        str
    description: str
    trigger:     EnchantmentTrigger
    color:       str   # ANSI color code
    is_permanent: bool = True   # permanent = survives between rounds
    # Effect callback: (card, context) -> None
    effect: Callable | None = field(default=None, repr=False)


@dataclass
class Card:
    """A single playing card with an optional enchantment list."""

    rank: Rank
    suit: Suit
    card_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enchantments: list[Enchantment] = field(default_factory=list)
    # Special cards injected by skills/chips don't belong to the deck
    is_special: bool = False
    can_enchant: bool = True

    # ── Comparison ─────────────────────────────────────────────────────────

    def __lt__(self, other: Card) -> bool:
        return self.rank < other.rank

    def __le__(self, other: Card) -> bool:
        return self.rank <= other.rank

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.card_id == other.card_id

    def __hash__(self) -> int:
        return hash(self.card_id)

    # ── Display ────────────────────────────────────────────────────────────

    def short(self) -> str:
        """Short string representation, e.g. 'A♠' or '小王'."""
        if self.rank in (Rank.SMALL_JOKER, Rank.BIG_JOKER):
            return self.rank.display()
        return f"{self.rank.display()}{self.suit.display()}"

    def enchant_colors(self) -> list[str]:
        return [e.color for e in self.enchantments]

    # ── Factory helpers ────────────────────────────────────────────────────

    @classmethod
    def standard_deck() -> list[Card]:
        """Return a fresh 56-card deck (52 standard + 2 small jokers + 2 big jokers)."""
        cards: list[Card] = []
        for suit in (Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB):
            for rank in Rank:
                if rank in (Rank.SMALL_JOKER, Rank.BIG_JOKER):
                    continue
                cards.append(Card(rank=rank, suit=suit))
        cards.append(Card(rank=Rank.SMALL_JOKER, suit=Suit.NONE))
        cards.append(Card(rank=Rank.SMALL_JOKER, suit=Suit.NONE))
        cards.append(Card(rank=Rank.BIG_JOKER, suit=Suit.NONE))
        cards.append(Card(rank=Rank.BIG_JOKER, suit=Suit.NONE))
        return cards
