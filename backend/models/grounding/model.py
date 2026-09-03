import os
import time
import logging
import base64
from io import BytesIO
from typing import Any, Dict, List
import cv2
import numpy as np
from PIL import Image, ImageDraw
from backend.models.base import BaseSpecialistModel
from backend.config import settings

logger = logging.getLogger("satquery.grounding")

class RemoteSensingGroundingModel(BaseSpecialistModel):
    """
    Specialist model for Text-Guided Region Grounding in satellite images.
    Uses an OpenCV-based pixel segmentation and contour detection fallback
    to identify and output spatial bounding boxes for water, vegetation,
    and built-up regions.
    """

    def __init__(self):
        # In a production system, this could load a model like OWL-ViT or Grounding DINO.
        # For our local lightweight execution, we default to our OpenCV-based pixel-segmentation engine.
        self.device = "cpu"

    @property
    def name(self) -> str:
        return "RemoteSensingGrounding"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Region Grounding.
        
        Args:
            inputs: Dictionary containing:
                - image_path (str): Absolute path to the image.
                - query (str): Text describing the target region (e.g. "water", "vegetation", "buildings").
                
        Returns:
            Dict containing:
                - bounding_boxes (List[List[int]]): Bounding boxes [ymin, xmin, ymax, xmax] in pixels.
                - annotated_image_b64 (str): Base64-encoded string of the image with highlighted boxes.
                - confidence (float)
                - evidence (dict)
                - execution_trace (dict)
        """
        image_path = inputs.get("image_path")
        query = inputs.get("query", "water").strip().lower()
        
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        start_time = time.time()
        
        # Load image via OpenCV
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at path {image_path}")

        with Image.open(image_path) as source:
            if len(source.getbands()) > 4:
                raise ValueError("Grounding expects an RGB visualization, not a raw multispectral raster.")
            
        h, w, c = img.shape
        total_pixels = h * w
        
        # Determine targeting mask based on query keywords
        binary_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Extract channels (OpenCV reads in BGR)
        b_ch, g_ch, r_ch = img[:, :, 0], img[:, :, 1], img[:, :, 2]
        
        target_name = "unknown"
        
        if any(kw in query for kw in ["water", "river", "lake", "ocean", "sea", "pond"]):
            target_name = "water body"
            # Blue index filter: B channel is dominant and not white/too bright
            blue_mask = (b_ch > (g_ch.astype(int) + 15)) & (b_ch > (r_ch.astype(int) + 15)) & (b_ch < 235)
            binary_mask[blue_mask] = 255
            
        elif any(kw in query for kw in ["vegetation", "forest", "green", "agriculture", "tree", "grass", "crop"]):
            target_name = "vegetation"
            # Green index filter: G channel is dominant
            green_mask = (g_ch > (r_ch.astype(int) + 10)) & (g_ch > (b_ch.astype(int) + 10))
            binary_mask[green_mask] = 255
            
        elif any(kw in query for kw in ["built-up", "urban", "building", "city", "road", "infrastructure", "structure"]):
            target_name = "built-up structure"
            # Gray/structural filter: BGR channels are close and within brightness bounds
            diff_rg = np.abs(r_ch.astype(int) - g_ch.astype(int))
            diff_gb = np.abs(g_ch.astype(int) - b_ch.astype(int))
            mean_val = (r_ch.astype(int) + g_ch.astype(int) + b_ch.astype(int)) / 3.0
            gray_mask = (diff_rg < 15) & (diff_gb < 15) & (mean_val > 80) & (mean_val < 200)
            binary_mask[gray_mask] = 255
            
        else:
            return {
                "bounding_boxes": [],
                "annotated_image_b64": "",
                "target_detected": None,
                "box_count": 0,
                "confidence": 0.0,
                "evidence": {"unsupported_query": query},
                "execution_trace": {
                    "task": "Text-Guided Region Grounding",
                    "model": f"{self.name} (unsupported target)",
                    "execution_time_seconds": round(time.time() - start_time, 4),
                    "fallback_active": True,
                },
                "status": "unsupported_query",
            }

        # Post-process binary mask: Apply morphology to group adjacent pixels
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bounding_boxes = []
        annotated_img = img.copy()
        
        # Filter contours by size to ignore tiny spots (noise)
        min_contour_area = max(50, int(total_pixels * 0.0005))
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_contour_area:
                x, y, w_box, h_box = cv2.boundingRect(contour)
                # Formulate box coordinates: [ymin, xmin, ymax, xmax]
                box = [y, x, y + h_box, x + w_box]
                bounding_boxes.append(box)
                
                # Draw on annotated image (Green box for vegetation, Blue for water, Red for buildings/other)
                if target_name == "water body":
                    color = (255, 0, 0)  # BGR: Blue
                elif target_name == "vegetation":
                    color = (0, 255, 0)  # BGR: Green
                else:
                    color = (0, 0, 255)  # BGR: Red
                    
                cv2.rectangle(annotated_img, (x, y), (x + w_box, y + h_box), color, 2)
                
                # Put label text
                cv2.putText(annotated_img, target_name, (x, max(15, y - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Convert annotated image to base64
        _, buffer = cv2.imencode('.png', annotated_img)
        img_b64 = base64.b64encode(buffer).decode('utf-8')
        
        elapsed = time.time() - start_time
        
        # Calculate confidence metric based on detected box areas vs total target pixels
        target_pixels = np.sum(binary_mask == 255)
        target_ratio = float(target_pixels / total_pixels)
        confidence = float(np.clip(0.70 + (target_ratio * 0.25), 0.65, 0.90)) if bounding_boxes else 0.50

        return {
            "bounding_boxes": bounding_boxes,
            "annotated_image_b64": img_b64,
            "target_detected": target_name,
            "box_count": len(bounding_boxes),
            "confidence": round(confidence, 4),
            "evidence": {
                "segmented_area_ratio": round(target_ratio, 4),
                "box_coordinates_format": "[ymin, xmin, ymax, xmax]"
            },
            "execution_trace": {
                "task": "Text-Guided Region Grounding",
                "model": f"{self.name} (OpenCV Color-Contour Filter)",
                "execution_time_seconds": round(elapsed, 4),
                "fallback_active": True
            }
        }
