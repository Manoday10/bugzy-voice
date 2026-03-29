"""
Image analysis service using SNAP food analysis.
Provides a wrapper around the existing SNAP service for REST API integration.
"""

import time
import requests
from typing import Dict, Any, Optional
from app.services.snap.analyzer import analyze_food_image_direct
from app.services.image_analysis.downloader import download_image_from_url, cleanup_temp_file
import logging

logger = logging.getLogger(__name__)


def analyze_image_with_snap(
    image_url: str,
    auth_token: Optional[str] = None,
    user_query: Optional[str] = None  # NEW in v3.0
) -> Dict[str, Any]:
    """
    Analyze an image using SNAP food analysis service.

    This function downloads the image from a URL and uses the existing
    SNAP service (analyze_food_image_direct) to perform food classification
    and nutritional analysis.

    Args:
        image_url: URL to download the image from
        auth_token: Optional authentication token for image download
        user_query: Optional user caption or question for guided analysis (NEW in v3.0)

    Returns:
        Dict containing:
        - success: bool
        - response: str (formatted food analysis from SNAP)
        - confidence: float (0.0-1.0)
        - intent: str (category-based intent)
        - metadata: dict with SNAP analysis details
        - analysis_mode: str (NEW in v3.0)
        - user_query: str (NEW in v3.0)
        - error: Optional error message
    """
    temp_file_path = None
    start_time = time.time()

    try:
        # Step 1: Download the image
        logger.info("📥 Downloading image from: %s", image_url)
        temp_file_path, image_metadata = download_image_from_url(
            image_url=image_url,
            auth_header=auth_token,
            timeout=15,
            max_size_mb=10
        )

        logger.info("✅ Image downloaded: %s", image_metadata)

        # Step 2: Analyze using SNAP service
        logger.info("🍽️ Analyzing image with SNAP food analysis...")
        if user_query:
            logger.info("   With user query: %s", user_query)
        snap_result = analyze_food_image_direct(
            temp_file_path,
            user_query=user_query  # NEW in v3.0
        )

        # Step 3: Check if SNAP analysis succeeded
        if not snap_result.get("success", False):
            error_msg = snap_result.get("error", "SNAP analysis failed")
            logger.error("❌ SNAP analysis error: %s", error_msg)
            return {
                "success": False,
                "response": None,
                "confidence": None,
                "intent": None,
                "metadata": None,
                "error": error_msg
            }

        # Step 4: Map SNAP response to API format
        vision_content = snap_result.get("vision_content", "")
        category = snap_result.get("category", "")
        snap_confidence = snap_result.get("confidence", "MEDIUM")

        # Convert SNAP confidence to 0.0-1.0 scale
        confidence_map = {
            "HIGH": 0.9,
            "MEDIUM": 0.7,
            "LOW": 0.5,
            "RECLASSIFIED": 0.4
        }
        confidence = confidence_map.get(snap_confidence, 0.7)

        # Map category to intent
        intent_map = {
            "A": "food_prepared",
            "B": "food_raw",
            "C": "non_food"
        }
        intent = intent_map.get(category, "unknown")

        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Build metadata
        metadata = {
            "analysis_type": "snap_food_analysis",
            "category": category,
            "image_dimensions": {
                "width": image_metadata.get("width"),
                "height": image_metadata.get("height")
            },
            "image_format": image_metadata.get("format"),
            "image_size_bytes": image_metadata.get("size_bytes"),
            "processing_time_ms": round(processing_time_ms, 2),
            "model_used": "llama-11b-vision",
            "validation_details": snap_result.get("validation_details", []),
            "raw_output": snap_result.get("raw_output", ""),
            "reasoning": snap_result.get("reasoning", ""),
            # NEW in v3.0: Caption support fields
            "analysis_mode": snap_result.get("analysis_mode", "AUTO"),
            "mode_metadata": snap_result.get("mode_metadata", {})
        }

        logger.info("✅ SNAP analysis complete in %.2fms", processing_time_ms)
        logger.info("   Category: %s, Confidence: %s", category, snap_confidence)

        return {
            "success": True,
            "response": vision_content,
            "confidence": confidence,
            "intent": intent,
            "metadata": metadata,
            "error": None,
            # NEW in v3.0: Caption support fields
            "analysis_mode": snap_result.get("analysis_mode", "AUTO"),
            "user_query": user_query
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "response": None,
            "confidence": None,
            "intent": None,
            "metadata": None,
            "error": "Image download timed out. Please ensure the URL is accessible."
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "response": None,
            "confidence": None,
            "intent": None,
            "metadata": None,
            "error": f"Failed to download image: {str(e)}"
        }
    except ValueError as e:
        return {
            "success": False,
            "response": None,
            "confidence": None,
            "intent": None,
            "metadata": None,
            "error": str(e)
        }
    except Exception as e:
        logger.error("❌ Unexpected error in image analysis: %s", e, exc_info=True)
        return {
            "success": False,
            "response": None,
            "confidence": None,
            "intent": None,
            "metadata": None,
            "error": f"Image analysis failed: {str(e)}"
        }
    finally:
        # Always cleanup temp file
        if temp_file_path:
            cleanup_temp_file(temp_file_path)
