from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter

from app.agent.graph import get_agent
from app.agent.state import AgentState
from app.models.schemas import PlanRequest, PlanResponse
from app.logger import log

router = APIRouter(prefix="/api", tags=["plan"])


@router.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    """提交路径规划请求 → LangGraph Agent 全流程执行。"""
    log.info("POST /api/plan  source={}  target={}", req.source, req.target)

    initial = AgentState(
        user_input=req.scenario or "",
        source=req.source,
        target=req.target,
    )

    try:
        agent = get_agent()
        thread_id = uuid4().hex[:12]
        result = agent.invoke(initial, config={"configurable": {"thread_id": thread_id}})

        if result.get("error"):
            return PlanResponse(status="error", message=result["error"])

        return PlanResponse(
            status="success",
            path=result.get("selected_path", []),
            message=result.get("message", "Path computed successfully"),
        )
    except Exception as e:
        log.error("Agent execution failed: {}", e)
        return PlanResponse(status="error", message=str(e))
