"""Download openly hosted earth-observation images for local smoke tests."""
import argparse
import json
from pathlib import Path

import requests
from PIL import Image
from io import BytesIO

API_URL = "https://commons.wikimedia.org/w/api.php"


def download_samples(output_dir: str, count: int, query: str) -> int:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    response = requests.get(API_URL, params={
        "action": "query", "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": count * 3, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 900, "format": "json",
    }, timeout=30)
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {}).values()
    records = []
    for index, page in enumerate(pages):
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        try:
            image_response = requests.get(url, timeout=30)
            image_response.raise_for_status()
            image = Image.open(BytesIO(image_response.content)).convert("RGB")
            filename = f"online_{len(records):02d}.jpg"
            image.save(destination / filename, quality=92)
            records.append({"file": filename, "title": page.get("title"), "source_url": url})
            if len(records) >= count:
                break
        except Exception as exc:
            print(f"Skipping {url}: {exc}")
    (destination / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Downloaded {len(records)} image(s) to {destination}")
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="datasets/online_samples")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--query", default="satellite image earth observation")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")
    raise SystemExit(0 if download_samples(args.output_dir, args.count, args.query) else 1)
