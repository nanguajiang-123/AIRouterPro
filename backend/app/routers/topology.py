from __future__ import annotations

from fastapi import APIRouter

from app.agent.tools import fetch_inventory, fetch_topology, to_frontend_topology
from app.logger import log
from app.models.schemas import TopologyResponse

router = APIRouter(prefix="/api", tags=["topology"])


@router.get("/topology", response_model=TopologyResponse)
def get_topology() -> TopologyResponse:
    """返回当前网络拓扑（交换机 + 主机 + 链路）。"""
    log.debug("GET /api/topology")

    try:
        nodes_data = fetch_inventory()
        topo_data = fetch_topology()
        data = to_frontend_topology(nodes_data, topo_data)
        return TopologyResponse(**data)
    except Exception as e:
        log.warning("Failed to fetch topology: {}", e)
        return TopologyResponse()
