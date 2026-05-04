"""Hand type recognition and comparison engine.

All key parameters are stored in CONFIG so that skills/chips can modify them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from .card import Card, Rank


# ── Configurable constants (skills/chips may mutate these) ─────────────────

class HandConfig:
    STRAIGHT_MIN_LEN: int = 5
    CONSEC_PAIR_MIN_GROUPS: int = 3
    CONSEC_TRIP_MIN_GROUPS: int = 2
    BOMB_MIN_COUNT: int = 4


CONFIG = HandConfig()


# ── Hand types ─────────────────────────────────────────────────────────────

class HandType(IntEnum):
    SINGLE           = 1
    PAIR             = 2
    TRIPLE           = 3
    FULL_HOUSE       = 4
    STRAIGHT         = 5
    CONSECUTIVE_PAIR = 6
    CONSECUTIVE_TRIP = 7
    BOMB             = 8
    NUKE             = 9


@dataclass
class Hand:
    type:     HandType
    cards:    list[Card]
    key_rank: Rank   # rank used for comparison within same type/size

    def __len__(self) -> int:
        return len(self.cards)


# ── Custom hand type support (plugin registry) ─────────────────────────────

_custom_hand_registry: list = []  # list of recognize callables


def register_hand_type(recognizer):
    """Register a custom hand recognizer. Called before built-ins."""
    _custom_hand_registry.append(recognizer)


# ── Internal helpers ───────────────────────────────────────────────────────

def _ranks(cards: list[Card]) -> list[Rank]:
    return sorted((c.rank for c in cards), reverse=True)


def _rank_counter(cards: list[Card]) -> Counter:
    return Counter(c.rank for c in cards)


def _is_nuke(cards: list[Card]) -> bool:
    if len(cards) != 4:
        return False
    bigs = sum(1 for c in cards if c.rank == Rank.BIG_JOKER)
    smalls = sum(1 for c in cards if c.rank == Rank.SMALL_JOKER)
    return bigs == 2 and smalls == 2


def _is_bomb(cards: list[Card]) -> Optional[Hand]:
    cnt = _rank_counter(cards)
    if len(cnt) == 1:
        rank, count = next(iter(cnt.items()))
        if count >= CONFIG.BOMB_MIN_COUNT:
            return Hand(HandType.BOMB, cards, rank)
    return None


def _is_straight(cards: list[Card]) -> Optional[Hand]:
    if len(cards) < CONFIG.STRAIGHT_MIN_LEN:
        return None
    ranks = _ranks(cards)
    # No jokers in straight
    if Rank.SMALL_JOKER in ranks or Rank.BIG_JOKER in ranks:
        return None
    # All unique
    if len(set(ranks)) != len(ranks):
        return None
    # Consecutive
    for i in range(len(ranks) - 1):
        if ranks[i] - ranks[i + 1] != 1:
            return None
    return Hand(HandType.STRAIGHT, cards, ranks[0])


def _is_consec_pair(cards: list[Card]) -> Optional[Hand]:
    """Consecutive pairs: e.g. 3 groups of pairs = 6 cards min."""
    n = len(cards)
    if n < CONFIG.CONSEC_PAIR_MIN_GROUPS * 2 or n % 2 != 0:
        return None
    cnt = _rank_counter(cards)
    if any(v != 2 for v in cnt.values()):
        return None
    ranks = sorted(cnt.keys(), reverse=True)
    for i in range(len(ranks) - 1):
        if ranks[i] - ranks[i + 1] != 1:
            return None
    return Hand(HandType.CONSECUTIVE_PAIR, cards, ranks[0])


def _is_consec_trip(cards: list[Card]) -> Optional[Hand]:
    """Consecutive triples, e.g. 2 groups = 6 cards min."""
    n = len(cards)
    if n < CONFIG.CONSEC_TRIP_MIN_GROUPS * 3 or n % 3 != 0:
        return None
    cnt = _rank_counter(cards)
    if any(v != 3 for v in cnt.values()):
        return None
    ranks = sorted(cnt.keys(), reverse=True)
    for i in range(len(ranks) - 1):
        if ranks[i] - ranks[i + 1] != 1:
            return None
    return Hand(HandType.CONSECUTIVE_TRIP, cards, ranks[0])


def _is_full_house(cards: list[Card]) -> Optional[Hand]:
    if len(cards) != 5:
        return None
    cnt = _rank_counter(cards)
    if len(cnt) != 2:
        return None
    counts = sorted(cnt.values())
    if counts != [2, 3]:
        return None
    triple_rank = max(cnt, key=cnt.get)
    return Hand(HandType.FULL_HOUSE, cards, triple_rank)


# ── Public API ─────────────────────────────────────────────────────────────

def recognize(cards: list[Card]) -> Optional[Hand]:
    """Return a Hand if cards form a valid hand type, else None."""
    if not cards:
        return None

    # Custom registry (plugins first)
    for fn in _custom_hand_registry:
        result = fn(cards)
        if result is not None:
            return result

    n = len(cards)

    # Nuke
    if _is_nuke(cards):
        return Hand(HandType.NUKE, cards, Rank.BIG_JOKER)

    # Bomb
    bomb = _is_bomb(cards)
    if bomb:
        return bomb

    if n == 1:
        return Hand(HandType.SINGLE, cards, cards[0].rank)

    if n == 2:
        cnt = _rank_counter(cards)
        if len(cnt) == 1:
            return Hand(HandType.PAIR, cards, _ranks(cards)[0])
        return None

    if n == 3:
        cnt = _rank_counter(cards)
        if len(cnt) == 1:
            return Hand(HandType.TRIPLE, cards, _ranks(cards)[0])
        return None

    if n == 5:
        fh = _is_full_house(cards)
        if fh:
            return fh

    # Consecutive types
    st = _is_straight(cards)
    if st:
        return st

    cp = _is_consec_pair(cards)
    if cp:
        return cp

    ct = _is_consec_trip(cards)
    if ct:
        return ct

    return None


def beats(challenger: Hand, current: Hand) -> bool:
    """Return True if `challenger` beats `current`.

    Comparison rules:
    1. Nuke beats everything except another Nuke (equal → not beat).
    2. Bomb beats all non-bomb/non-nuke.
    3. Same type: total card count must be equal, then compare key_rank.
    4. Exception: larger bombs beat smaller bombs (different counts allowed).
    """
    if challenger.type == HandType.NUKE and current.type == HandType.NUKE:
        return False  # equal, not beat
    if challenger.type == HandType.NUKE:
        return True
    if current.type == HandType.NUKE:
        return False

    if challenger.type == HandType.BOMB and current.type != HandType.BOMB:
        return True
    if current.type == HandType.BOMB and challenger.type != HandType.BOMB:
        return False

    # Both bombs: more cards wins; if equal count → compare key rank
    if challenger.type == HandType.BOMB and current.type == HandType.BOMB:
        if len(challenger) != len(current):
            return len(challenger) > len(current)
        return challenger.key_rank > current.key_rank

    # Normal comparison: must be same type and same total card count
    if challenger.type != current.type:
        return False
    if len(challenger) != len(current):
        return False
    return challenger.key_rank > current.key_rank


def suggest_plays(hand: list[Card], current: Optional[Hand]) -> list[list[Card]]:
    """Return a list of valid plays from `hand` that beat `current`.

    Uses a simple heuristic: try all subsets up to a reasonable size.
    Suitable for AI and the 'H' hint key. Not exhaustive for large hands.
    """
    from itertools import combinations

    results: list[list[Card]] = []
    max_len = min(len(hand), 10)  # cap to keep it fast

    for size in range(1, max_len + 1):
        for combo in combinations(hand, size):
            h = recognize(list(combo))
            if h is None:
                continue
            if current is None or beats(h, current):
                results.append(list(combo))

    return results
