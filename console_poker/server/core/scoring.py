"""Scoring and coin settlement logic.

All calculation functions are kept isolated so they can be unit-tested and
adjusted independently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RoundScoreResult:
    player_id:   str
    score_delta: int
    coin_delta:  int


def calc_round_scores(
    player_ids: list[str],
    remaining_cards: dict[str, int],   # player_id → cards left
    winner_id: str,
    total_scores_before: dict[str, int],
) -> list[RoundScoreResult]:
    """Calculate per-player score and coin deltas for one combat round.

    Formula (x = number of players):
        base = 1000 * x
        winner:  base + 100 * Σ(other players' remaining cards)
        loser:   base - 100 * own remaining cards
    """
    x = len(player_ids)
    base = 1000 * x

    results: list[RoundScoreResult] = []
    for pid in player_ids:
        remaining = remaining_cards.get(pid, 0)
        if pid == winner_id:
            others_remaining = sum(
                v for k, v in remaining_cards.items() if k != pid
            )
            score_delta = base + 100 * others_remaining
        else:
            score_delta = base - 100 * remaining
        results.append(RoundScoreResult(
            player_id=pid,
            score_delta=score_delta,
            coin_delta=0,
        ))

    return results


def calc_coin_settlement(
    player_ids: list[str],
    current_coins: dict[str, int],
    current_scores: dict[str, int],   # after this round's score update
    winner_id: str,
) -> dict[str, int]:
    """Return coin deltas (per player) for end-of-round coin settlement.

    Order:
    1. Interest: +1 for every 5 coins, capped at +5
    2. Win/loss bonus: winner +20, others +10
    3. Trailing subsidy: per 1000 score behind leader → +1 coin (no cap)
    """
    highest_score = max(current_scores.values()) if current_scores else 0
    deltas: dict[str, int] = {}

    for pid in player_ids:
        coins = current_coins.get(pid, 0)
        interest = min(coins // 5, 5)
        win_bonus = 20 if pid == winner_id else 10
        score_gap = max(0, highest_score - current_scores.get(pid, 0))
        subsidy = score_gap // 1000
        deltas[pid] = interest + win_bonus + subsidy

    return deltas
