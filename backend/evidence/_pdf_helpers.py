"""Internal helper utilities for SatQuery AI PDF report generation.

Provides robust Latin-1 text sanitization, aspect-ratio-preserving image insertion
(for single and side-by-side multi-modal layouts), styled tables, KPI badges,
confidence bars, and execution DAG pipeline flowcharts.
"""

from __future__ import annotations

import base64
import io
import os
import tempfile
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# ---------------------------------------------------------------------------
# Color constants (RGB tuples)
# ---------------------------------------------------------------------------
C_NAVY = (11, 36, 71)             # #0B2447 - Primary dark navy
C_BLUE = (21, 101, 192)           # #1565C0 - Accent blue
C_LIGHT_BLUE = (227, 242, 253)    # #E3F2FD - Soft blue background
C_SECTION_BG = (235, 241, 250)    # #EBF1FA - Section banner fill
C_SLATE_BG = (244, 247, 251)      # #F4F7FB - Card / Table fill
C_ZEBRA = (250, 252, 255)         # #FAFCFF - Alternate table row
C_BODY = (33, 37, 41)             # #212529 - Charcoal body text
C_MUTED = (108, 117, 125)         # #6C757D - Muted caption text
C_WHITE = (255, 255, 255)
C_LIGHT_BORDER = (218, 224, 233)  # #DAE0E9 - Border line
C_CARD_BORDER = (195, 207, 224)
C_SUCCESS_GREEN = (22, 130, 70)   # #168246 - Green indicator
C_WARN_AMBER = (217, 119, 6)      # #D97706 - Amber indicator
C_ERROR_RED = (185, 28, 28)       # #B91C1C - Red indicator


# ---------------------------------------------------------------------------
# Text sanitization (guarantees zero FPDFUnicodeEncodingException)
# ---------------------------------------------------------------------------

_UNICODE_REPLACEMENTS = {
    "\u203a": ">",
    "\u2039": "<",
    "\u2192": "->",
    "\u2190": "<-",
    "\u2193": "v",
    "\u2191": "^",
    "\u21d2": "=>",
    "\u2229": "&",
    "\u00b2": "^2",
    "\u00b3": "^3",
    "\u2022": "*",
    "\u00b7": "*",
    "\u25cf": "*",
    "\u2014": " - ",
    "\u2013": "-",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2026": "...",
    "\u2713": "[OK]",
    "\u2714": "[OK]",
    "\u2717": "[X]",
    "\u2718": "[X]",
    "\u00b0": " deg",
    "\u00b1": "+/-",
    "\u00d7": "x",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2260": "!=",
    "\u2248": "~=",
}


def clean_text(text: Any) -> str:
    """Sanitize text to guarantee compatibility with Latin-1 FPDF core fonts."""
    if text is None:
        return ""
    s = str(text)
    for uni_char, rep in _UNICODE_REPLACEMENTS.items():
        if uni_char in s:
            s = s.replace(uni_char, rep)

    # Normalize unicode to NFKD decomposed form
    s = unicodedata.normalize("NFKD", s)

    # Encode with latin-1 ignoring unsupported characters, then decode
    return s.encode("latin-1", "replace").decode("latin-1")


# ---------------------------------------------------------------------------
# Image utilities & Aspect-Ratio-Preserving Insertion
# ---------------------------------------------------------------------------

