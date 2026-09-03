from pathlib import Path

from PIL import Image

from backend.models.vqa.model import RemoteSensingVQAModel


ROOT = Path(__file__).resolve().parents[1]


def test_evidence_guard_corrects_water_contradiction():
    model = RemoteSensingVQAModel()
    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        answer, evidence = model._apply_evidence_guard(image, "Is there water in this image?", "no")
    assert answer.startswith("Yes, water is visible")
    assert evidence["evidence_guard_applied"] is True
    assert evidence["answer_status"] == "evidence_corrected"
    assert evidence["visual_metrics"]["water_ratio"] > 0.03


def test_evidence_guard_abstains_on_exact_counts():
    model = RemoteSensingVQAModel()
    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        answer, evidence = model._apply_evidence_guard(image, "How many buildings are visible?", "174")
    assert "cannot reliably determine" in answer
    assert evidence["evidence_guard_applied"] is True
    assert evidence["answer_status"] == "abstained"


def test_evidence_guard_preserves_shape_question():
    model = RemoteSensingVQAModel()
    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        answer, evidence = model._apply_evidence_guard(image, "Is there a circular water area?", "no")
    assert answer == "no"
    assert evidence["evidence_guard_applied"] is False
    assert evidence["answer_status"] == "model"
