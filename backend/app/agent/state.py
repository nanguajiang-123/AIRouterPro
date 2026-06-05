from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentState:
    """LangGraph 的共享状态 — 每个字段对应一个工作流阶段。"""

    # ── input ────────────────────────────────────────────────────
    user_input: str = ""
    source: str = ""
    target: str = ""
    intent_constraints: dict = field(default_factory=dict)

    # ── topology ─────────────────────────────────────────────────
    topology_nodes: list = field(default_factory=list)
    topology_links: list = field(default_factory=list)

    # ── pathfinding ──────────────────────────────────────────────
    candidate_paths: list = field(default_factory=list)
    selected_path: list = field(default_factory=list)

    # ── result ───────────────────────────────────────────────────
    flows_installed: bool = False
    message: str = ""
    error: Optional[str] = None
