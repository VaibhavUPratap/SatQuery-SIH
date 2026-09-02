"""LangGraph StateGraph orchestration engine for SatQuery AI.

Orchestrates input validation, intent classification, specialist tool invocation,
and evidence fusion into an auditable directed acyclic graph (DAG) workflow.
"""
import logging
from typing import Any, Callable, Dict, List, Optional

from backend.agent.state import AgentState
from backend.agent.task_classifier import TaskClassifier
from backend.agent.tool_registry import tool_registry
from backend.evidence.report import generate_pdf_report
from backend.preprocessing.registration import ImageRegistration
from backend.validation.validator import InputValidator

logger = logging.getLogger("satquery.agent.graph")
classifier = TaskClassifier()


# -------------------------------------------------------------------------
# Node Implementations
# -------------------------------------------------------------------------

def validate_inputs_node(state: AgentState) -> Dict[str, Any]:
    """Node: validates image integrity, dimensions, formats, and coregistration."""
    file_1 = state.get("file_1_path")
    file_2 = state.get("file_2_path")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])

    if not file_1:
        return {
            "is_valid": False,
            "error_message": "Primary image is required.",
            "execution_trace": trace + [{"node": "validate_inputs", "status": "failed", "error": "Primary image missing"}],
        }

    valid_1, error_1, meta_1 = InputValidator.validate_image(file_1)
    if not valid_1:
        return {
            "is_valid": False,
            "error_message": f"Primary image validation failed: {error_1}",
            "execution_trace": trace + [{"node": "validate_inputs", "status": "failed", "error": error_1}],
        }

    pair_metadata = None
    if file_2:
        valid_2, error_2, meta_2 = InputValidator.validate_image(file_2)
        if not valid_2:
            return {
                "is_valid": False,
                "error_message": f"Secondary image validation failed: {error_2}",
                "execution_trace": trace + [{"node": "validate_inputs", "status": "failed", "error": error_2}],
            }
        query = (state.get("query") or "").lower()
        is_optical_sar = "sar" in query and "optical" in query
        pair_validator = (
            ImageRegistration.validate_optical_sar_pair
            if is_optical_sar
            else ImageRegistration.validate_pair
        )
        valid_pair, error_pair, pair_metadata = pair_validator(file_1, file_2)
        if not valid_pair:
            return {
                "is_valid": False,
                "error_message": f"Pair validation failed: {error_pair}",
                "pair_metadata": pair_metadata,
                "execution_trace": trace + [{"node": "validate_inputs", "status": "failed", "error": error_pair}],
            }

    trace_entry = {
        "node": "validate_inputs",
        "status": "passed",
        "image_count": 2 if file_2 else 1,
        "primary_format": meta_1.get("format") if meta_1 else "unknown",
        "pair_validator": "optical_sar" if file_2 and is_optical_sar else "spatial",
    }
    return {
        "is_valid": True,
        "error_message": None,
        "pair_metadata": pair_metadata,
        "execution_trace": trace + [trace_entry],
    }


def classify_intent_node(state: AgentState) -> Dict[str, Any]:
    """Node: classifies user natural language query and configures specialist route."""
    query = state.get("query", "")
    image_count = 2 if state.get("file_2_path") else 1
    requested = state.get("requested_task", "auto")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])

    try:
        decision = classifier.classify(query, image_count, requested)
    except Exception as exc:
        return {
            "is_valid": False,
            "error_message": str(exc),
            "execution_trace": trace + [{"node": "classify_intent", "status": "failed", "error": str(exc)}],
        }

    if decision.task in {"change", "optical_sar"} and not state.get("file_2_path"):
        msg = f"{decision.task} analysis requires two images."
        return {
            "is_valid": False,
            "error_message": msg,
            "route_task": decision.task,
            "route_reason": decision.reason,
            "execution_trace": trace + [{"node": "classify_intent", "status": "failed", "error": msg}],
        }

    trace_entry = {
        "node": "classify_intent",
        "status": "passed",
        "selected_task": decision.task,
        "reason": decision.reason,
    }
    return {
        "route_task": decision.task,
        "route_reason": decision.reason,
        "execution_trace": trace + [trace_entry],
    }