def _load_image_to_pil(img_src: Union[str, bytes]) -> Optional[Any]:
    """Load image from base64 string, byte stream, or local file path to a PIL RGB Image."""
    if not img_src:
        return None
    try:
        from PIL import Image as PILImage

        # 1. Byte stream
        if isinstance(img_src, bytes):
            im = PILImage.open(io.BytesIO(img_src))
            return im.convert("RGB")

        if not isinstance(img_src, str):
            return None

        # 2. Base64 data URI or raw base64 string
        b64_str = img_src
        if "," in b64_str and "base64" in b64_str:
            b64_str = b64_str.split(",", 1)[1]

        # Check if it's a valid existing file path first
        if os.path.exists(img_src) and os.path.isfile(img_src):
            ext = os.path.splitext(img_src)[1].lower()
            if ext in {".tif", ".tiff"}:
                # Handle GeoTIFF / Multi-spectral
                try:
                    import numpy as np
                    im = PILImage.open(img_src)
                    arr = np.array(im)
                    if arr.ndim == 3 and arr.shape[2] >= 3:
                        rgb = arr[:, :, :3]
                    elif arr.ndim == 2:
                        rgb = np.stack([arr] * 3, axis=-1)
                    else:
                        rgb = arr
                    # Normalize to 0-255 uint8
                    if rgb.dtype != np.uint8:
                        p2, p98 = np.percentile(rgb, 2), np.percentile(rgb, 98)
                        if p98 > p2:
                            rgb = np.clip((rgb - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                        else:
                            rgb = np.clip(rgb, 0, 255).astype(np.uint8)
                    return PILImage.fromarray(rgb)
                except Exception:
                    pass

            im = PILImage.open(img_src)
            return im.convert("RGB")

        # Attempt Base64 decode
        try:
            raw_data = base64.b64decode(b64_str)
            im = PILImage.open(io.BytesIO(raw_data))
            return im.convert("RGB")
        except Exception:
            return None

    except Exception:
        return None


def insert_image_safe(
    pdf,
    img_source: Union[str, bytes],
    max_w: float,
    max_h: float,
    caption: str = "",
    caption_color: tuple = C_MUTED,
    border: bool = True,
) -> float:
    """Insert an image into the PDF, strictly preserving aspect ratio within bounds.

    Returns the vertical space consumed (in mm). The image is horizontally centered.
    """
    im = _load_image_to_pil(img_source)
    if im is None:
        return 0.0

    temp_path = None
    try:
        iw, ih = im.size
        scale = min(max_w / iw, max_h / ih)
        disp_w = iw * scale
        disp_h = ih * scale

        # Save to temporary PNG file for FPDF
        fd, temp_path = tempfile.mkstemp(suffix=".png", prefix="satquery_img_")
        os.close(fd)
        im.save(temp_path, format="PNG")

        x_offset = pdf.l_margin + (max_w - disp_w) / 2.0
        y_start = pdf.get_y()

        # Check if image fits on current page
        if y_start + disp_h + (6 if caption else 2) > pdf.h - pdf.b_margin:
            pdf.add_page()
            y_start = pdf.get_y()
            x_offset = pdf.l_margin + (max_w - disp_w) / 2.0

        # Draw image
        pdf.image(temp_path, x=x_offset, y=y_start, w=disp_w, h=disp_h)

        # Draw subtle border
        if border:
            pdf.set_draw_color(*C_CARD_BORDER)
            pdf.set_line_width(0.2)
            pdf.rect(x_offset, y_start, disp_w, disp_h)

        consumed = disp_h + 1.5
        pdf.set_y(y_start + disp_h + 1.5)

        # Render caption
        if caption:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*caption_color)
            usable = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.cell(usable, 4.5, clean_text(caption), align="C", new_x="LMARGIN", new_y="NEXT")
            consumed += 5.5

        return consumed
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def insert_dual_images_side_by_side(
    pdf,
    img1_src: Union[str, bytes],
    img2_src: Union[str, bytes],
    label1: str = "Primary Image",
    label2: str = "Secondary Image",
    max_h: float = 62.0,
) -> float:
    """Render two images side-by-side (for Optical+SAR or Change Detection pairs).

    Returns vertical space consumed (in mm).
    """
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    gap = 6.0
    col_w = (usable_w - gap) / 2.0

    im1 = _load_image_to_pil(img1_src)
    im2 = _load_image_to_pil(img2_src)

    if not im1 and not im2:
        return 0.0

    temp_path1, temp_path2 = None, None
    try:
        y_start = pdf.get_y()
        if y_start + max_h + 15 > pdf.h - pdf.b_margin:
            pdf.add_page()
            y_start = pdf.get_y()

        consumed_h = 0.0

        # Render Left Column (Image 1)
        x1 = pdf.l_margin
        pdf.set_xy(x1, y_start)
        pdf.set_fill_color(*C_NAVY)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w, 5.5, f"  {clean_text(label1)}", fill=True, border=0)
        
        if im1:
            fd1, temp_path1 = tempfile.mkstemp(suffix=".png", prefix="sq_opt_")
            os.close(fd1)
            im1.save(temp_path1, format="PNG")
            w1, h1 = im1.size
            scale1 = min(col_w / w1, max_h / h1)
            dw1, dh1 = w1 * scale1, h1 * scale1
            img_x1 = x1 + (col_w - dw1) / 2.0
            img_y1 = y_start + 6.5
            pdf.image(temp_path1, x=img_x1, y=img_y1, w=dw1, h=dh1)
            pdf.set_draw_color(*C_CARD_BORDER)
            pdf.set_line_width(0.2)
            pdf.rect(img_x1, img_y1, dw1, dh1)
            consumed_h = max(consumed_h, 6.5 + dh1)

        # Render Right Column (Image 2)
        x2 = pdf.l_margin + col_w + gap
        pdf.set_xy(x2, y_start)
        pdf.set_fill_color(*C_NAVY)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w, 5.5, f"  {clean_text(label2)}", fill=True, border=0)

        if im2:
            fd2, temp_path2 = tempfile.mkstemp(suffix=".png", prefix="sq_sar_")
            os.close(fd2)
            im2.save(temp_path2, format="PNG")
            w2, h2 = im2.size
            scale2 = min(col_w / w2, max_h / h2)
            dw2, dh2 = w2 * scale2, h2 * scale2
            img_x2 = x2 + (col_w - dw2) / 2.0
            img_y2 = y_start + 6.5
            pdf.image(temp_path2, x=img_x2, y=img_y2, w=dw2, h=dh2)
            pdf.set_draw_color(*C_CARD_BORDER)
            pdf.set_line_width(0.2)
            pdf.rect(img_x2, img_y2, dw2, dh2)
            consumed_h = max(consumed_h, 6.5 + dh2)

        pdf.set_y(y_start + consumed_h + 3.0)
        return consumed_h + 3.0

    finally:
        for p in (temp_path1, temp_path2):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Section Titles & Callout Cards
