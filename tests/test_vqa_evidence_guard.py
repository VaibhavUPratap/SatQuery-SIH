from pathlib import Path
from PIL import Image

from backend.models.vqa.model import RemoteSensingVQAModel

ROOT = Path(__file__).resolve().parents[1]


def test_sanity_layer_validates_clean_answer():
    """Verify that clean model predictions pass validation and retain visual spectral metrics."""
    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        answer, confidence, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
            "rural", "Is it a rural or an urban area", image
        )
    assert answer == "rural"
    assert evidence["validation_status"] == "validated"
    assert evidence["visual_metrics"]["water_ratio"] > 0.03
    assert confidence >= 0.75


def test_sanity_layer_catches_empty_and_garbage():
    """Verify that empty, pure punctuation, or repetitive loop outputs return the standard refusal string."""
    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        # Empty output
        ans_empty, conf_empty, ev_empty = RemoteSensingVQAModel._validate_and_sanitize_output(
            "", "What is visible?", image
        )
        assert ans_empty == "Unable to determine a reliable answer from the provided image."
        assert ev_empty["validation_status"] == "unreliable_empty"

        # Pure punctuation output
        ans_punct, conf_punct, ev_punct = RemoteSensingVQAModel._validate_and_sanitize_output(
            "???", "What is visible?", image
        )
        assert ans_punct == "Unable to determine a reliable answer from the provided image."
        assert ev_punct["validation_status"] == "unreliable_punctuation"

        # Repetitive loop output
        ans_loop, conf_loop, ev_loop = RemoteSensingVQAModel._validate_and_sanitize_output(
            "water water water", "What is visible?", image
        )
        assert ans_loop == "Unable to determine a reliable answer from the provided image."
        assert ev_loop["validation_status"] == "unreliable_repetition"


def test_sanity_layer_catches_excessive_length():
    """Verify that runaway generation exceeding length bounds is flagged."""
    long_gibberish = " ".join(["building"] * 30)
    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        answer, confidence, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
            long_gibberish, "How many buildings?", image
        )
    assert answer == "Unable to determine a reliable answer from the provided image."
    assert evidence["validation_status"] == "unreliable_length"


def test_model_answer_canonicalizes_standalone_number_words():
    assert RemoteSensingVQAModel._canonicalize_answer("one") == "1"
    assert RemoteSensingVQAModel._canonicalize_answer("  SEVEN  ") == "7"
    assert RemoteSensingVQAModel._canonicalize_answer("there are one") == "there are one"


def test_fallback_reports_why_model_inference_was_skipped():
    """Verify fallback metadata distinguishes configuration from model failure."""
    image_path = ROOT / "datasets/samples/lake_suburb.png"
    vqa = RemoteSensingVQAModel()
    vqa.use_fallback = True

    configured = vqa.run({"image_path": str(image_path), "question": "What is visible?"})

    assert configured["evidence"]["fallback_reason"] == "configured"
    assert configured["execution_trace"]["fallback_reason"] == "configured"

    vqa = RemoteSensingVQAModel()
    failed = vqa._run_fallback(str(image_path), "What is visible?", 0, error_msg="checkpoint unavailable")

    assert failed["evidence"]["fallback_reason"] == "model_error"
    assert failed["execution_trace"]["fallback_reason"] == "model_error"