def execute_vqa_node(state: AgentState) -> Dict[str, Any]:
    """Node: executes RemoteSensingVQAModel."""
    tool = tool_registry.get_tool("vqa")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])
    if not tool:
        return {
            "is_valid": False,
            "error_message": "VQA specialist tool is unavailable.",
            "execution_trace": trace + [{"node": "execute_vqa", "status": "failed", "error": "Tool not found"}],
        }

    result = tool.run({"image_path": state["file_1_path"], "question": state["query"]})
    trace_entry = result.get("execution_trace") or {"node": "execute_vqa", "model": tool.name}
    return {
        "task_result": result,
        "execution_trace": trace + [trace_entry],
    }


def execute_caption_node(state: AgentState) -> Dict[str, Any]:
    """Node: executes RemoteSensingCaptionModel."""
    tool = tool_registry.get_tool("caption")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])
    if not tool:
        return {
            "is_valid": False,
            "error_message": "Caption specialist tool is unavailable.",
            "execution_trace": trace + [{"node": "execute_caption", "status": "failed", "error": "Tool not found"}],
        }

    result = tool.run({"image_path": state["file_1_path"]})
    trace_entry = result.get("execution_trace") or {"node": "execute_caption", "model": tool.name}
    return {
        "task_result": result,
        "execution_trace": trace + [trace_entry],
    }


def execute_grounding_node(state: AgentState) -> Dict[str, Any]:
    """Node: executes RemoteSensingGroundingModel."""
    tool = tool_registry.get_tool("grounding")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])
    if not tool:
        return {
            "is_valid": False,
            "error_message": "Grounding specialist tool is unavailable.",
            "execution_trace": trace + [{"node": "execute_grounding", "status": "failed", "error": "Tool not found"}],
        }

    result = tool.run({"image_path": state["file_1_path"], "query": state["query"]})
    trace_entry = result.get("execution_trace") or {"node": "execute_grounding", "model": tool.name}
    return {
        "task_result": result,
        "execution_trace": trace + [trace_entry],
    }


def execute_change_node(state: AgentState) -> Dict[str, Any]:
    """Node: executes ChangeDetectionModel and ChangeVQAModel."""
    detection = tool_registry.get_tool("change_detection")
    change_vqa = tool_registry.get_tool("change_vqa")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])

    if not detection or not change_vqa:
        return {
            "is_valid": False,
            "error_message": "Change specialist tools are unavailable.",
            "execution_trace": trace + [{"node": "execute_change", "status": "failed", "error": "Tools not found"}],
        }

    model_inputs = {"image_path_a": state["file_1_path"], "image_path_b": state["file_2_path"]}
    detected = detection.run(model_inputs)
    answered = change_vqa.run({**model_inputs, "question": state["query"]})

    result = {
        "answer": answered.get("answer"),
        "confidence": answered.get("confidence"),
        "change_summary": detected.get("change_summary"),
        "overlay_b64": detected.get("change_map_b64"),
        "evidence": {
            "change_detection": detected.get("evidence"),
            "change_vqa": answered.get("evidence"),
        },
    }
    steps = [detected.get("execution_trace"), answered.get("execution_trace")]
    return {
        "task_result": result,
        "execution_trace": trace + [s for s in steps if s],
    }


def execute_optical_sar_node(state: AgentState) -> Dict[str, Any]:
    """Node: executes OpticalSARFusionModel."""
    tool = tool_registry.get_tool("optical_sar")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])

    if not tool:
        return {
            "is_valid": False,
            "error_message": "Optical-SAR fusion tool is unavailable.",
            "execution_trace": trace + [{"node": "execute_optical_sar", "status": "failed", "error": "Tool not found"}],
        }

    result = tool.run({
        "optical_path": state["file_1_path"],
        "sar_path": state["file_2_path"],
        "query": state["query"],
    })
    result["answer"] = result.get("summary") or result.get("answer")
    trace_entry = result.get("execution_trace") or {"node": "execute_optical_sar", "model": tool.name}
    return {
        "task_result": result,
        "execution_trace": trace + [trace_entry],
    }


