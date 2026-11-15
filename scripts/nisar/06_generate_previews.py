#!/usr/bin/env python3
"""Generate display-only PNG previews from the extracted measurement GeoTIFFs."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont

LOG = logging.getLogger("nisar_preview")
RANGES_DB = {"HH": (-20.0, 10.0), "HV": (-28.0, -4.0)}
TARGETS = (
    ("20261029", "HH"), ("20261029", "HV"),
    ("20261110", "HH"), ("20261110", "HV"),
)


def font(size: int) -> ImageFont.ImageFont:
    for name in ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def make_preview(source: Path, target: Path, date: str, polarization: str) -> None:
    low, high = RANGES_DB[polarization]
    with rasterio.open(source) as src:
        data = src.read(1, out_shape=(max(1, src.height // 3), max(1, src.width // 3)), resampling=rasterio.enums.Resampling.nearest)
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(data)
    scaled = np.clip((np.nan_to_num(db, nan=low) - low) / (high - low), 0, 1)
    image = Image.fromarray(np.uint8(scaled * 255)).convert("RGB")
    canvas = Image.new("RGB", (image.width, image.height + 86), (20, 24, 30))
    canvas.paste(image, (0, 86))
    draw = ImageDraw.Draw(canvas)
    draw.text((18, 12), f"NISAR L2 GCOV | Bengaluru AOI | {polarization}", fill="white", font=font(20))
    draw.text((18, 45), f"Acquisition: {date[:4]}-{date[4:6]}-{date[6:]} | RTC gamma-zero | Display: {low:g} to {high:g} dB", fill=(190, 210, 225), font=font(14))
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, format="PNG", optimize=True)
    LOG.info("Wrote %s", target)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    root = Path(__file__).resolve().parents[2]
    base = root / "datasets" / "processed" / "bengaluru"
    for date, polarization in TARGETS:
        source = base / f"nisar_{polarization.lower()}_{date}.tif"
        if not source.is_file():
            raise FileNotFoundError(source)
        make_preview(source, base / "previews" / f"nisar_{polarization.lower()}_{date}_preview.png", date, polarization)


if __name__ == "__main__":
    main()
