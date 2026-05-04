"""Class registry — placeholder classes for the initial version."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.player import Player


@dataclass
class ClassDefinition:
    class_id:    str
    name:        str
    description: str
    # Initial skill factory
    class_skill_factory: object = field(default=None, repr=False)

    def apply_start(self, player: "Player") -> None:
        """Called once when the game starts after class selection."""
        if callable(self.class_skill_factory):
            skill = self.class_skill_factory()
            player.class_skill = skill


# ── Placeholder classes ────────────────────────────────────────────────────

def _make_warrior_skill():
    from ..entities.player import Skill
    return Skill(
        skill_id="warrior_strike",
        name="战士之击",
        description="本回合出牌额外触发一次筹码效果（占位符）。",
        mana_cost=2,
        is_class_skill=True,
    )


def _make_mage_skill():
    from ..entities.player import Skill
    return Skill(
        skill_id="mage_arcane",
        name="奥术爆发",
        description="获得 2 点额外法力（占位符）。",
        mana_cost=0,
        is_class_skill=True,
        on_use=lambda player, _: setattr(player, "mana", min(player.mana + 2, player.mana_max)),
    )


def _make_rogue_skill():
    from ..entities.player import Skill
    return Skill(
        skill_id="rogue_shadow",
        name="暗影突袭",
        description="下次出牌无视出牌规则限制（占位符）。",
        mana_cost=3,
        is_class_skill=True,
    )


def _make_priest_skill():
    from ..entities.player import Skill
    return Skill(
        skill_id="priest_heal",
        name="神圣愈合",
        description="获得 30 金币（占位符）。",
        mana_cost=1,
        is_class_skill=True,
        on_use=lambda player, _: player.add_coins(30),
    )


def _make_paladin_skill():
    from ..entities.player import Skill
    return Skill(
        skill_id="paladin_guard",
        name="圣盾",
        description="本轮不受疲劳弃牌惩罚（占位符）。",
        mana_cost=2,
        is_class_skill=True,
    )


CLASS_REGISTRY: dict[str, ClassDefinition] = {
    "warrior": ClassDefinition(
        class_id="warrior", name="战士", description="擅长强力出牌，技能增强筹码效果。",
        class_skill_factory=_make_warrior_skill,
    ),
    "mage": ClassDefinition(
        class_id="mage", name="法师", description="法力充沛，奥术爆发瞬间获得额外法力。",
        class_skill_factory=_make_mage_skill,
    ),
    "rogue": ClassDefinition(
        class_id="rogue", name="刺客", description="规则破坏者，可无视出牌规则约束。",
        class_skill_factory=_make_rogue_skill,
    ),
    "priest": ClassDefinition(
        class_id="priest", name="牧师", description="丰厚的金币收益，经济型职业。",
        class_skill_factory=_make_priest_skill,
    ),
    "paladin": ClassDefinition(
        class_id="paladin", name="圣骑士", description="坚韧防御，免疫疲劳惩罚。",
        class_skill_factory=_make_paladin_skill,
    ),
}
