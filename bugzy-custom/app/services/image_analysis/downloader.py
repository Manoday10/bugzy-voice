"""
Generic image download utilities for image analysis service.
Supports downloading images from any accessible URL.
"""

import requests
import tempfile
import os
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)


def download_image_from_url(
    image_url: str,
    auth_header: Optional[str] = None,
    timeout: int = 10,
    max_size_mb: int = 10
) -> Tuple[str, Dict[str, Any]]:
    """
    Download an image from a URL and save to temporary file.

    Args:
        image_url: URL to download the image from
        auth_header: Optional Bearer token for authentication
        timeout: Request timeout in seconds
        max_size_mb: Maximum allowed file size in MB

    Returns:
        Tuple of (temp_file_path, metadata_dict)
        metadata contains: size_bytes, format, width, height

    Raises:
        requests.exceptions.RequestException: Network/HTTP errors
        ValueError: Invalid image or size exceeded
    """
    # Prepare headers
    headers = {}
    if auth_header:
        headers["Authorization"] = f"Bearer {auth_header}"

    # Download the image
    response = requests.get(image_url, headers=headers, timeout=timeout, stream=True)
    response.raise_for_status()

    # Check size before loading entire file
    content_length = response.headers.get('content-length')
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise ValueError(f"Image size ({size_mb:.2f}MB) exceeds maximum ({max_size_mb}MB)")

    # Read image content
    image_content = response.content

    # Verify it's a valid image and get metadata
    try:
        img = Image.open(io.BytesIO(image_content))
        img_format = img.format
        width, height = img.size

        metadata = {
            "size_bytes": len(image_content),
            "format": img_format,
            "width": width,
            "height": height
        }
    except Exception as e:
        raise ValueError(f"Invalid image file: {str(e)}")

    # Save to temporary file
    suffix = f".{img_format.lower()}" if img_format else ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(image_content)
        temp_path = tmp_file.name

    return temp_path, metadata


def cleanup_temp_file(file_path: str) -> None:
    """
    Safely remove a temporary file.

    Args:
        file_path: Path to the temporary file
    """
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except Exception as e:
        logger.warning("Could not delete temp file %s: %s", file_path, e)
