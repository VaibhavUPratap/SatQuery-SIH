"""Internal helper utilities for SatQuery AI PDF report generation.

All helpers accept an fpdf.FPDF instance as their first argument and operate
on its current cursor position, leaving it ready for the next content block.
"""

from __future__ import annotations

import base64
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Colour constants  (RGB tuples)
# ---------------------------------------------------------------------------
C_NAVY = (11, 36, 71)           # #0B2447 - header bands, table headers
C_BLUE = (21, 101, 192)         # #1565C0 - accent lines
C_SECTION_BG = (232, 238, 247)  # #E8EEF7 - section title backgrounds
C_BODY = (26, 26, 26)           # #1A1A1A - primary body text
C_MUTED = (107, 114, 128)       # #6B7280 - secondary / caption text
C_WHITE = (255, 255, 255)
C_LIGHT_BORDER = (210, 218, 230)
C_SUCCESS_GREEN = (34, 139, 34)
C_WARN_AMBER = (217, 119, 6)
C_ERROR_RED = (185, 28, 28)


# ---------------------------------------------------------------------------
# Image utilities
# ---------------------------------------------------------------------------

def decode_b64_to_tempfile(b64_string: str) -> Optional[str]:
    """Decode a base64 PNG/JPEG string to a temp file. Returns path or None."""
    if not b64_string:
        return None
    try:
        data = base64.b64decode(b64_string)
        suffix = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".png"
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="satquery_pdf_img_")
        os.close(fd)
        with open(path, "wb") as fh:
            fh.write(data)
        return path
    except Exception:
        return None


def insert_image_safe(
    pdf,
    b64_string: str,
    max_w: float,
    max_h: float,
    caption: str = "",
    caption_color: tuple = C_MUTED,
) -> float:
    """Insert an image from base64, preserving aspect ratio within bounds.

    Returns vertical space consumed (mm). Image is centred horizontally.
    """
    path = decode_b64_to_tempfile(b64_string)
    if not path:
        return 0.0
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            iw, ih = im.size
        scale = min(max_w / iw, max_h / ih)
        disp_w = iw * scale
        disp_h = ih * scale

        x_offset = pdf.l_margin + (max_w - disp_w) / 2.0
        y_start = pdf.get_y()

        if y_start + disp_h > pdf.h - pdf.b_margin - 5:
            pdf.add_page()
            y_start = pdf.get_y()

        pdf.image(path, x=x_offset, y=y_start, w=disp_w, h=disp_h)
        pdf.set_y(y_start + disp_h + 1)
        consumed = disp_h + 1

        if caption:
            pdf.set_font("Helvetica", "I", 7.5)
            pdf.set_text_color(*caption_color)
            usable = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.cell(usable, 4, caption, align="C", new_x="LMARGIN", new_y="NEXT")
            consumed += 5

        return consumed
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Section title
# ---------------------------------------------------------------------------

def section_title(pdf, text: str, top_gap: float = 4.0) -> None:
    """Draw a shaded section heading and advance the cursor."""
    if top_gap > 0:
        pdf.ln(top_gap)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_fill_color(*C_SECTION_BG)
    pdf.set_text_color(*C_NAVY)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(usable, 7, f"  {text}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*C_BLUE)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + usable, pdf.get_y())
    pdf.ln(2)
    pdf.set_text_color(*C_BODY)
    pdf.set_line_width(0.2)


# ---------------------------------------------------------------------------
# Key-value table
# ---------------------------------------------------------------------------

def kv_table(
    pdf,
    rows: Sequence[Tuple[str, str]],
    col_widths: Optional[Tuple[float, float]] = None,
) -> None:
    """Render a two-column label/value table."""
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    if col_widths is None:
        col_widths = (usable * 0.36, usable * 0.64)
    label_w, value_w = col_widths
    row_h = 6.0

    for i, (label, value) in enumerate(rows):
        y = pdf.get_y()
        # Check page overflow before each row
        if y + row_h > pdf.h - pdf.b_margin - 5:
            pdf.add_page()
            y = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(246, 249, 252)
            pdf.rect(pdf.l_margin, y, usable, row_h, style="F")
        pdf.set_draw_color(*C_LIGHT_BORDER)
        pdf.set_line_width(0.1)
        pdf.rect(pdf.l_margin, y, usable, row_h)

        pdf.set_xy(pdf.l_margin, y)
        pdf.set_text_color(*C_MUTED)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(label_w, row_h, f"  {label}", border=0)

        pdf.set_text_color(*C_BODY)
        pdf.set_font("Helvetica", "", 8.5)
        val_str = str(value) if value is not None else "\u2014"
        if len(val_str) > 120:
            val_str = val_str[:117] + "\u2026"
        pdf.cell(value_w, row_h, val_str, border=0, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)


# ---------------------------------------------------------------------------
# Confidence bar
# ---------------------------------------------------------------------------

def draw_confidence_bar(
    pdf,
    confidence: float,
    label: str = "Confidence",
    bar_w: float = 80.0,
    bar_h: float = 5.0,
) -> None:
    """Draw a horizontal filled confidence bar with percentage label."""
    pct = max(0.0, min(1.0, float(confidence)))
    filled = bar_w * pct
    bar_color = C_SUCCESS_GREEN if pct >= 0.80 else (C_WARN_AMBER if pct >= 0.60 else C_ERROR_RED)

    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(220, 226, 234)
    pdf.rect(x, y, bar_w, bar_h, style="F")
    if filled > 0:
        pdf.set_fill_color(*bar_color)
        pdf.rect(x, y, filled, bar_h, style="F")
    pdf.set_draw_color(*C_LIGHT_BORDER)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, bar_w, bar_h)

    pdf.set_xy(x + bar_w + 3, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*C_BODY)
    pdf.cell(30, bar_h, f"{pct * 100:.1f}%")
    pdf.set_xy(x + bar_w + 33, y)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(0, bar_h, label)
    pdf.ln(bar_h + 4)