# ---------------------------------------------------------------------------

def section_title(pdf, title: str, top_gap: float = 3.5, subtitle: str = "") -> None:
    """Draw a styled section heading banner with blue accent band."""
    if top_gap > 0:
        pdf.ln(top_gap)
    usable = pdf.w - pdf.l_margin - pdf.r_margin

    y = pdf.get_y()
    # Check page overflow
    if y + 10 > pdf.h - pdf.b_margin:
        pdf.add_page()
        y = pdf.get_y()

    pdf.set_fill_color(*C_SECTION_BG)
    pdf.rect(pdf.l_margin, y, usable, 7.0, style="F")

    # Blue accent bar on the left
    pdf.set_fill_color(*C_BLUE)
    pdf.rect(pdf.l_margin, y, 3.0, 7.0, style="F")

    pdf.set_xy(pdf.l_margin + 4.5, y + 1.0)
    pdf.set_text_color(*C_NAVY)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(usable - 6.0, 5.0, clean_text(title), border=0)

    pdf.set_y(y + 8.5)
    pdf.set_text_color(*C_BODY)


def callout_card(
    pdf,
    label: str,
    text: str,
    bg_color: tuple = C_SLATE_BG,
    accent_color: tuple = C_BLUE,
    min_h: float = 14.0,
) -> None:
    """Draw a rounded framed callout container with bold label and multi-line body text."""
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    clean_body = clean_text(text) or "None"

    # Measure multi_cell height
    pdf.set_font("Helvetica", "", 9)
    # Estimate lines roughly
    line_count = max(1, len(clean_body) // 95 + 1)
    card_h = max(min_h, 6.5 + line_count * 4.8 + 3.0)

    y = pdf.get_y()
    if y + card_h > pdf.h - pdf.b_margin:
        pdf.add_page()
        y = pdf.get_y()

    # Background card
    pdf.set_fill_color(*bg_color)
    pdf.rect(pdf.l_margin, y, usable, card_h, style="F")

    # Accent left border
    pdf.set_fill_color(*accent_color)
    pdf.rect(pdf.l_margin, y, 3.5, card_h, style="F")

    # Border frame
    pdf.set_draw_color(*C_CARD_BORDER)
    pdf.set_line_width(0.2)
    pdf.rect(pdf.l_margin, y, usable, card_h)

    # Label
    pdf.set_xy(pdf.l_margin + 5.5, y + 2.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*accent_color)
    pdf.cell(usable - 10, 4.0, clean_text(label).upper(), border=0)

    # Body
    pdf.set_xy(pdf.l_margin + 5.5, y + 7.0)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*C_BODY)
    pdf.multi_cell(usable - 10, 4.8, clean_body, border=0)

    pdf.set_y(y + card_h + 2.5)


