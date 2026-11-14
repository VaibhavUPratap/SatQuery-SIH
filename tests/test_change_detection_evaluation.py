import base64
import json
import sys
import types

import cv2
import numpy as np

from experiments import benchmark_suite


def test_change_evaluation_scores_model_output_mask(tmp_path, monkeypatch):
    predicted = np.zeros((4, 4), dtype=np.uint8)
    predicted[0, 0] = 255
    predicted[1, 1] = 255
    reference = np.zeros((4, 4), dtype=np.uint8)
    reference[0, 0] = 255
    reference[2, 2] = 255
    _, encoded_prediction = cv2.imencode(".png", predicted)

    reference_path = tmp_path / "reference.png"
    assert cv2.imwrite(str(reference_path), reference)
    manifest_path = tmp_path / "change_holdout.jsonl"

    class StubChangeDetectionModel:
        def run(self, _inputs):
            return {"change_mask_b64": base64.b64encode(encoded_prediction).decode("ascii")}

    models_package = types.ModuleType("backend.models")
    models_package.__path__ = []
    change_package = types.ModuleType("backend.models.change_detection")
    change_package.__path__ = []
    model_module = types.ModuleType("backend.models.change_detection.model")
    model_module.ChangeDetectionModel = StubChangeDetectionModel
    monkeypatch.setitem(sys.modules, "backend.models", models_package)
    monkeypatch.setitem(sys.modules, "backend.models.change_detection", change_package)
    monkeypatch.setitem(sys.modules, "backend.models.change_detection.model", model_module)
    monkeypatch.setattr(benchmark_suite, "DATASETS_DIR", str(tmp_path))
    monkeypatch.setattr(benchmark_suite, "PROJECT_DIR", str(tmp_path))
    manifest_path.write_text(json.dumps({
        "id": "sample",
        "t1_path": "t1.png",
        "t2_path": "t2.png",
        "gt_mask_path": "reference.png",
    }) + "\n")

    results = benchmark_suite.evaluate_change_detection()

    assert results["scenarios_evaluated"] == 1
    assert results["mean_pixel_iou"] == 0.3333
    assert results["mean_f1_score"] == 0.5
    assert results["mean_precision"] == 0.5
    assert results["mean_recall"] == 0.5
    assert "independent annotation provenance not verified" in results["reference_provenance"]
