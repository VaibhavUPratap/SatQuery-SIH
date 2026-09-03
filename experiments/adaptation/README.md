# Remote-Sensing VLM Adaptation

Use an RSVQA-style JSONL file with one record per example:

```json
{"image": "/content/data/image.png", "question": "Is water visible?", "answer": "yes"}
```

Run in Colab after installing the optional training dependencies:

```bash
python train_lora.py \
	--train-jsonl datasets/rsvqa/train_split.jsonl \
	--holdout-jsonl datasets/rsvqa/test_holdout.jsonl \
	--output-dir checkpoints/rsvqa-blip-lora
```

Store the resulting adapter outside Git, then set `VQA_ADAPTER_PATH` to its
directory. Record the run in `Docs/training_runs/` before claiming adaptation
or benchmark performance.
