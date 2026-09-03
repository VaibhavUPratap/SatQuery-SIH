import os
import sys
import logging
import json
import argparse
from PIL import Image

# Add workspace directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("satquery.datasets.real")

def fetch_samples(count=50, split="validation", output_dir=None):
    try:
        from datasets import load_dataset
        logger.info("Loading dmarsili/RSVQA-LR-2k dataset from HuggingFace...")
        dataset = load_dataset("dmarsili/RSVQA-LR-2k", split=split, streaming=True)
        
        # Get 50 samples
        iterator = iter(dataset)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        rsvqa_dir = output_dir or os.path.join(base_dir, "rsvqa")
        os.makedirs(rsvqa_dir, exist_ok=True)
        
        logger.info("Extracting sample images and QA pairs...")
        samples_metadata = []
        jsonl_lines = []
        
        for idx in range(count):
            try:
                sample = next(iterator)
                img = sample.get("image")
                question = sample.get("question", "What is visible in the image?")
                answer = sample.get("answer", "")
                
                img_name = f"rsvqa_sample_{idx}.png"
                img_path = os.path.abspath(os.path.join(rsvqa_dir, img_name))
                
                # Save PIL image
                if isinstance(img, Image.Image):
                    img.save(img_path)
                else:
                    logger.warning(f"Image type: {type(img)}")
                    continue
                    
                samples_metadata.append({
                    "id": f"rsvqa_{idx}",
                    "image_name": img_name,
                    "question": question,
                    "answer": answer
                })
                
                jsonl_lines.append(json.dumps({
                    "image": img_path,
                    "question": question,
                    "answer": answer
                }))
                
                if idx < 3:
                    logger.info(f"Saved real RSVQA image to {img_path}")
                    logger.info(f"  - Q: {question}")
                    logger.info(f"  - A: {answer}")
            except StopIteration:
                logger.info(f"Reached end of dataset iteration at index {idx}.")
                break
                
        # Write metadata file
        with open(os.path.join(rsvqa_dir, "metadata.json"), "w") as f:
            json.dump(samples_metadata, f, indent=2)
            
        # Keep evaluation images out of the training manifest. The first 40
        # records are the training split and the remaining records are held out.
        train_count = min(40, len(samples_metadata))
        jsonl_path = os.path.join(rsvqa_dir, "train.jsonl")
        with open(jsonl_path, "w") as f:
            train_lines = [json.dumps({
                "image": os.path.join(rsvqa_dir, item["image_name"]),
                "question": item["question"],
                "answer": item["answer"],
            }) for item in samples_metadata[:train_count]]
            f.write("\n".join(train_lines) + "\n")

        holdout_path = os.path.join(rsvqa_dir, "test_holdout.jsonl")
        with open(holdout_path, "w") as f:
            holdout_lines = [json.dumps({
                "image": os.path.join(rsvqa_dir, item["image_name"]),
                "question": item["question"],
                "target": item["answer"],
                "split": "strictly_held_out",
            }) for item in samples_metadata[train_count:]]
            f.write("\n".join(holdout_lines) + "\n")
            
        logger.info(
            f"Successfully fetched RSVQA manifests: {train_count} train and "
            f"{len(samples_metadata) - train_count} held out"
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch real RSVQA data: {str(e)}")
        logger.info("Fallback: Proceeding with local offline generated dataset.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch real RSVQA image/Q&A records.")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--split", default="validation")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")
    fetch_samples(count=args.count, split=args.split, output_dir=args.output_dir)
