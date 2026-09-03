"""Comprehensive regression test suite for RSVQA LoRA VQA Inference Pipeline."""
import os
import sys
import tempfile
import pytest
from PIL import Image
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.vqa.model import RemoteSensingVQAModel
from backend.config import settings

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LAKE_IMG = os.path.join(ROOT, "datasets", "samples", "lake_suburb.png")
FOREST_IMG = os.path.join(ROOT, "datasets", "samples", "forest_scene.png")
RSVQA_0_IMG = os.path.join(ROOT, "datasets", "rsvqa", "rsvqa_sample_0.png")


def test_model_and_adapter_loading():
    """Verify that the specialist initializes, identifies the checkpoint, and loads correctly."""
    vqa = RemoteSensingVQAModel()
    assert vqa.name == "RemoteSensingVQA"
    assert vqa.adapter_path == settings.VQA_ADAPTER_PATH

    # Trigger lazy load
    vqa._load_model()
    assert vqa.model is not None
    assert vqa.processor is not None
    assert not vqa.model.training  # Model must be in eval mode
    
    diagnostics = vqa.get_model_diagnostics()
    assert diagnostics["base_model"] == settings.VQA_MODEL_NAME
    assert diagnostics["eval_mode"] is True
    assert diagnostics["is_peft_model"] is True


def test_valid_image_and_question_inference():
    """Verify successful inference on a valid satellite image and natural question."""
    vqa = RemoteSensingVQAModel()
    result = vqa.run({
        "image_path": LAKE_IMG,
        "question": "Is it a rural or an urban area"
    })
    
    assert "answer" in result
    assert len(result["answer"]) > 0
    assert result["evidence"]["inference_mode"] == "model"
    assert result["execution_trace"]["adapter_loaded"] is True
    assert result["execution_trace"]["fallback_active"] is False
    assert result["confidence"] > 0.5


def test_deterministic_inference():
    """Verify that multiple runs with identical inputs produce identical deterministic outputs."""
    vqa = RemoteSensingVQAModel()
    res1 = vqa.run({"image_path": RSVQA_0_IMG, "question": "Is it a rural or an urban area"})
    res2 = vqa.run({"image_path": RSVQA_0_IMG, "question": "Is it a rural or an urban area"})
    
    assert res1["answer"] == res2["answer"]
    assert res1["confidence"] == res2["confidence"]


def test_empty_question_rejection():
    """Verify that an empty question query raises a ValueError."""
    vqa = RemoteSensingVQAModel()
    with pytest.raises(ValueError, match="Question text cannot be empty"):
        vqa.run({"image_path": LAKE_IMG, "question": "   "})


def test_nonexistent_image_rejection():
    """Verify that a missing image path raises FileNotFoundError."""
    vqa = RemoteSensingVQAModel()
    with pytest.raises(FileNotFoundError):
        vqa.run({"image_path": "nonexistent_image.png", "question": "What is visible?"})


def test_multispectral_raster_rejection():
    """Verify that 12-band multispectral rasters are rejected with a clear message."""
    multispectral_path = os.path.join(ROOT, "datasets", "samples", "real_12band_s2.tif")
    if os.path.exists(multispectral_path):
        vqa = RemoteSensingVQAModel()
        with pytest.raises(ValueError, match=r"expects an RGB image, not a raw.*multispectral raster"):
            vqa.run({"image_path": multispectral_path, "question": "What is the land cover?"})


def test_sanity_validation_layer():
    """Verify that the sanity filter detects empty, malformed, or repetitive outputs."""
    with Image.open(LAKE_IMG) as img:
        # 1. Empty answer
        ans, conf, ev = RemoteSensingVQAModel._validate_and_sanitize_output("", "any question", img)
        assert "Unable to determine a reliable answer" in ans
        assert ev["validation_status"] == "unreliable_empty"

        # 2. Pure punctuation
        ans, conf, ev = RemoteSensingVQAModel._validate_and_sanitize_output("...", "any question", img)
        assert "Unable to determine a reliable answer" in ans
        assert ev["validation_status"] == "unreliable_punctuation"

        # 3. Excessive repetition loop
        ans, conf, ev = RemoteSensingVQAModel._validate_and_sanitize_output("water water water water", "any question", img)
        assert "Unable to determine a reliable answer" in ans
        assert ev["validation_status"] == "unreliable_repetition"

        # 4. Valid answer
        ans, conf, ev = RemoteSensingVQAModel._validate_and_sanitize_output("rural area", "any question", img)
        assert ans == "rural area"
        assert ev["validation_status"] == "validated"
        assert conf >= 0.75


def test_fallback_behavior():
    """Verify that explicit fallback mode reports transparent metadata."""
    vqa = RemoteSensingVQAModel()
    vqa.use_fallback = True
    result = vqa.run({
        "image_path": LAKE_IMG,
        "question": "Is there a water body present?"
    })
    
    assert "water" in result["answer"].lower()
    assert result["evidence"]["inference_mode"] == "fallback"
    assert result["execution_trace"]["fallback_active"] is True
    assert result["execution_trace"]["adapter_loaded"] is False


if __name__ == "__main__":
    pytest.main(["-v", __file__])
