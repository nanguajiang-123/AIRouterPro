from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

from app.agent.state import AgentState
from app.agent.nodes import (
    parse_intent,
    fetch_topology_data,
    compute_path,
    install_flow_rules,
)


def build_agent() -> CompiledStateGraph:
    """构建并编译 LangGraph 工作流。

    节点顺序:
      1. parse_intent      — 解析自然语言输入
      2. fetch_topology    — 从 ODL 获取拓扑
      3. compute_path      — RL 模型寻路
      4. install_flows     — 下发流表到 ODL
    """
    builder = StateGraph(AgentState)

    builder.add_node("parse_intent", parse_intent)
    builder.add_node("fetch_topology", fetch_topology_data)
    builder.add_node("compute_path", compute_path)
    builder.add_node("install_flows", install_flow_rules)

    builder.add_edge(START, "parse_intent")
    builder.add_edge("parse_intent", "fetch_topology")
    builder.add_edge("fetch_topology", "compute_path")
    builder.add_edge("compute_path", "install_flows")
    builder.add_edge("install_flows", END)

    return builder.compile(checkpointer=MemorySaver())


_compiled: CompiledStateGraph | None = None


def get_agent() -> CompiledStateGraph:
    global _compiled
    if _compiled is None:
        _compiled = build_agent()
    return _compiled
