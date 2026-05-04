"""Skill registry — available skills for purchase in the shop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillDefinition:
    skill_id:    str
    name:        str
    description: str
    mana_cost:   int
    class_id:    str = ""   # "" = universal
    # on_use: callable(player, game_state) -> None
    on_use: object = field(default=None, repr=False)

    def instantiate(self, level: int = 1):
        from ..entities.player import Skill
        return Skill(
            skill_id=self.skill_id,
            name=self.name,
            description=self.description,
            mana_cost=self.mana_cost,
            level=level,
            is_class_skill=False,
            on_use=self.on_use,
        )


SKILL_REGISTRY: dict[str, SkillDefinition] = {}


def _reg(skill_id, name, desc, mana_cost, class_id="", on_use=None):
    SKILL_REGISTRY[skill_id] = SkillDefinition(
        skill_id=skill_id, name=name, description=desc,
        mana_cost=mana_cost, class_id=class_id, on_use=on_use,
    )


# Universal skills
_reg("insight",    "洞察",     "查看任意玩家的手牌一张（占位符）。",  1)
_reg("mana_surge", "法力涌动", "立即回复 3 点法力（占位符）。",       0,
     on_use=lambda p, _: setattr(p, "mana", min(p.mana + 3, p.mana_max)))
_reg("coin_toss",  "投币",     "50%概率获得 5 金币（占位符）。",      2)
_reg("discard",    "弃牌",     "弃掉最多 3 张手牌（占位符）。",       1)

# Class-specific skills
_reg("warrior_rage",  "狂暴",   "战士专属：下一张出牌得分翻倍（占位符）。", 3, "warrior")
_reg("mage_blink",    "闪现",   "法师专属：瞬间移动至得分最高的玩家后面（占位符）。", 2, "mage")
_reg("rogue_vanish",  "消失",   "刺客专属：本回合不受任何技能影响（占位符）。", 2, "rogue")
_reg("priest_divine", "神佑",   "牧师专属：清除所有 debuff（占位符）。",      1, "priest")
_reg("paladin_aura",  "圣光光环", "圣骑士专属：所有队友获得 1 点法力（占位符）。", 2, "paladin")
