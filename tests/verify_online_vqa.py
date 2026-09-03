"""Run VQA smoke checks over downloaded online samples or local fixtures."""
import json
import os
from pathlib import Path

os.environ.setdefault("VQA_USE_FALLBACK", "true")

from backend.models.vqa.model import RemoteSensingVQAModel


ROOT = Path(__file__).resolve().parents[1]
ONLINE = ROOT / "datasets" / "online_samples"
LOCAL = ROOT / "datasets" / "samples"


def test_vqa_samples():
    manifest_path = ONLINE / "manifest.json"
    if manifest_path.exists():
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
        samples = [(ONLINE / record["file"], "Describe the dominant land cover") for record in records]
    else:
        samples = [(LOCAL / "forest_scene.png", "Describe the vegetation"), (LOCAL / "lake_suburb.png", "Is there water present?")]
    model = RemoteSensingVQAModel()
    for image_path, question in samples:
        result = model.run({"image_path": str(image_path), "question": question})
        assert result["answer"].strip()
        assert result["execution_trace"]["inference_mode"] == "fallback"
    print(f"VQA smoke checks passed for {len(samples)} sample(s).")


if __name__ == "__main__":
    test_vqa_samples()