# ---------------------------------------------------------------------------
# Structured Key-Value & Multi-Column Tables
# ---------------------------------------------------------------------------

def kv_table(
    pdf,
    rows: Sequence[Tuple[str, Any]],
    col_widths: Optional[Tuple[float, float]] = None,
    row_h: float = 5.8,
) -> None:
    """Render a clean 2-column key-value table with zebra striping and borders."""
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    if col_widths is None:
        col_widths = (usable * 0.35, usable * 0.65)
    label_w, value_w = col_widths

    for i, (label, value) in enumerate(rows):
        y = pdf.get_y()
        if y + row_h > pdf.h - pdf.b_margin:
            pdf.add_page()
            y = pdf.get_y()

        # Alternate row fill
        fill_color = C_ZEBRA if i % 2 == 0 else C_WHITE
        pdf.set_fill_color(*fill_color)
        pdf.rect(pdf.l_margin, y, usable, row_h, style="F")

        # Row border
        pdf.set_draw_color(*C_LIGHT_BORDER)
        pdf.set_line_width(0.15)
        pdf.rect(pdf.l_margin, y, usable, row_h)

        # Label cell
        pdf.set_xy(pdf.l_margin, y)
        pdf.set_text_color(*C_NAVY)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(label_w, row_h, f"  {clean_text(label)}", border=0)

        # Value cell
        pdf.set_text_color(*C_BODY)
        pdf.set_font("Helvetica", "", 8)
        val_str = clean_text(value) if value is not None else "-"
        if len(val_str) > 115:
            val_str = val_str[:112] + "..."
        pdf.cell(value_w, row_h, val_str, border=0, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(1.5)


def two_column_kv_tables(
    pdf,
    rows1: Sequence[Tuple[str, Any]],
    title1: str,
    rows2: Sequence[Tuple[str, Any]],
    title2: str,
    row_h: float = 5.5,
) -> None:
    """Render two side-by-side metadata tables (e.g. Optical on Left, SAR on Right)."""
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    gap = 6.0
    col_w = (usable_w - gap) / 2.0
    lbl_w = col_w * 0.42
    val_w = col_w * 0.58

    max_rows = max(len(rows1), len(rows2))
    table_h = 6.0 + max_rows * row_h + 2.0

    y_start = pdf.get_y()
    if y_start + table_h > pdf.h - pdf.b_margin:
        pdf.add_page()
        y_start = pdf.get_y()

    # Left Title
    x1 = pdf.l_margin
    pdf.set_xy(x1, y_start)
    pdf.set_fill_color(*C_SECTION_BG)
    pdf.set_text_color(*C_NAVY)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(col_w, 6.0, f"  {clean_text(title1)}", fill=True, border=0)

    # Right Title
    x2 = pdf.l_margin + col_w + gap
    pdf.set_xy(x2, y_start)
    pdf.cell(col_w, 6.0, f"  {clean_text(title2)}", fill=True, border=0)

    # Render Rows
    for r in range(max_rows):
        y_row = y_start + 6.5 + r * row_h
        fill = C_ZEBRA if r % 2 == 0 else C_WHITE

        # Left Column Row
        if r < len(rows1):
            k1, v1 = rows1[r]
            pdf.set_fill_color(*fill)
            pdf.rect(x1, y_row, col_w, row_h, style="F")
            pdf.set_draw_color(*C_LIGHT_BORDER)
            pdf.rect(x1, y_row, col_w, row_h)

            pdf.set_xy(x1, y_row)
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_text_color(*C_NAVY)
            pdf.cell(lbl_w, row_h, f" {clean_text(k1)}", border=0)

            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(*C_BODY)
            v_str1 = clean_text(v1)
            pdf.cell(val_w, row_h, v_str1[:40], border=0)

        # Right Column Row
        if r < len(rows2):
            k2, v2 = rows2[r]
            pdf.set_fill_color(*fill)
            pdf.rect(x2, y_row, col_w, row_h, style="F")
            pdf.set_draw_color(*C_LIGHT_BORDER)
            pdf.rect(x2, y_row, col_w, row_h)

            pdf.set_xy(x2, y_row)
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_text_color(*C_NAVY)
            pdf.cell(lbl_w, row_h, f" {clean_text(k2)}", border=0)

            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(*C_BODY)
            v_str2 = clean_text(v2)
            pdf.cell(val_w, row_h, v_str2[:40], border=0)

    pdf.set_y(y_start + table_h + 1.5)


def styled_data_table(
    pdf,
    headers: List[str],
    rows: List[List[Any]],
    col_widths: Optional[List[float]] = None,
    row_h: float = 5.5,
) -> None:
    """Render a generic multi-column data table with dark header and zebra striping."""
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    if not col_widths:
        w_each = usable / len(headers)
        col_widths = [w_each] * len(headers)

    y = pdf.get_y()
    if y + 8.0 + len(rows) * row_h > pdf.h - pdf.b_margin:
        pdf.add_page()
        y = pdf.get_y()

    # Header Row
    pdf.set_fill_color(*C_NAVY)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(headers, col_widths):
        pdf.cell(w, 6.0, f" {clean_text(h)}", fill=True, border=0)
    pdf.ln()

    # Data Rows
    for idx, row in enumerate(rows):
        y_cur = pdf.get_y()
        if y_cur + row_h > pdf.h - pdf.b_margin:
            pdf.add_page()
            y_cur = pdf.get_y()

        fill = C_ZEBRA if idx % 2 == 0 else C_WHITE
        pdf.set_fill_color(*fill)
        pdf.set_draw_color(*C_LIGHT_BORDER)
        pdf.set_line_width(0.15)
        pdf.rect(pdf.l_margin, y_cur, usable, row_h, style="FD")

        pdf.set_text_color(*C_BODY)
        pdf.set_font("Helvetica", "", 7.5)
        for val, w in zip(row, col_widths):
            pdf.cell(w, row_h, f" {clean_text(val)[:65]}", border=0)
        pdf.ln()

    pdf.ln(2.0)


# ---------------------------------------------------------------------------
# Bounding Box Table (Page 4 Evidence)
# ---------------------------------------------------------------------------

def bounding_box_table(pdf, boxes: List[Any]) -> None:
    """Render detected bounding boxes in a clean table format."""
    if not boxes:
        body_text(pdf, "No discrete bounding boxes or ROI detections generated for this scene.")
        return

    usable = pdf.w - pdf.l_margin - pdf.r_margin
    widths = [12.0, usable * 0.28, usable * 0.42, usable * 0.18]
    headers = ["#", "Class / Feature Label", "Coordinates [ymin, xmin, ymax, xmax]", "Area (px^2)"]

    rows_data = []
    for idx, box in enumerate(boxes[:15]):
        if isinstance(box, dict):
            label = str(box.get("class") or box.get("label") or "detected_region")
            coords = box.get("coordinates") or box.get("box") or []
        elif isinstance(box, (list, tuple)) and len(box) == 4:
            label, coords = "detected_region", list(box)
        else:
            label, coords = str(box), []

        coord_str = str(coords) if coords else "-"
        area_str = "-"
        if coords and len(coords) == 4:
            try:
                ymin, xmin, ymax, xmax = [int(v) for v in coords]
                area_str = f"{(ymax - ymin) * (xmax - xmin):,}"
            except Exception:
                pass

        rows_data.append([str(idx + 1), label, coord_str, area_str])

    styled_data_table(pdf, headers, rows_data, widths)


# ---------------------------------------------------------------------------
# Confidence Bar & KPI Badges (Page 1 Executive Summary)
# ---------------------------------------------------------------------------

def draw_confidence_bar(
    pdf,
    confidence: float,
    label: str = "Confidence Metric",
    bar_w: float = 85.0,
    bar_h: float = 5.5,
) -> None:
    """Draw a horizontal filled confidence score indicator."""
    pct = max(0.0, min(1.0, float(confidence)))
    filled_w = bar_w * pct

    bar_color = C_SUCCESS_GREEN if pct >= 0.80 else (C_WARN_AMBER if pct >= 0.60 else C_ERROR_RED)

    x, y = pdf.l_margin, pdf.get_y()
    if y + bar_h + 4.0 > pdf.h - pdf.b_margin:
        pdf.add_page()
        x, y = pdf.l_margin, pdf.get_y()

    # Background track
    pdf.set_fill_color(225, 232, 240)
    pdf.rect(x, y, bar_w, bar_h, style="F")

    # Filled progress
    if filled_w > 0:
        pdf.set_fill_color(*bar_color)
        pdf.rect(x, y, filled_w, bar_h, style="F")

    # Track border
    pdf.set_draw_color(*C_CARD_BORDER)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, bar_w, bar_h)

    # Percentage label
    pdf.set_xy(x + bar_w + 4.0, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*bar_color)
    pdf.cell(24, bar_h, f"{pct * 100:.1f}%", border=0)

    # Description
    pdf.set_xy(x + bar_w + 28.0, y)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(0, bar_h, clean_text(label), border=0)

    pdf.set_y(y + bar_h + 3.0)


