"""State schema for the SatQuery LangGraph orchestration graph."""
from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """
    Complete state container passed across nodes in the SatQuery StateGraph.
    Tracks user input, validation status, routing decisions, specialist outputs,
    execution traces, and the assembled final response.
    """
    # Inputs
    query: str
    image_count: int
    requested_task: str
    file_1_path: str
    file_2_path: Optional[str]
    include_report: bool
    thread_id: Optional[str]

    # Validation and routing state
    is_valid: bool
    error_message: Optional[str]
    pair_metadata: Optional[Dict[str, Any]]
    nisar_processing_result: Optional[Dict[str, Any]]
    allow_large_nisar_grid: bool
    route_task: Optional[str]
    route_reason: Optional[str]

    # Execution and outputs
    task_result: Optional[Dict[str, Any]]
    execution_trace: List[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]
