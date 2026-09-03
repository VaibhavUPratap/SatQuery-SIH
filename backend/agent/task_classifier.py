"""Transparent intent routing for SatQuery specialist tools."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    task: str
    reason: str


class TaskClassifier:
    """Deterministic, auditable router; replaceable with an LLM classifier later."""

    def classify(self, query: str, image_count: int, requested_task: str = "auto") -> RouteDecision:
        allowed = {"vqa", "caption", "grounding", "change", "optical_sar", "land_cover"}
        if requested_task != "auto":
            if requested_task not in allowed:
                raise ValueError(f"Unsupported analysis_type '{requested_task}'.")
            if requested_task in {"change", "optical_sar"} and image_count != 2:
                raise ValueError(f"{requested_task} analysis requires exactly two images.")
            if requested_task in {"vqa", "caption", "grounding", "land_cover"} and image_count != 1:
                raise ValueError(f"{requested_task} analysis accepts exactly one image.")
            return RouteDecision(requested_task, "Explicit analysis_type supplied by caller.")
        text = query.lower()
        if image_count == 2:
            if any(word in text for word in ("sar", "radar", "backscatter", "optical-sar", "optical sar")):
                return RouteDecision("optical_sar", "Two inputs plus optical/SAR terminology.")
            return RouteDecision("change", "Two inputs default to bi-temporal analysis.")
        if any(word in text for word in ("caption", "describe this scene", "scene description")):
            return RouteDecision("caption", "Single image plus scene-description intent.")
        if any(word in text for word in ("locate", "highlight", "where is", "bounding box", "ground")):
            return RouteDecision("grounding", "Single image plus region-localization intent.")
        if any(word in text for word in ("land cover", "land-cover", "classify", "classification", "corine")):
            return RouteDecision("land_cover", "Single image plus land-cover classification intent.")
        return RouteDecision("vqa", "Single image defaults to visual question answering.")