def kpi_grid(
    pdf,
    items: List[Tuple[str, str, Optional[str]]],
) -> None:
    """Render a 2x3 or 3x2 grid of clean KPI cards."""
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    cols = 3
    col_w = (usable - (cols - 1) * 3.5) / float(cols)
    card_h = 13.0

    y = pdf.get_y()
    for idx, (title, value, sub) in enumerate(items):
        r = idx // cols
        c = idx % cols
        card_x = pdf.l_margin + c * (col_w + 3.5)
        card_y = y + r * (card_h + 2.5)

        pdf.set_fill_color(*C_SLATE_BG)
        pdf.rect(card_x, card_y, col_w, card_h, style="F")
        pdf.set_draw_color(*C_LIGHT_BORDER)
        pdf.set_line_width(0.2)
        pdf.rect(card_x, card_y, col_w, card_h)

        # Title
        pdf.set_xy(card_x + 2.5, card_y + 1.8)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(col_w - 5.0, 3.2, clean_text(title).upper(), border=0)

        # Value
        pdf.set_xy(card_x + 2.5, card_y + 5.0)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*C_NAVY)
        pdf.cell(col_w - 5.0, 4.2, clean_text(value)[:30], border=0)

        # Subtext if present
        if sub:
            pdf.set_xy(card_x + 2.5, card_y + 9.0)
            pdf.set_font("Helvetica", "I", 6.5)
            pdf.set_text_color(*C_MUTED)
            pdf.cell(col_w - 5.0, 3.0, clean_text(sub)[:35], border=0)

    rows_count = (len(items) + cols - 1) // cols
    pdf.set_y(y + rows_count * (card_h + 2.5) + 2.0)


