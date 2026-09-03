"""Comparison script evaluating Base BLIP-VQA, BLIP + RSVQA LoRA, and Fallback.

Runs a curated set of remote sensing queries across representative images to
diagnose and compare model behaviors.
"""
import os
import sys
import time
import torch
from PIL import Image
from transformers import BlipProcessor, BlipForQuestionAnswering
from peft import PeftModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.models.vqa.model import RemoteSensingVQAModel
from backend.config import settings

TEST_CASES = [
    {
        "image": "datasets/samples/lake_suburb.png",
        "question": "Is there a large water body?",
        "expected": "yes / water body present",
        "category": "presence"
    },
    {
        "image": "datasets/samples/lake_suburb.png",
        "question": "Is the area predominantly urban or rural?",
        "expected": "urban / residential area",
        "category": "scene_type"
    },
    {
        "image": "datasets/samples/forest_scene.png",
        "question": "Is vegetation present?",
        "expected": "yes / vegetation visible",
        "category": "presence"
    },
    {
        "image": "datasets/samples/forest_scene.png",
        "question": "What type of land cover is visible?",
        "expected": "forest / dense vegetation",
        "category": "land_cover"
    },
    {
        "image": "datasets/rsvqa/rsvqa_sample_0.png",
        "question": "Is it a rural or an urban area",
        "expected": "rural",
        "category": "rsvqa_domain"
    },
    {
        "image": "datasets/samples/lake_suburb.png",
        "question": "Are roads visible?",
        "expected": "yes / roads visible",
        "category": "presence"
    }
]

def main():
    print("=" * 80)
    print("VQA THREE-WAY INFERENCE COMPARISON BENCHMARK")
    print("=" * 80)

    device = "cuda" if torch.cuda.is_available() else ("mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu")
    print(f"Executing on device: {device}\n")

    adapter_path = settings.VQA_ADAPTER_PATH
    base_model_name = settings.VQA_MODEL_NAME

    # 1. Load Processor
    processor = BlipProcessor.from_pretrained(adapter_path)

    # 2. Load Base Model
    print("Loading Base BLIP-VQA...")
    base_model = BlipForQuestionAnswering.from_pretrained(base_model_name).to(device).eval()

    # 3. Load LoRA Model
    print("Loading BLIP + RSVQA LoRA Adapter...")
    lora_base = BlipForQuestionAnswering.from_pretrained(base_model_name).to(device)
    lora_model = PeftModel.from_pretrained(lora_base, adapter_path).to(device).eval()

    # 4. Initialize Fallback / Specialist Model
    vqa_specialist = RemoteSensingVQAModel()

    print("\nRunning test evaluations...\n")
    results = []

    for idx, case in enumerate(TEST_CASES, 1):
        img_path = case["image"]
        question = case["question"]
        expected = case["expected"]

        img = Image.open(img_path).convert("RGB")
        inputs = processor(images=img, text=question, return_tensors="pt").to(device)

        # Base BLIP inference
        with torch.no_grad():
            out_base = base_model.generate(
                **inputs,
                max_new_tokens=16,
                num_beams=3,
                repetition_penalty=1.15,
                do_sample=False
            )
        ans_base = processor.decode(out_base[0], skip_special_tokens=True).strip()

        # LoRA BLIP inference
        with torch.no_grad():
            out_lora = lora_model.generate(
                **inputs,
                max_new_tokens=16,
                num_beams=3,
                repetition_penalty=1.15,
                do_sample=False
            )
        ans_lora = processor.decode(out_lora[0], skip_special_tokens=True).strip()

        # Fallback spectral inference
        res_fallback = vqa_specialist._run_fallback(img_path, question, time.time())
        ans_fallback = res_fallback["answer"]

        results.append({
            "idx": idx,
            "image": os.path.basename(img_path),
            "question": question,
            "expected": expected,
            "base_blip": ans_base,
            "lora_blip": ans_lora,
            "fallback": ans_fallback
        })

    # Print summary table
    print("-" * 120)
    print(f"{'#':<3} | {'Image':<18} | {'Question':<38} | {'Base BLIP':<15} | {'BLIP+LoRA':<12} | {'Expected'}")
    print("-" * 120)
    for r in results:
        print(f"{r['idx']:<3} | {r['image']:<18} | {r['question']:<38} | {r['base_blip']:<15} | {r['lora_blip']:<12} | {r['expected']}")
    print("-" * 120)

    print("\nDetailed breakdown:")
    for r in results:
        print(f"\n[{r['idx']}] Image: {r['image']} | Question: \"{r['question']}\"")
        print(f"    Expected:  {r['expected']}")
        print(f"    Base BLIP: \"{r['base_blip']}\"")
        print(f"    BLIP+LoRA: \"{r['lora_blip']}\"")
        print(f"    Fallback:  \"{r['fallback']}\"")

if __name__ == "__main__":
    main()
