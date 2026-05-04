"""Phase flow engine.

Executes a sequence of phase nodes as defined by a template.
Nodes: combat, shop, reward.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator


class NodeType(Enum):
    COMBAT = auto()
    SHOP   = auto()
    REWARD = auto()


@dataclass
class PhaseNode:
    node_type: NodeType
    config: dict  # node-specific config from template


class PhaseEngine:
    """Drives the game through a template-defined list of phase nodes."""

    def __init__(self, nodes: list[PhaseNode]) -> None:
        self._nodes: list[PhaseNode] = nodes
        self._index: int = 0

    @property
    def current(self) -> PhaseNode | None:
        if self._index < len(self._nodes):
            return self._nodes[self._index]
        return None

    @property
    def is_done(self) -> bool:
        return self._index >= len(self._nodes)

    def advance(self) -> None:
        """Move to the next phase node."""
        self._index += 1

    def remaining(self) -> list[PhaseNode]:
        return self._nodes[self._index:]

    @classmethod
    def from_template(cls, template: dict) -> "PhaseEngine":
        """Build a PhaseEngine from a JSON-loaded template dict.

        Template format::

            {
              "name": "classic",
              "nodes": [
                {"type": "combat"},
                {"type": "shop"},
                {"type": "combat"},
                {"type": "reward", "picks": 1}
              ]
            }
        """
        type_map = {
            "combat": NodeType.COMBAT,
            "shop":   NodeType.SHOP,
            "reward": NodeType.REWARD,
        }
        nodes: list[PhaseNode] = []
        for entry in template.get("nodes", []):
            node_type_str = entry.get("type", "").lower()
            if node_type_str not in type_map:
                raise ValueError(f"Unknown phase node type: {node_type_str!r}")
            nodes.append(PhaseNode(
                node_type=type_map[node_type_str],
                config={k: v for k, v in entry.items() if k != "type"},
            ))
        return cls(nodes)