# ---------------------------------------------------------------------------
# Pipeline DAG Flowchart (Page 5 Execution Trace)
# ---------------------------------------------------------------------------

def pipeline_flowchart(
    pdf,
    steps: List[Tuple[str, str, str, str]],
) -> None:
    """Render a clean vertical flowchart representing the DAG pipeline stages.

    Each step tuple contains: (Stage Number, Stage Name, Status, Action Description)
    """
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    step_h = 13.0
    badge_w = 18.0

    y_start = pdf.get_y()
    for i, (num, name, status, desc) in enumerate(steps):
        y_cur = pdf.get_y()
        if y_cur + step_h + 4.0 > pdf.h - pdf.b_margin:
            pdf.add_page()
            y_cur = pdf.get_y()

        # Connecting vertical line
        if i < len(steps) - 1:
            pdf.set_draw_color(*C_BLUE)
            pdf.set_line_width(0.6)
            pdf.line(pdf.l_margin + 9.0, y_cur + 6.0, pdf.l_margin + 9.0, y_cur + step_h + 2.0)

        # Badge circle / box
        pdf.set_fill_color(*C_NAVY if i == len(steps) - 1 else C_BLUE)
        pdf.rect(pdf.l_margin, y_cur + 1.0, badge_w, 7.5, style="F")
        pdf.set_xy(pdf.l_margin, y_cur + 1.0)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_WHITE)
        pdf.cell(badge_w, 7.5, clean_text(num), align="C", border=0)

        # Stage Content Card
        card_x = pdf.l_margin + badge_w + 3.0
        card_w = usable - (badge_w + 3.0)

        pdf.set_fill_color(*C_SLATE_BG)
        pdf.rect(card_x, y_cur, card_w, step_h, style="F")
        pdf.set_draw_color(*C_LIGHT_BORDER)
        pdf.set_line_width(0.15)
        pdf.rect(card_x, y_cur, card_w, step_h)

        # Stage Name
        pdf.set_xy(card_x + 3.0, y_cur + 1.5)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*C_NAVY)
        pdf.cell(card_w * 0.65, 4.0, clean_text(name), border=0)

        # Status badge
        status_clean = clean_text(status).upper()
        stat_color = C_SUCCESS_GREEN if "PASS" in status_clean or "OK" in status_clean or "DONE" in status_clean else C_BLUE
        pdf.set_xy(card_x + card_w * 0.65, y_cur + 1.5)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*stat_color)
        pdf.cell(card_w * 0.32, 4.0, f"[{status_clean}]", align="R", border=0)

        # Stage Description
        pdf.set_xy(card_x + 3.0, y_cur + 6.0)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*C_BODY)
        pdf.cell(card_w - 6.0, 4.5, clean_text(desc)[:95], border=0)

        pdf.set_y(y_cur + step_h + 2.5)

    pdf.ln(1.5)


# ---------------------------------------------------------------------------
# Simple Body Text Utility
# ---------------------------------------------------------------------------

def body_text(pdf, text: str, line_height: float = 4.8) -> None:
    """Render paragraph body text cleanly wrapped."""
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*C_BODY)
    pdf.multi_cell(usable, line_height, clean_text(text) if text else "-", border=0)
    pdf.ln(1.0)
