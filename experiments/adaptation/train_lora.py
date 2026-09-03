"""LoRA adaptation entry point for training on RSVQA-style data."""
import argparse
import json
import random
import re
from pathlib import Path

from PIL import Image


def normalize_answer(raw):
    """Normalize answer text so equivalent labels are treated consistently."""
    if raw is None:
        return ""
    text = str(raw).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .,!?:;\"'[](){}<>")
    if text:
        text = text.replace("’", "'")
        text = text.replace("-", " ")
        text = re.sub(r"\s+", " ", text).strip()
    return text


def split_train_val(records, val_ratio=0.2, seed=42):
    """Return a deterministic train/validation split for small RSVQA datasets."""
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio must be between 0 and 1.")
    if len(records) < 2:
        raise ValueError("At least two records are required for a train/validation split.")
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    split_index = max(1, int(len(shuffled) * (1 - val_ratio)))
    split_index = min(split_index, len(shuffled) - 1)
    return shuffled[:split_index], shuffled[split_index:]


def resolve_image_path(image_value, manifest_path):
    """Resolve paths saved on another machine relative to the manifest directory."""
    image_path = Path(str(image_value)).expanduser()
    if image_path.exists():
        return str(image_path)

    relocated_path = Path(manifest_path).resolve().parent / image_path.name
    if relocated_path.exists():
        return str(relocated_path)
    return str(image_path)


def validate_no_image_overlap(train_records, holdout_records, train_manifest, holdout_manifest):
    """Reject image-level leakage between training and evaluation manifests."""
    train_images = {
        Path(resolve_image_path(record["image"], train_manifest)).resolve()
        for record in train_records
    }
    holdout_images = {
        Path(resolve_image_path(record["image"], holdout_manifest)).resolve()
        for record in holdout_records
    }
    overlap = train_images & holdout_images
    if overlap:
        examples = ", ".join(sorted(path.name for path in overlap)[:3])
        raise ValueError(
            f"Training manifest overlaps the holdout by {len(overlap)} image(s): {examples}. "
            "Use a strict train split with zero image overlap."
        )


def load_training_records(train_manifest, additional_manifests=()):
    """Load and normalize base plus optional supervised training manifests."""
    train_manifest = Path(train_manifest).resolve()
    manifest_paths = [train_manifest, *(Path(path).resolve() for path in additional_manifests)]
    records = []
    required = {"image", "question", "answer"}
    for manifest_path in manifest_paths:
        manifest_records = [
            json.loads(line) for line in manifest_path.read_text().splitlines() if line.strip()
        ]
        for index, record in enumerate(manifest_records):
            missing = required - record.keys()
            if missing:
                raise ValueError(
                    f"Manifest record {index} in {manifest_path} is missing: {sorted(missing)}"
                )
            records.append({
                "image": resolve_image_path(record["image"], manifest_path),
                "question": str(record["question"]).strip(),
                "answer": normalize_answer(record["answer"]),
            })
    return records


