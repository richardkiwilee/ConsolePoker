"""Chip registry — placeholder chips for initial version."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChipDefinition:
    chip_id:     str
    name:        str
    description: str
    rarity:      int   # 1=common 2=rare 3=epic 4=legendary
    base_price:  int
    class_price: int   # price for class-exclusive chips (0 = universal)
    class_id:    str = ""   # "" = universal
    hooks: dict = field(default_factory=dict, repr=False)

    def instantiate(self):
        """Return a Chip instance for a player to own."""
        from ..entities.player import Chip
        return Chip(
            chip_id=self.chip_id,
            name=self.name,
            description=self.description,
            rarity=self.rarity,
            buy_price=self.base_price,
            hooks=dict(self.hooks),
        )


# Rarity weights for shop appearance
RARITY_WEIGHTS = {1: 60, 2: 25, 3: 10, 4: 5}

# ── Price constants ────────────────────────────────────────────────────────
PRICE_TABLE = {
    1: (4, 6),   # common:  universal, class-exclusive
    2: (7, 9),
    3: (12, 14),
    4: (20, 22),
}

# ── Placeholder chip catalogue ─────────────────────────────────────────────

CHIP_REGISTRY: dict[str, ChipDefinition] = {}


def _reg(chip_id, name, desc, rarity, class_id=""):
    prices = PRICE_TABLE[rarity]
    price = prices[1] if class_id else prices[0]
    CHIP_REGISTRY[chip_id] = ChipDefinition(
        chip_id=chip_id, name=name, description=desc,
        rarity=rarity, base_price=price, class_price=prices[1], class_id=class_id,
    )


# Common chips
_reg("lucky_coin",     "幸运金币",   "每回合开始获得 +1 金币（占位符）。", 1)
_reg("card_draw",      "牌运",       "初始手牌 +2 张（占位符）。",          1)
_reg("mana_crystal",   "法晶",       "法力上限 +1（占位符）。",             1)
_reg("score_booster",  "积分加成",   "每次出牌得分 +50（占位符）。",        1)

# Rare chips
_reg("double_strike",  "双击",       "出牌时 50% 概率触发两次（占位符）。", 2)
_reg("gold_rush",      "淘金热",     "金币上限增加 20（占位符）。",         2)
_reg("echo_play",      "回响",       "对子出牌额外 +100 分（占位符）。",    2)

# Epic chips
_reg("chaos_orb",      "混沌球",     "每回合随机触发一个筹码效果（占位符）。", 3)
_reg("time_warp",      "时空扭曲",   "每局游戏有一次跳过对方回合（占位符）。", 3)

# Legendary chips
_reg("godhand",        "神之手",     "打出炸弹时额外获得 500 分（占位符）。", 4)
_reg("philosopher",    "哲学家之石", "每拥有 3 个筹码获得 1 金币利息（占位符）。", 4)

# Class-specific chips
_reg("warrior_blade",  "战刃",       "战士专属：出牌伤害+1 层（占位符）。",  2, "warrior")
_reg("mage_staff",     "法杖",       "法师专属：法力消耗-1（占位符）。",      2, "mage")
