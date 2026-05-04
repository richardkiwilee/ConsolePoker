"""Player deck management."""

from __future__ import annotations

import random
from .card import Card, Rank, Suit


def _build_standard_56() -> list[Card]:
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


class Deck:
    """Each player owns one independent Deck."""

    def __init__(self) -> None:
        self._cards: list[Card] = _build_standard_56()

    # ── Public interface ───────────────────────────────────────────────────

    def shuffle_and_deal(self, hand_size: int = 27) -> list[Card]:
        """Shuffle the deck and return `hand_size` cards as the starting hand."""
        random.shuffle(self._cards)
        hand = self._cards[:hand_size]
        return list(hand)  # copies reference; deck retains full list

    def add_card(self, card: Card) -> None:
        self._cards.append(card)

    def remove_card(self, card: Card) -> bool:
        try:
            self._cards.remove(card)
            return True
        except ValueError:
            return False

    def remove_cards(self, cards: list[Card]) -> None:
        for c in cards:
            self.remove_card(c)

    @property
    def size(self) -> int:
        return len(self._cards)

    @property
    def cards(self) -> list[Card]:
        return list(self._cards)