def execute_land_cover_node(state: AgentState) -> Dict[str, Any]:
    """Execute multi-label BigEarthNet v2.0 land-cover classification."""
    tool = tool_registry.get_tool("land_cover")
    trace: List[Dict[str, Any]] = list(state.get("execution_trace") or [])
    if not tool:
        return {"is_valid": False, "error_message": "BigEarthNet land-cover specialist is unavailable.",
                "execution_trace": trace + [{"node": "execute_land_cover", "status": "failed", "error": "Tool not found"}]}
    result = tool.run({"image_path": state["file_1_path"]})
    return {"task_result": result, "execution_trace": trace + [result.get("execution_trace") or {"node": "execute_land_cover", "model": tool.name}]}


def fuse_evidence_node(state: AgentState) -> Dict[str, Any]:
    """Node: assembles final answer, visual overlays, confidence, and PDF report."""
    if not state.get("is_valid", True) or state.get("error_message"):
        error_msg = state.get("error_message") or "Unknown validation error"
        output = {
            "status": "error",
            "detail": error_msg,
            "query": state.get("query"),
            "route": {
                "task": state.get("route_task"),
                "reason": state.get("route_reason"),
            },
            "execution_trace": {"steps": state.get("execution_trace") or []},
        }
        return {"final_output": output}

    task_result = dict(state.get("task_result") or {})
    task_name = state.get("route_task")
    answer = (
        task_result.get("answer")
        or task_result.get("caption")
        or (f"Detected {task_result.get('box_count', 0)} regions." if task_name == "grounding" else "Analysis complete.")
    )

    final_payload: Dict[str, Any] = {
        "status": "success",
        "query": state.get("query"),
        "route": {
            "task": task_name,
            "reason": state.get("route_reason"),
        },
        "answer": answer,
        "confidence": task_result.get("confidence", 0.8),
        "pair_metadata": state.get("pair_metadata"),
        "evidence": task_result.get("evidence"),
        "execution_trace": {"steps": state.get("execution_trace") or []},
    }

    # Pass through task-specific visual artifacts
    for key in (
        "overlay_b64",
        "annotated_image_b64",
        "change_map_b64",
        "change_summary",
        "bounding_boxes",
        "box_count",
        "target",
        "target_detected",
        "predictions",
        "scores",
    ):
        if key in task_result and key not in final_payload:
            final_payload[key] = task_result[key]

    if "overlay_b64" not in final_payload and final_payload.get("annotated_image_b64"):
        final_payload["overlay_b64"] = final_payload["annotated_image_b64"]

    if state.get("include_report"):
        final_payload["report_pdf_b64"] = generate_pdf_report("SatQuery AI Evidence Report", final_payload)

    return {"final_output": final_payload}


# -------------------------------------------------------------------------
# Conditional Edge Functions
# -------------------------------------------------------------------------

def validation_condition(state: AgentState) -> str:
    """Branches after validation: continue to classifier if valid, else fuse evidence."""
    if not state.get("is_valid", True):
        return "fuse_evidence"
    return "classify_intent"


def specialist_routing_condition(state: AgentState) -> str:
    """Branches after classifier: routes to corresponding specialist node."""
    if not state.get("is_valid", True):
        return "fuse_evidence"

    task = state.get("route_task")
    routing_map = {
        "vqa": "execute_vqa",
        "caption": "execute_caption",
        "grounding": "execute_grounding",
        "change": "execute_change",
        "optical_sar": "execute_optical_sar",
        "land_cover": "execute_land_cover",
    }
    return routing_map.get(task, "fuse_evidence")


# -------------------------------------------------------------------------
# StateGraph Runner & Compiler
# -------------------------------------------------------------------------

