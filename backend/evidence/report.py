"""Self-contained PDF evidence-report generation for API responses."""
import base64
import io
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageFont


def generate_pdf_report(title: str, result: Dict[str, Any]) -> str:
    """Build a compact audit PDF and return it as base64-encoded bytes."""
    page = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default()
    y = 55
    draw.text((55, y), title, fill="black", font=font)
    y += 45
    fields = ("status", "query", "answer", "caption", "summary", "confidence", "route", "job_id", "change_summary")
    for field in fields:
        value = result.get(field)
        if value is None:
            continue
        for line in textwrap.wrap(f"{field}: {value}", width=145):
            draw.text((55, y), line, fill="black", font=font)
            y += 20
        y += 10
    timestamp = datetime.now(timezone.utc).isoformat()
    draw.text((55, y), f"generated_at: {timestamp}", fill="black", font=font)
    y += 30
    trace = result.get("execution_trace", {})
    for line in textwrap.wrap(f"execution_trace: {trace}", width=145):
        draw.text((55, y), line, fill="black", font=font)
        y += 20
    buffer = io.BytesIO()
    page.save(buffer, format="PDF", resolution=150.0)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
