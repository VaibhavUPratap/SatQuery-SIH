from pathlib import Path
import numpy as np
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
    assert evidence["visual_metrics"]["water_region_ratio"] > 0.03
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


def test_sanity_layer_corrects_irrelevant_water_answers_from_strong_evidence():
    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        answer, confidence, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
            "no", "Is there a water region?", image
        )

    assert answer == "Yes, a water region is visible in the image."
    assert confidence == 0.62
    assert evidence["validation_status"] == "corrected_by_visual_evidence"
    assert evidence["raw_answer"] == "no"

    with Image.open(ROOT / "datasets/samples/lake_suburb.png") as image:
        answer, _, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
            "1", "Is there a water region?", image
        )
    assert answer == "Yes, a water region is visible in the image."
    assert evidence["validation_status"] == "corrected_by_visual_evidence"


def test_sanity_layer_corrects_irrelevant_vegetation_answers_from_strong_evidence():
    with Image.open(ROOT / "datasets/samples/forest_scene.png") as image:
        answer, _, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
            "0", "Is vegetation present?", image
        )

    assert answer == "Yes, vegetation is visible in the image."
    assert evidence["validation_status"] == "corrected_by_visual_evidence"


def test_sanity_layer_expands_short_land_cover_label():
    with Image.open(ROOT / "datasets/samples/forest_scene.png") as image:
        answer, confidence, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
            "green", "What is the land coverage?", image
        )

    assert "vegetated land" in answer
    assert "qualitative RGB assessment" in answer
    assert "%" not in answer
    assert confidence == 0.62
    assert evidence["validation_status"] == "corrected_by_visual_evidence"


def test_land_coverage_does_not_call_scattered_blue_pixels_water():
    pixels = np.full((100, 100, 3), (40, 150, 50), dtype=np.uint8)
    pixels[::4, ::4] = (30, 80, 220)
    image = Image.fromarray(pixels)

    answer, _, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
        "green", "What is the land coverage?", image
    )

    assert "vegetated land" in answer
    assert "water" not in answer
    assert evidence["visual_metrics"]["water_region_ratio"] < 0.01


def test_land_coverage_reports_uncertainty_instead_of_generic_error():
    pixels = np.zeros((100, 100, 3), dtype=np.uint8)
    colors = ((211, 47, 91), (71, 189, 211), (217, 173, 49), (151, 73, 197))
    for index, color in enumerate(colors):
        pixels[index % 2 :: 2, (index // 2) % 2 :: 2] = color
    image = Image.fromarray(pixels)

    answer, confidence, evidence = RemoteSensingVQAModel._validate_and_sanitize_output(
        "green", "What is the land coverage?", image
    )

    assert "mixed or other land surface" in answer
    assert "does not provide enough reliable evidence" not in answer
    assert confidence == 0.42
    assert evidence["validation_status"] == "uncertain_rgb_land_cover"


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