class SatQueryStateGraph:
    """
    StateGraph wrapper supporting both native LangGraph (when installed)
    and an embedded DAG runner with in-memory thread persistence.
    """

    def __init__(self):
        self._checkpoints: Dict[str, List[AgentState]] = {}
        self._compiled_graph = None
        self._init_graph()

    def _init_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
            from langgraph.checkpoint.memory import MemorySaver

            builder = StateGraph(AgentState)
            builder.add_node("validate_inputs", validate_inputs_node)
            builder.add_node("classify_intent", classify_intent_node)
            builder.add_node("execute_vqa", execute_vqa_node)
            builder.add_node("execute_caption", execute_caption_node)
            builder.add_node("execute_grounding", execute_grounding_node)
            builder.add_node("execute_change", execute_change_node)
            builder.add_node("execute_optical_sar", execute_optical_sar_node)
            builder.add_node("execute_land_cover", execute_land_cover_node)
            builder.add_node("fuse_evidence", fuse_evidence_node)

            builder.add_edge(START, "validate_inputs")
            builder.add_conditional_edges(
                "validate_inputs",
                validation_condition,
                {"classify_intent": "classify_intent", "fuse_evidence": "fuse_evidence"},
            )
            builder.add_conditional_edges(
                "classify_intent",
                specialist_routing_condition,
                {
                    "execute_vqa": "execute_vqa",
                    "execute_caption": "execute_caption",
                    "execute_grounding": "execute_grounding",
                    "execute_change": "execute_change",
                    "execute_optical_sar": "execute_optical_sar",
                    "execute_land_cover": "execute_land_cover",
                    "fuse_evidence": "fuse_evidence",
                },
            )

            for specialist_node in ("execute_vqa", "execute_caption", "execute_grounding", "execute_change", "execute_optical_sar", "execute_land_cover"):
                builder.add_edge(specialist_node, "fuse_evidence")

            builder.add_edge("fuse_evidence", END)

            checkpointer = MemorySaver()
            self._compiled_graph = builder.compile(checkpointer=checkpointer)
            logger.info("Compiled native LangGraph StateGraph agent.")
        except Exception as exc:
            logger.info(f"Using built-in DAG runner ({exc}).")
            self._compiled_graph = None

    def invoke(self, initial_state: AgentState, config: Optional[Dict[str, Any]] = None) -> AgentState:
        """Executes the StateGraph workflow on the given initial state."""
        thread_id = None
        if config and "configurable" in config:
            thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            thread_id = initial_state.get("thread_id") or "default"

        if self._compiled_graph is not None:
            cfg = {"configurable": {"thread_id": thread_id}}
            result = self._compiled_graph.invoke(initial_state, cfg)
            return result

        # Built-in fallback DAG runner executing the exact graph topology
        state = dict(initial_state)

        # 1. validate_inputs
        state.update(validate_inputs_node(state))

        # 2. conditional branch after validation
        next_node = validation_condition(state)
        if next_node == "classify_intent":
            # 3. classify_intent
            state.update(classify_intent_node(state))
            # 4. conditional branch to specialist
            specialist = specialist_routing_condition(state)
            specialist_map = {
                "execute_vqa": execute_vqa_node,
                "execute_caption": execute_caption_node,
                "execute_grounding": execute_grounding_node,
                "execute_change": execute_change_node,
                "execute_optical_sar": execute_optical_sar_node,
                "execute_land_cover": execute_land_cover_node,
            }
            if specialist in specialist_map:
                state.update(specialist_map[specialist](state))

        # 5. fuse_evidence
        state.update(fuse_evidence_node(state))

        # Save checkpoint in memory
        if thread_id not in self._checkpoints:
            self._checkpoints[thread_id] = []
        self._checkpoints[thread_id].append(dict(state))

        return state

    def get_state_history(self, thread_id: str) -> List[AgentState]:
        """Retrieve execution state history for a given thread/session."""
        if self._compiled_graph is not None:
            config = {"configurable": {"thread_id": thread_id}}
            return [checkpoint.values for checkpoint in self._compiled_graph.get_state_history(config)]
        return self._checkpoints.get(thread_id, [])


# Singleton graph instance
agent_graph = SatQueryStateGraph()