# ---------------------------------------------------------------------------
# Pipeline timeline
# ---------------------------------------------------------------------------

def pipeline_timeline(pdf, steps: List[str], statuses: Optional[List[str]] = None) -> None:
    """Render a clean numbered vertical pipeline timeline."""
    step_h = 10.0
    dot_r = 2.5
    line_x = pdf.l_margin + 12.0
    text_x = line_x + 8.0
    usable_text = pdf.w - pdf.l_margin - pdf.r_margin - (text_x - pdf.l_margin)

    for i, step in enumerate(steps):
        if pdf.get_y() + step_h > pdf.h - pdf.b_margin - 5:
            pdf.add_page()
        y_top = pdf.get_y()
        y_center = y_top + step_h / 2

        if i < len(steps) - 1:
            pdf.set_draw_color(*C_LIGHT_BORDER)
            pdf.set_line_width(0.4)
            pdf.line(line_x, y_center + dot_r, line_x, y_top + step_h)

        status = (statuses[i] if statuses and i < len(statuses) else "passed").lower()
        dot_color = C_BLUE if status == "passed" else (C_ERROR_RED if status == "failed" else C_MUTED)
        pdf.set_fill_color(*dot_color)
        pdf.ellipse(line_x - dot_r, y_center - dot_r, dot_r * 2, dot_r * 2, style="F")

        pdf.set_xy(pdf.l_margin, y_top)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(12, step_h, str(i + 1), align="C")

        pdf.set_xy(text_x, y_top)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*C_BODY)
        pdf.cell(usable_text, step_h, step, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)


# ---------------------------------------------------------------------------
# Body text
# ---------------------------------------------------------------------------

def body_text(pdf, text: str, line_height: float = 5.5) -> None:
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_BODY)
    pdf.multi_cell(usable, line_height, str(text) if text else "\u2014", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


# ---------------------------------------------------------------------------
# Bounding box table
# ---------------------------------------------------------------------------

def bounding_box_table(pdf, boxes: List[Any]) -> None:
    """Render detected bounding boxes as a structured table."""
    if not boxes:
        body_text(pdf, "No bounding boxes detected for this query.")
        return

    usable = pdf.w - pdf.l_margin - pdf.r_margin
    widths = [10, usable * 0.24, usable * 0.50, usable * 0.18]
    headers = ["#", "Class / Label", "Coordinates  [ymin, xmin, ymax, xmax]", "Area (px\u00b2)"]

    pdf.set_fill_color(*C_NAVY)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6.5, h, fill=True, border=0)
    pdf.ln()

    pdf.set_text_color(*C_BODY)
    for idx, box in enumerate(boxes[:20]):
        if pdf.get_y() + 7 > pdf.h - pdf.b_margin - 5:
            pdf.add_page()
        fill = idx % 2 == 0
        if fill:
            pdf.set_fill_color(246, 249, 252)

        if isinstance(box, dict):
            label = str(box.get("class", "\u2014"))
            coords = box.get("coordinates", box.get("box", []))
        elif isinstance(box, (list, tuple)) and len(box) == 4:
            label, coords = "detected", list(box)
        else:
            label, coords = str(box), []

        coord_str = str(coords) if coords else "\u2014"
        area = "\u2014"
        if coords and len(coords) == 4:
            try:
                ymin, xmin, ymax, xmax = [int(v) for v in coords]
                area = f"{(ymax - ymin) * (xmax - xmin):,}"
            except Exception:
                pass

        pdf.set_font("Helvetica", "", 8)
        for val, w in zip([str(idx + 1), label, coord_str, area], widths):
            pdf.cell(w, 6, val[:70], fill=fill, border=0)
        pdf.ln()

    pdf.ln(2)
