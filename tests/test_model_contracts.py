from pathlib import Path

from backend.agent.graph import classify_intent_node
from backend.agent.task_classifier import TaskClassifier
from backend.models.grounding.model import RemoteSensingGroundingModel


ROOT = Path(__file__).resolve().parents[1]


def test_explicit_task_requires_correct_image_count():
    classifier = TaskClassifier()
    for task, count in (("change", 1), ("vqa", 2), ("land_cover", 2)):
        try:
            classifier.classify("test", count, task)
        except ValueError:
            continue
        raise AssertionError(f"{task} accepted invalid image count")


def test_unknown_grounding_target_does_not_return_fake_boxes():
    result = RemoteSensingGroundingModel().run({
        "image_path": str(ROOT / "datasets/samples/forest_scene.png"),
        "query": "find aircraft",
    })
    assert result["status"] == "unsupported_query"
    assert result["bounding_boxes"] == []
    assert result["confidence"] == 0.0


def test_auto_land_cover_query_on_rgb_routes_to_vqa():
    result = classify_intent_node({
        "query": "What land cover is visible in this image?",
        "image_count": 1,
        "requested_task": "auto",
        "meta_1": {"bands": 3},
    })

    assert result["route_task"] == "vqa"
    assert "RGB image detected" in result["route_reason"]