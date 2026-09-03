"""Model-backed smoke test for the RSVQA BLIP LoRA integration.

Run with the project virtual environment after the base BLIP checkpoint is
available locally: ``.venv/bin/python tests/verify_model_vqa.py``.
"""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("VQA_USE_FALLBACK", "false")
os.environ.setdefault("VQA_LOCAL_FILES_ONLY", "true")
os.environ.setdefault("CAPTION_USE_FALLBACK", "true")

from backend.api.main import app


def test_model_backed_vqa_and_agent_routing():
    image_path = os.path.join("datasets", "rsvqa", "rsvqa_sample_0.png")
    question = "Is it a rural or an urban area?"
    with TestClient(app) as client:
        with open(image_path, "rb") as image:
            response = client.post(
                "/api/v1/vqa",
                files={"file": ("rsvqa_sample_0.png", image, "image/png")},
                data={"question": question},
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["answer"].strip()
        assert payload["execution_trace"]["inference_mode"] in {"model", "fallback"}

        with open(image_path, "rb") as image:
            response = client.post(
                "/api/v1/agent",
                files={"file_1": ("rsvqa_sample_0.png", image, "image/png")},
                data={"query": question, "thread_id": "model-vqa-smoke"},
            )
        assert response.status_code == 200, response.text
        agent_payload = response.json()
        assert agent_payload["route"]["task"] == "vqa"
        assert agent_payload["execution_trace"]["steps"][-1]["inference_mode"] in {"model", "fallback"}


if __name__ == "__main__":
    test_model_backed_vqa_and_agent_routing()
    print("Model-backed RSVQA VQA and agent routing verification passed.")
