"""Shop system — generates and manages per-player shop state."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .chip_registry import CHIP_REGISTRY, RARITY_WEIGHTS, ChipDefinition
from .skill_registry import SKILL_REGISTRY, SkillDefinition

INITIAL_REFRESH_COST = 3


@dataclass
class ShopItemEntry:
    item_id:   str
    item_type: str   # chip / skill / card_pack / enchant_pack / delete_pack
    name:      str
    description: str
    price:     int
    rarity:    int = 1
    reserved:  bool = False
    _def: object = field(default=None, repr=False)


class PlayerShop:
    """Per-player shop state."""

    SHELF_SIZE = 6   # 3 chips + 3 non-chips

    def __init__(self, player_id: str, class_id: str = "") -> None:
        self.player_id = player_id
        self.class_id = class_id
        self.items: list[ShopItemEntry] = []
        self.refresh_cost = INITIAL_REFRESH_COST
        self._reserved: dict[str, ShopItemEntry] = {}   # item_id → entry

        self._generate_shelf()

    # ── Generation ────────────────────────────────────────────────────────

    def _weighted_chips(self, n: int) -> list[ChipDefinition]:
        available = [
            c for c in CHIP_REGISTRY.values()
            if c.class_id == "" or c.class_id == self.class_id
        ]
        weights = [RARITY_WEIGHTS.get(c.rarity, 10) for c in available]
        return random.choices(available, weights=weights, k=n)

    def _random_non_chips(self, n: int) -> list[ShopItemEntry]:
        """Return n random non-chip items (skills, packs)."""
        result: list[ShopItemEntry] = []
        kinds = ["skill", "skill", "card_pack", "enchant_pack", "delete_pack"]
        random.shuffle(kinds)
        for kind in kinds[:n]:
            if kind == "skill":
                candidates = [
                    s for s in SKILL_REGISTRY.values()
                    if s.class_id == "" or s.class_id == self.class_id
                ]
                if candidates:
                    s_def = random.choice(candidates)
                    result.append(ShopItemEntry(
                        item_id=s_def.skill_id,
                        item_type="skill",
                        name=s_def.name,
                        description=s_def.description,
                        price=5,
                        rarity=1,
                        _def=s_def,
                    ))
            elif kind == "card_pack":
                result.append(ShopItemEntry(
                    item_id=f"card_pack_{random.randint(1000, 9999)}",
                    item_type="card_pack",
                    name="卡包",
                    description="展示6张牌，选1张加入牌库。",
                    price=8,
                ))
            elif kind == "enchant_pack":
                result.append(ShopItemEntry(
                    item_id=f"enchant_pack_{random.randint(1000, 9999)}",
                    item_type="enchant_pack",
                    name="附魔包",
                    description="从牌库抽6张，选1张附魔。",
                    price=6,
                ))
            elif kind == "delete_pack":
                result.append(ShopItemEntry(
                    item_id=f"delete_pack_{random.randint(1000, 9999)}",
                    item_type="delete_pack",
                    name="删除包",
                    description="从牌库抽6张，选3张移除。",
                    price=4,
                ))
        return result

    def _generate_shelf(self) -> None:
        items: list[ShopItemEntry] = []

        # 3 chips
        for chip_def in self._weighted_chips(3):
            price = chip_def.class_price if chip_def.class_id else chip_def.base_price
            items.append(ShopItemEntry(
                item_id=chip_def.chip_id,
                item_type="chip",
                name=chip_def.name,
                description=chip_def.description,
                price=price,
                rarity=chip_def.rarity,
                _def=chip_def,
            ))

        # 3 non-chips
        items.extend(self._random_non_chips(3))

        # Restore reserved items
        new_ids = {i.item_id for i in items}
        reserved_to_add = [v for v in self._reserved.values() if v.item_id not in new_ids]
        self.items = list(self._reserved.values()) + [i for i in items if i.item_id not in self._reserved]
        self.items = self.items[:self.SHELF_SIZE + len(self._reserved)]

    def refresh(self, coins: int) -> tuple[bool, int]:
        """Refresh shelf, spending coins. Returns (success, new_refresh_cost)."""
        if coins < self.refresh_cost:
            return False, self.refresh_cost
        cost = self.refresh_cost
        self.refresh_cost += 1
        self._generate_shelf()
        return True, cost

    def reset_refresh_cost(self) -> None:
        self.refresh_cost = INITIAL_REFRESH_COST

    # ── Actions ───────────────────────────────────────────────────────────

    def get_item(self, item_id: str) -> Optional[ShopItemEntry]:
        return next((i for i in self.items if i.item_id == item_id), None)

    def buy(self, item_id: str) -> Optional[ShopItemEntry]:
        item = self.get_item(item_id)
        if item is None:
            return None
        self.items.remove(item)
        self._reserved.pop(item_id, None)
        return item

    def reserve(self, item_id: str) -> bool:
        item = self.get_item(item_id)
        if item is None:
            return False
        item.reserved = not item.reserved
        if item.reserved:
            self._reserved[item_id] = item
        else:
            self._reserved.pop(item_id, None)
        return True
