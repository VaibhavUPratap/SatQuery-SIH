import logging
import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status, Depends

from backend.agent.graph import agent_graph
from backend.agent.state import AgentState
from backend.config import settings
from backend.api.auth import current_user
from backend.api.upload import persist_upload

logger = logging.getLogger("satquery.api.agent")
router = APIRouter()


@router.post("/agent", status_code=status.HTTP_200_OK)
async def execute_agent(
    file_1: UploadFile = File(..., description="Primary image"),
    file_2: UploadFile | None = File(None, description="Optional paired image"),
    query: str = Form(...),
    analysis_type: str = Form("auto"),
    include_report: bool = Form(False),
    thread_id: str | None = Form(None),
    user: str = Depends(current_user),
):
    """Execute LangGraph StateGraph agent for remote sensing image analysis."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    paths = []
    try:
        first = await persist_upload(file_1, "agent_1")
        paths.append(first)
        second = None
        if file_2:
            second = await persist_upload(file_2, "agent_2")
            paths.append(second)

        session_id = thread_id or str(uuid.uuid4())
        initial_state: AgentState = {
            "query": query,
            "image_count": len(paths),
            "requested_task": analysis_type,
            "file_1_path": first,
            "file_2_path": second,
            "include_report": include_report,
            "thread_id": session_id,
        }

        graph_result = agent_graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}},
        )

        final_output = graph_result.get("final_output") or {}
        if final_output.get("status") == "error":
            raise HTTPException(status_code=400, detail=final_output.get("detail", "Execution failed"))

        final_output["thread_id"] = session_id
        return final_output
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc
    finally:
        for path in paths:
            if os.path.exists(path):
                os.remove(path)

