import asyncio
import logging
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.agent.graph import agent_graph
from backend.agent.state import AgentState
from backend.api.auth import current_user
from backend.api.jobs import sanitize_result_paths
from backend.api.upload import persist_upload
from backend.config import settings

logger = logging.getLogger("satquery.api.agent")
router = APIRouter()

# Global semaphore bounding max concurrent synchronous model executions
_agent_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_JOBS)


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
    """Execute LangGraph StateGraph agent for remote sensing image analysis with isolation & concurrency bounding."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # Concurrency capacity check
    if _agent_semaphore.locked():
        logger.warning("Synchronous agent execution busy; queuing or rejecting.")
    
    try:
        # Acquire slot or wait with bounded timeout
        await asyncio.wait_for(_agent_semaphore.acquire(), timeout=5.0)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Server inference capacity busy. Please submit via /jobs queue or try again shortly."
        )

    session_id = thread_id or str(uuid.uuid4())
    paths: list[str] = []
    job_dir: str | None = None

    try:
        first, job_dir = await persist_upload(file_1, "primary", job_id=session_id)
        paths.append(first)
        second = None
        if file_2:
            second, _ = await persist_upload(file_2, "secondary", job_id=session_id)
            paths.append(second)

        initial_state: AgentState = {
            "query": query,
            "image_count": len(paths),
            "requested_task": analysis_type,
            "file_1_path": first,
            "file_2_path": second,
            "include_report": include_report,
            "thread_id": session_id,
        }

        # Run graph in threadpool to avoid blocking event loop
        loop = asyncio.get_running_loop()
        graph_result = await loop.run_in_executor(
            None,
            lambda: agent_graph.invoke(
                initial_state,
                config={"configurable": {"thread_id": session_id}},
            )
        )

        raw_output = graph_result.get("final_output") or {}
        if raw_output.get("status") == "error":
            raise HTTPException(status_code=400, detail=raw_output.get("detail", "Execution failed"))

        final_output = sanitize_result_paths(raw_output)
        final_output["thread_id"] = session_id
        return final_output
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent execution failed for user %s", user)
        raise HTTPException(status_code=500, detail="Agent execution encountered an internal error.") from exc
    finally:
        _agent_semaphore.release()
        for path in paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if job_dir and os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
