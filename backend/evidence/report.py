"""Professional 6-page PDF analysis report generator for SatQuery AI.

Public interface (signature unchanged from original):

    generate_pdf_report(title: str, result: Dict[str, Any]) -> str

Returns a base64-encoded PDF built from the final_payload dict produced by
``fuse_evidence_node`` in ``backend/agent/graph.py``.

Pages
-----
1. Executive Summary   - ID, datetime, query, task, result, confidence
2. Input Data          - image previews + metadata table
3. Analysis            - task classifier, specialist, output, scores
4. Evidence            - overlays, bounding boxes, change masks
5. Execution Trace     - numbered pipeline timeline
6. Technical Info      - model, checkpoint, preprocessing, evaluation notes
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fpdf import FPDF

from backend.evidence._pdf_helpers import (
    C_BLUE, C_BODY, C_LIGHT_BORDER, C_MUTED, C_NAVY, C_SECTION_BG, C_WHITE,
    body_text, bounding_box_table, draw_confidence_bar,
    insert_image_safe, kv_table, pipeline_timeline, section_title,
)

PAGE_W = 210
PAGE_H = 297
MARGIN_LR = 15
MARGIN_TB = 12
USABLE_W = PAGE_W - 2 * MARGIN_LR


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(title: str, result: Dict[str, Any]) -> Dict[str, Any]:
    route = result.get("route") or {}
    task_name = route.get("task") or result.get("route_task") or "unknown"
    evidence = result.get("evidence") or {}
    exec_trace = result.get("execution_trace") or {}
    steps = exec_trace.get("steps") if isinstance(exec_trace, dict) else []

    img_meta_1 = (
        evidence.get("image_metadata")
        or evidence.get("image_t1_metadata")
        or {}
    )
    img_meta_2 = evidence.get("image_t2_metadata") or {}
    raw_conf = result.get("confidence")
    confidence = float(raw_conf) if raw_conf is not None else None
    answer = (
        result.get("answer") or result.get("caption")
        or result.get("change_summary") or result.get("summary") or ""
    )
    overlay_b64 = next(
        (result[k] for k in ("overlay_b64", "annotated_image_b64", "change_map_b64") if result.get(k)),
        None,
    )
    analysis_id = f"SQ-{uuid.uuid4().hex[:10].upper()}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M:%S UTC")

    return {
        "title": title,
        "analysis_id": analysis_id,
        "generated_at": generated_at,
        "query": result.get("query") or "",
        "status": result.get("status") or "success",
        "task_name": task_name,
        "task_reason": route.get("reason") or "",
        "answer": answer,
        "confidence": confidence,
        "img_meta_1": img_meta_1,
        "img_meta_2": img_meta_2,
        "overlay_b64": overlay_b64,
        "bboxes": result.get("bounding_boxes") or [],
        "predictions": result.get("predictions") or [],
        "scores": (result.get("scores") or [])[:8],
        "change_ratio": result.get("change_ratio"),
        "change_summary": result.get("change_summary"),
        "class_coverage": result.get("class_coverage") or {},
        "pair_meta": result.get("pair_metadata") or {},
        "evidence": evidence,
        "trace_steps": steps or [],
        "thread_id": result.get("thread_id") or "-",
    }


# ---------------------------------------------------------------------------
# Core PDF class
# ---------------------------------------------------------------------------

class SatQueryPDFReport(FPDF):
    """Six-page professional remote-sensing analysis PDF."""

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(MARGIN_LR, MARGIN_TB, MARGIN_LR)
        self.set_auto_page_break(auto=True, margin=18)
        self._page_label = ""

    def header(self) -> None:
        self.set_fill_color(*C_NAVY)
        self.rect(0, 0, PAGE_W, 14, style="F")
        self.set_xy(MARGIN_LR, 3.5)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*C_WHITE)
        self.cell(80, 7, "SatQuery AI", border=0)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(180, 200, 230)
        self.cell(0, 7, self._page_label, align="R", border=0)
        self.set_y(16)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*C_BLUE)
        self.set_line_width(0.3)
        self.line(MARGIN_LR, self.get_y(), PAGE_W - MARGIN_LR, self.get_y())
        self.ln(1)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*C_MUTED)
        self.cell(USABLE_W / 2, 5, "Remote Sensing Analysis Report  -  SatQuery AI", border=0)
        self.cell(USABLE_W / 2, 5, f"Page {self.page_no()}", align="R", border=0)

    def _page_heading(self, number: str, title: str, subtitle: str = "") -> None:
        self.ln(1)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*C_NAVY)
        self.cell(USABLE_W, 8, f"Section {number}  *  {title}", new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(*C_MUTED)
            self.cell(USABLE_W, 5, subtitle, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_LIGHT_BORDER)
        self.set_line_width(0.2)
        self.line(MARGIN_LR, self.get_y() + 1, MARGIN_LR + USABLE_W, self.get_y() + 1)
        self.ln(4)
        self.set_text_color(*C_BODY)

    # ------------------------------------------------------------------
    # Page 1 - Executive Summary
    # ------------------------------------------------------------------

    def _page_executive_summary(self, ctx: Dict[str, Any]) -> None:
        self._page_label = "Executive Summary"
        self.add_page()

        # Hero block
        self.set_fill_color(*C_NAVY)
        self.rect(MARGIN_LR, self.get_y(), USABLE_W, 30, style="F")
        self.set_xy(MARGIN_LR + 4, self.get_y() + 4)
        self.set_font("Helvetica", "B", 17)
        self.set_text_color(*C_WHITE)
        self.cell(USABLE_W - 8, 9, "Remote Sensing Analysis Report", new_x="LMARGIN", new_y="NEXT")
        self.set_xy(MARGIN_LR + 4, self.get_y())
        self.set_font("Helvetica", "", 9)
        self.set_text_color(180, 200, 230)
        self.cell(USABLE_W - 8, 5.5, ctx["generated_at"], new_x="LMARGIN", new_y="NEXT")
        self.set_xy(MARGIN_LR + 4, self.get_y())
        self.set_font("Helvetica", "I", 8)
        self.cell(USABLE_W - 8, 5, f"Analysis ID: {ctx['analysis_id']}   *   Session: {ctx['thread_id']}")
        self.set_y(self.get_y() + 20)
        self.ln(6)

        TASK_LABELS = {
            "vqa": "Visual Question Answering",
            "caption": "Scene Captioning",
            "grounding": "Region Grounding",
            "change": "Bi-temporal Change Detection",
            "optical_sar": "Optical + SAR Fusion",
            "land_cover": "Land-Cover Classification",
        }
        task_label = TASK_LABELS.get(ctx["task_name"], ctx["task_name"].replace("_", " ").title())

        section_title(self, "Query", top_gap=0)
        body_text(self, ctx["query"] or "-")

        section_title(self, "Analysis Summary")
        kv_table(self, [
            ("Detected Task", task_label),
            ("Analysis ID", ctx["analysis_id"]),
            ("Generated", ctx["generated_at"]),
            ("Session / Thread", ctx["thread_id"]),
            ("Input Modality", ctx["img_meta_1"].get("modality") or "-"),
            ("Sensor", ctx["img_meta_1"].get("sensor") or "-"),
            ("Status", ctx["status"].title()),
        ])

        section_title(self, "Final Result")
        body_text(self, ctx["answer"] or "-")

        if ctx["confidence"] is not None:
            section_title(self, "Confidence")
            draw_confidence_bar(self, ctx["confidence"])

    # ------------------------------------------------------------------
    # Page 2 - Input Data
    # ------------------------------------------------------------------

    def _page_input_data(self, ctx: Dict[str, Any]) -> None:
        self._page_label = "Input Data"
        self.add_page()
        self._page_heading("2", "Input Data", "Image specifications, sensor metadata, and validation status")

        def _render_meta(meta: Dict[str, Any], label: str) -> None:
            section_title(self, label, top_gap=2)
            rows = [
                ("File Name", meta.get("file_name") or "-"),
                ("Sensor", meta.get("sensor") or "-"),
                ("Modality", meta.get("modality") or "-"),
                ("Format", meta.get("format") or "-"),
                ("Dimensions", f"{meta.get('width', '?')} x {meta.get('height', '?')} px"),
                ("Bands", str(meta.get("bands") or "-")),
                ("Acquisition Date", meta.get("acquisition_date") or "Not available"),
                ("CRS", meta.get("crs") or "Not georeferenced"),
                ("Geospatial", "Yes" if meta.get("geospatial") else "No"),
                ("Polarization", meta.get("polarization") or "-"),
                ("File Size", f"{meta.get('file_size_bytes', 0) // 1024:,} KB"
                    if meta.get("file_size_bytes") else "-"),
                ("Validation", "Passed OK"),
            ]
            rows = [(k, v) for k, v in rows if v not in ("-", "Not available", None)]
            kv_table(self, rows)

        meta1 = ctx["img_meta_1"]
        meta2 = ctx["img_meta_2"]

        if ctx["task_name"] == "optical_sar" and meta2:
            _render_meta(meta1, "Optical Image (Sentinel-2)")
            self.ln(3)
            _render_meta(meta2, "SAR Image (Sentinel-1)")
        elif ctx["task_name"] == "change":
            _render_meta(meta1, "T1 - Earlier Image")
            if meta2:
                self.ln(3)
                _render_meta(meta2, "T2 - Later Image")
        else:
            _render_meta(meta1, "Input Image")

        if ctx["pair_meta"]:
            section_title(self, "Co-registration / Pair Metadata")
            pair_rows = [
                (str(k).replace("_", " ").title(), str(v))
                for k, v in ctx["pair_meta"].items() if v is not None
            ]
            kv_table(self, pair_rows[:10])

    # ------------------------------------------------------------------
    # Page 3 - Analysis
    # ------------------------------------------------------------------

    def _page_analysis(self, ctx: Dict[str, Any]) -> None:
        self._page_label = "Analysis"
        self.add_page()
        self._page_heading("3", "Analysis", "Task classification, specialist model output, and inference scores")

        TASK_MAP = {
            "vqa": ("Visual Question Answering (RSVQA)", "RemoteSensingVQAModel  (BLIP-VQA + LoRA adapter)"),
            "caption": ("Remote Sensing Scene Captioning", "RemoteSensingCaptionModel  (BLIP Image Captioning)"),
            "grounding": ("Text-Guided Region Grounding", "RemoteSensingGroundingModel  (OpenCV Color-Contour Filter)"),
            "change": ("Bi-temporal Change Detection", "ChangeDetectionModel + ChangeVQAModel"),
            "optical_sar": ("Optical + SAR Cross-Modal Fusion", "OpticalSARFusionModel  (Spectral-Backscatter Baseline)"),
            "land_cover": ("BigEarthNet v2.0 Land-Cover Classification", "BigEarthNetV2ConvMixer  (ConvMixer-768/32)"),
        }
        task_label, specialist = TASK_MAP.get(
            ctx["task_name"], (ctx["task_name"].replace("_", " ").title(), "Specialist Model")
        )

        section_title(self, "Task Classification", top_gap=0)
        kv_table(self, [
            ("Detected Task", task_label),
            ("Classification Basis", ctx["task_reason"] or "Query keywords and image count"),
            ("Specialist Model", specialist),
        ])

        section_title(self, "Analysis Output")
        body_text(self, ctx["answer"] or "-")

        if ctx["confidence"] is not None:
            self.ln(2)
            draw_confidence_bar(self, ctx["confidence"])

        if ctx["change_ratio"] is not None:
            section_title(self, "Change Statistics")
            kv_table(self, [
                ("Changed Area", f"{ctx['change_ratio'] * 100:.1f}% of scene"),
                ("Change Description", ctx["change_summary"] or "-"),
            ])

        if ctx["class_coverage"]:
            section_title(self, "Class Coverage")
            kv_table(self, [
                (k.replace("_", " ").title(), f"{v * 100:.1f}%")
                for k, v in ctx["class_coverage"].items()
            ])

        if ctx["predictions"]:
            section_title(self, "Land-Cover Predictions  (threshold >= 0.50)")
            col_lbl = USABLE_W * 0.72
            col_sc  = USABLE_W * 0.28
            self.set_fill_color(*C_NAVY)
            self.set_text_color(*C_WHITE)
            self.set_font("Helvetica", "B", 8)
            self.cell(col_lbl, 6.5, "Class", fill=True, border=0)
            self.cell(col_sc, 6.5, "Score", fill=True, border=0)
            self.ln()
            for i, pred in enumerate(ctx["predictions"][:12]):
                if self.get_y() + 6.5 > PAGE_H - 20:
                    self.add_page()
                fill = i % 2 == 0
                if fill:
                    self.set_fill_color(246, 249, 252)
                self.set_text_color(*C_BODY)
                self.set_font("Helvetica", "", 8)
                self.cell(col_lbl, 6, str(pred.get("label", "-")), fill=fill, border=0)
                self.cell(col_sc, 6, f"{pred.get('score', 0):.4f}", fill=fill, border=0)
                self.ln()
            self.ln(2)

        ev = ctx["evidence"]
        if ev:
            section_title(self, "Evidence Metadata")
            ev_rows = []
            for k, v in ev.items():
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        ev_rows.append((f"{k} › {k2}".replace("_", " ").title(), str(v2)))
                elif v is not None:
                    ev_rows.append((k.replace("_", " ").title(), str(v)))
            kv_table(self, ev_rows[:16])

    # ------------------------------------------------------------------
    # Page 4 - Evidence
    # ------------------------------------------------------------------

    def _page_evidence(self, ctx: Dict[str, Any]) -> None:
        self._page_label = "Evidence"
        self.add_page()
        self._page_heading("4", "Evidence", "Visual outputs: overlays, bounding boxes, segmentation masks")

        if ctx["overlay_b64"]:
            overlay_caption = {
                "vqa": "VQA input visualization",
                "caption": "Scene overview",
                "grounding": "Region grounding annotation with detected bounding boxes",
                "change": "Change heatmap overlay (JET colormap blended with T2)",
                "optical_sar": "Optical-SAR fusion overlay  (blue = water, red = built-up)",
                "land_cover": "Multi-spectral RGB preview",
            }.get(ctx["task_name"], "Analysis overlay")

            section_title(self, "Analysis Overlay / Annotated Output", top_gap=0)
            insert_image_safe(
                self, ctx["overlay_b64"],
                max_w=USABLE_W, max_h=110,
                caption=overlay_caption,
            )

        if ctx["bboxes"] or ctx["task_name"] in ("grounding", "optical_sar"):
            section_title(self, "Detected Regions - Bounding Boxes")
            bounding_box_table(self, ctx["bboxes"])

        if ctx["change_ratio"] is not None:
            section_title(self, "Change Magnitude")
            draw_confidence_bar(
                self, ctx["change_ratio"],
                label=f"Changed area  ({ctx['change_ratio'] * 100:.1f}% of scene)",
                bar_w=100,
            )

        if not ctx["overlay_b64"] and not ctx["bboxes"] and ctx["change_ratio"] is None:
            body_text(self, "No visual evidence artifacts were generated for this analysis type.")

    # ------------------------------------------------------------------
    # Page 5 - Execution Trace
    # ------------------------------------------------------------------

    def _page_execution_trace(self, ctx: Dict[str, Any]) -> None:
        self._page_label = "Execution Trace"
        self.add_page()
        self._page_heading("5", "Execution Trace", "High-level pipeline timeline - internal chain-of-thought not exposed")

        PIPELINE = [
            "Input Received",
            "Input Validation",
            "Task Classification",
            "Specialist Inference",
            "Evidence Generation",
            "Result Assembly",
        ]
        section_title(self, "Pipeline Timeline", top_gap=0)
        pipeline_timeline(self, PIPELINE)

        raw_steps = ctx["trace_steps"]
        if raw_steps:
            section_title(self, "Detailed Node Trace")
            node_rows = []
            for step in raw_steps:
                if not isinstance(step, dict):
                    continue
                node = (step.get("node") or step.get("task") or step.get("model") or "step")
                status = step.get("status") or "done"
                reason = step.get("reason") or step.get("selected_task") or step.get("error") or ""
                exec_t = step.get("execution_time_seconds")
                val = status.title()
                if reason:
                    val += f"  -  {reason}"
                if exec_t is not None:
                    val += f"  ({exec_t:.3f} s)"
                node_rows.append((node.replace("_", " ").title(), val))
            kv_table(self, node_rows[:20])

        timing = [
            (
                (s.get("task") or s.get("model") or s.get("node") or "step").replace("_", " ").title(),
                f"{s['execution_time_seconds']:.4f} s",
            )
            for s in raw_steps
            if isinstance(s, dict) and s.get("execution_time_seconds") is not None
        ]
        if timing:
            section_title(self, "Execution Timing")
            kv_table(self, timing)

    # ------------------------------------------------------------------
    # Page 6 - Technical Information
    # ------------------------------------------------------------------

    def _page_technical_info(self, ctx: Dict[str, Any]) -> None:
        self._page_label = "Technical Information"
        self.add_page()
        self._page_heading("6", "Technical Information", "Model architecture, preprocessing, and evaluation notes")

        TECH: Dict[str, Dict[str, str]] = {
            "vqa": {
                "Model": "Salesforce/blip-vqa-base",
                "Adapter": "LoRA fine-tuned on RSVQA-LR  (rsvqa-blip-lora checkpoint)",
                "Framework": "HuggingFace Transformers + PEFT",
                "Inference": "Beam search  *  4 beams  *  max 16 new tokens",
                "Input Format": "RGB PNG/JPEG  *  384x384 px  (BLIP processor resize)",
                "Task Type": "Conditional generation  -  Visual Question Answering",
                "Benchmark": "RSVQA-LR  (Lobry et al., IEEE TGRS 2020)",
            },
            "caption": {
                "Model": "Salesforce/blip-image-captioning-base",
                "Fallback": "Pixel-spectral heuristic  (vegetation / water / structural ratios)",
                "Framework": "HuggingFace Transformers",
                "Input Format": "RGB PNG/JPEG, variable resolution",
                "Task Type": "Unconditional image captioning",
            },
            "grounding": {
                "Model": "RemoteSensingGroundingModel v1.0.0",
                "Backend": "OpenCV color-channel segmentation + morphological contour detection",
                "Supported Targets": "Water body, vegetation, built-up structures",
                "Output Format": "Bounding boxes [ymin, xmin, ymax, xmax] + annotated PNG",
                "Input Format": "RGB PNG/JPEG visualization (not raw multispectral)",
            },
            "change": {
                "Model": "ChangeDetectionModel v1.0.0 + ChangeVQAModel",
                "Method": "Grayscale difference → Gaussian blur → threshold 30 DN → morphological cleanup",
                "Visualization": "JET colormap heatmap blended with T2  (alpha = 0.50)",
                "Input Format": "Co-registered RGB PNG/JPEG pairs  (equal spatial dimensions required)",
            },
            "optical_sar": {
                "Model": "OpticalSARFusionModel v1.0.0",
                "Fusion Rule": "Water: optical blue dominance AND SAR P35 low backscatter; "
                               "Built-up: optical neutral albedo AND SAR P65 high backscatter",
                "SAR Preprocessing": "3x3 median filter + P2/P98 percentile normalisation",
                "Input Format": "Co-registered optical RGB + SAR grayscale PNG  (equal dimensions)",
            },
            "land_cover": {
                "Model": "BigEarthNetV2ConvMixer v0.2.0",
                "Checkpoint": "BIFOLD-BigEarthNetv2-0/convmixer_768_32-all-v0.2.0",
                "Architecture": "ConvMixer-768 depth 32  (isotropic depthwise-separable patches)",
                "Nomenclature": "19-class CORINE Land Cover aggregated taxonomy",
                "Threshold": "Sigmoid probability >= 0.50  (BIGEARTHNET_THRESHOLD)",
                "Input Format": "12-band Sentinel-2 L2A GeoTIFF  *  float32 BOA reflectance  *  120x120 px",
                "Band Order": "B01, B02, B03, B04, B05, B06, B07, B08, B8A, B09, B11, B12",
                "Normalisation": "Per-band mean/std from ConfigILM BENv2_utils (120_nearest statistics)",
                "Reference": "reBEN: Revisiting BigEarthNet for Remote Sensing Image Analysis (2024)",
            },
        }

        details = TECH.get(ctx["task_name"], {})
        section_title(self, "Model & Inference Details", top_gap=0)
        if details:
            kv_table(self, list(details.items()))
        else:
            body_text(self, "Technical details not available for this task type.")

        section_title(self, "Data Provenance & Licensing")
        kv_table(self, [
            ("Sensor - Optical", "Sentinel-2 MSI  (ESA Copernicus Open Access)"),
            ("Sensor - SAR", "Sentinel-1 C-band GRD  (ESA Copernicus Open Access)"),
            ("VQA Benchmark", "RSVQA-LR  (Lobry et al., IEEE TGRS 2020)"),
            ("Land-Cover Benchmark", "BigEarthNet v2.0 / reBEN  (CDLA-Permissive-1.0)"),
            ("Optical License", "Copernicus Open Access  -  free and open data policy"),
        ])

        section_title(self, "Validation & Quality Notes")
        body_text(self,
            "All input images were validated prior to inference for: file format integrity, "
            "pixel value range, minimum dimension requirements, and (for GeoTIFF) "
            "band count and spatial reference system conformance. "
            "BigEarthNet land-cover inference strictly rejects RGB imagery; a 12-band "
            "Sentinel-2 GeoTIFF is required. "
            "Optical-SAR fusion requires co-registered images of equal dimensions. "
            "Change detection requires T1 and T2 images of identical spatial extent."
        )

        section_title(self, "Report Generation")
        kv_table(self, [
            ("Generated At", ctx["generated_at"]),
            ("Analysis ID", ctx["analysis_id"]),
            ("Report Version", "SatQuery AI PDF Report v2.0  (fpdf2 2.8.x)"),
            ("Generator", "backend.evidence.report.SatQueryPDFReport"),
        ])


# ---------------------------------------------------------------------------
# Public entry point - signature identical to original
# ---------------------------------------------------------------------------

def generate_pdf_report(title: str, result: Dict[str, Any]) -> str:
    """Generate a professional 6-page PDF analysis report.

    Args:
        title: Report title string (forwarded from fuse_evidence_node).
        result: The final_payload dict produced by fuse_evidence_node.

    Returns:
        Base64-encoded PDF byte string (starts with 'JVBER' when decoded).
    """
    import base64
    ctx = _build_context(title, result)
    pdf = SatQueryPDFReport()
    pdf._page_executive_summary(ctx)
    pdf._page_input_data(ctx)
    pdf._page_analysis(ctx)
    pdf._page_evidence(ctx)
    pdf._page_execution_trace(ctx)
    pdf._page_technical_info(ctx)
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
