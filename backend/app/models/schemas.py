from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ── Topology ──────────────────────────────────────────────────────────

class TopologyNode(BaseModel):
    id: str
    name: str
    type: str  # "switch" | "host"


class TopologyLink(BaseModel):
    source: str
    target: str
    bandwidth: Optional[float] = None
    delay: Optional[float] = None


class TopologyResponse(BaseModel):
    nodes: list[TopologyNode] = []
    links: list[TopologyLink] = []


# ── Plan ──────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    source: str
    target: str
    scenario: Optional[str] = None


class PlanResponse(BaseModel):
    status: str = "success"  # "success" | "error"
    path: list[str] = []
    message: str = ""
