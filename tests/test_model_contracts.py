from pathlib import Path

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