def evaluate_model(model, processor, records, device, max_new_tokens=32, num_beams=3, repetition_penalty=1.15, length_penalty=1.0):
    """Run a lightweight validation pass and return accuracy on the provided records."""
    if not records:
        return {"accuracy": 0.0, "count": 0}

    model.eval()
    correct = 0
    with __import__("torch").no_grad():
        for rec in records:
            image = Image.open(rec["image"]).convert("RGB")
            inputs = processor(images=image, text=rec["question"], return_tensors="pt").to(device)
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
                repetition_penalty=repetition_penalty,
                length_penalty=length_penalty,
                do_sample=False,
            )
            pred = normalize_answer(processor.decode(generated[0], skip_special_tokens=True))
            target = normalize_answer(rec["answer"])
            if pred == target:
                correct += 1
    model.train()
    return {"accuracy": round(correct / len(records), 4), "count": len(records), "correct": correct}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--base-model", default="Salesforce/blip-vqa-base")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--max-new-tokens", type=int, default=16)
    parser.add_argument("--num-beams", type=int, default=3)
    parser.add_argument("--repetition-penalty", type=float, default=1.15)
    parser.add_argument("--length-penalty", type=float, default=1.0)
    parser.add_argument(
        "--holdout-jsonl",
        default=None,
        help="Optional holdout manifest used to reject image-level train/evaluation leakage.",
    )
    parser.add_argument(
        "--additional-jsonl",
        action="append",
        default=[],
        help="Optional labeled JSONL manifest(s) to add to the training records.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    train_manifest = Path(args.train_jsonl).resolve()
    records = load_training_records(train_manifest, args.additional_jsonl)
    if not records:
        raise ValueError("The training JSONL contains no records.")

    missing_images = [record["image"] for record in records if not Path(record["image"]).is_file()]
    if missing_images:
        raise FileNotFoundError(
            f"Training manifest contains {len(missing_images)} missing image(s); first: {missing_images[0]}"
        )

    holdout_manifest = Path(args.holdout_jsonl).resolve() if args.holdout_jsonl else None
    if holdout_manifest is None and train_manifest.name == "train.jsonl":
        candidate = train_manifest.with_name("test_holdout.jsonl")
        if candidate.is_file():
            holdout_manifest = candidate

    if holdout_manifest:
        holdout_records = [
            json.loads(line) for line in holdout_manifest.read_text().splitlines() if line.strip()
        ]
        validate_no_image_overlap(records, holdout_records, train_manifest, holdout_manifest)

    train_records, val_records = split_train_val(records, val_ratio=args.val_ratio, seed=args.seed)
    if len(train_records) == 0:
        raise ValueError("Validation split consumed all records; reduce --val-ratio.")

    try:
        import torch
        from torch.utils.data import Dataset, DataLoader
        from peft import LoraConfig, get_peft_model
        from transformers import BlipForQuestionAnswering, BlipProcessor
    except ImportError as exc:
        raise RuntimeError("Install optional training dependencies: pip install peft accelerate datasets") from exc

    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    print("Loading model and processor...")
    processor = BlipProcessor.from_pretrained(args.base_model)
    model = BlipForQuestionAnswering.from_pretrained(args.base_model)

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        target_modules=["query", "value"]
    )
    
    model = get_peft_model(model, lora_config)
    model.to(device)
    model.train()
    
    print(f"PEFT model initialized. Trainable parameters:")
    model.print_trainable_parameters()

    # Custom Dataset class
    class RSVQADataSet(Dataset):
        def __init__(self, data_records):
            self.records = data_records

        def __len__(self):
            return len(self.records)

        def __getitem__(self, idx):
            rec = self.records[idx]
            img_path = rec["image"]
            question = rec["question"]
            answer = rec["answer"]
            
            image = Image.open(img_path).convert("RGB")
            return image, question, answer

    # Collate function to tokenize and batch
    def collate_fn(batch):
        images = [item[0] for item in batch]
        questions = [item[1] for item in batch]
        answers = [item[2] for item in batch]
        
        inputs = processor(images=images, text=questions, return_tensors="pt", padding=True)
        
        labels = processor(text=answers, return_tensors="pt", padding=True).input_ids
        labels[labels == processor.tokenizer.pad_token_id] = -100
        
        inputs["labels"] = labels
        return inputs

    dataset = RSVQADataSet(train_records)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    best_val_accuracy = -1.0

    print("Starting training loop...")
    for epoch in range(args.epochs):
        epoch_loss = 0.0
        model.train()
        for step, batch in enumerate(dataloader):
            optimizer.zero_grad()

            batch_inputs = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch_inputs)
            loss = outputs.loss
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            if (step + 1) % 5 == 0 or step == len(dataloader) - 1:
                print(f"Epoch {epoch+1}/{args.epochs} | Step {step+1}/{len(dataloader)} | Loss: {loss.item():.4f}")

        avg_loss = epoch_loss / len(dataloader)
        print(f"Epoch {epoch+1}/{args.epochs} completed. Average Loss: {avg_loss:.4f}")

        val_metrics = evaluate_model(
            model,
            processor,
            val_records,
            device,
            args.max_new_tokens,
            args.num_beams,
            args.repetition_penalty,
            args.length_penalty,
        )
        print(f"Validation accuracy after epoch {epoch+1}: {val_metrics['accuracy']} ({val_metrics['correct']}/{val_metrics['count']})")

        if val_metrics["accuracy"] > best_val_accuracy:
            best_val_accuracy = val_metrics["accuracy"]
            Path(args.output_dir).mkdir(parents=True, exist_ok=True)
            model.save_pretrained(args.output_dir)
            processor.save_pretrained(args.output_dir)
            Path(args.output_dir, "run_config.json").write_text(json.dumps({**vars(args), "best_val_accuracy": best_val_accuracy}, indent=2))

    if best_val_accuracy < 0:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        model.save_pretrained(args.output_dir)
        processor.save_pretrained(args.output_dir)
        Path(args.output_dir, "run_config.json").write_text(json.dumps({**vars(args), "best_val_accuracy": 0.0}, indent=2))

    if best_val_accuracy < 0:
        raise RuntimeError("Training completed without producing a validated checkpoint.")
    print(f"Best validated adapter saved to {args.output_dir} with accuracy {best_val_accuracy:.4f}.")

if __name__ == "__main__":
    main()
