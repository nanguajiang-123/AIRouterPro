from __future__ import annotations

from typing import Any

import networkx as nx

from app.agent.state import AgentState
from app.agent.tools import (
    fetch_inventory,
    fetch_topology,
    get_routing_model,
    install_flows,
    to_frontend_topology,
    to_graph,
)
from app.logger import log
from app.agent.llm_client import classify_intent


def parse_intent(state: AgentState) -> dict[str, Any]:
    """解析自然语言场景 → 输出 ``"streaming"`` 或 ``"voip"`` 类型约束。

    通过 LLM（DeepSeek）对用户场景描述（如"打游戏""看视频"）分类：
      - ``streaming`` → 瓶颈带宽优先（phi ≈ 0.8）
      - ``voip``     → 端到端延迟优先（phi ≈ 0.2）
    """
    log.info("Parsing intent: scenario='{}'", state.user_input)

    src = state.source.strip() if state.source else ""
    dst = state.target.strip() if state.target else ""

    # ── LLM 场景分类 ──
    traffic_type = "streaming"
    if state.user_input and state.user_input.strip():
        traffic_type = classify_intent(state.user_input)

    # ── 映射为约束 ──
    if traffic_type == "voip":
        constraints: dict = {
            "traffic_type": "voip",
            "delay_sensitive": True,
            "bandwidth_sensitive": False,
            "phi": 0.2,  # φ 低 → 时延敏感
        }
    else:
        constraints = {
            "traffic_type": "streaming",
            "delay_sensitive": False,
            "bandwidth_sensitive": True,
            "phi": 0.8,  # φ 高 → 带宽敏感
        }

    log.info("Intent classified: {} (src={}, dst={})", traffic_type, src or "?", dst or "?")

    if not src:
        log.warning("Source not specified, will try to infer from topology")
    if not dst:
        log.warning("Destination not specified, will try to infer from topology")

    return {
        "source": src,
        "target": dst,
        "intent_constraints": constraints,
    }


def fetch_topology_data(state: AgentState) -> dict[str, Any]:
    """从 ODL 获取当前网络拓扑。"""
    log.info("Fetching network topology from ODL")

    nodes_data = fetch_inventory()
    topo_data = fetch_topology()

    if not nodes_data and not topo_data:
        return {"error": "Failed to fetch topology from ODL"}

    frontend = to_frontend_topology(nodes_data, topo_data)

    return {
        "topology_nodes": frontend["nodes"],
        "topology_links": frontend["links"],
    }


def compute_path(state: AgentState) -> dict[str, Any]:
    """计算源到目标的最优路径（RL 模型或回退算法）。"""
    if not state.source or not state.target:
        return {"error": "Missing source or target"}

    log.info("Computing path: {} → {}", state.source, state.target)

    # 将 ODL 数据转为 networkx 图
    nodes_data = fetch_inventory()
    topo_data = fetch_topology()
    graph = to_graph(nodes_data, topo_data)

    if not graph or graph.number_of_nodes() == 0:
        return {"error": "Empty topology graph"}

    # 调用路由模型
    model = get_routing_model()
    path = model.select_path(graph, state.source, state.target, k=16)

    if not path:
        return {"error": f"No path found between {state.source} and {state.target}"}

    return {
        "selected_path": list(path),
        "candidate_paths": [],  # 暂不保留候选
    }


def install_flow_rules(state: AgentState) -> dict[str, Any]:
    """将选中路径写入 ODL 流表。"""
    if not state.selected_path:
        return {"error": "No path to install"}

    log.info("Installing flow rules: {}", " → ".join(state.selected_path))
    ok = install_flows(state.selected_path)

    return {
        "flows_installed": ok,
        "message": "Flows installed successfully" if ok else "Flow installation failed",
    }
