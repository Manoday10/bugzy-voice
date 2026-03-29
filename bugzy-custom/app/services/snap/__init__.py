"""
Snap Vision Analysis Service

This package provides food image analysis capabilities using vision AI.
Supports classification and analysis of prepared foods, raw ingredients,
and non-food items.
"""

from app.services.snap.analyzer import analyze_food_image
from app.services.snap.models import CategoryAOutput, CategoryBOutput, CategoryCOutput
from app.services.snap.formatters import format_category_a_text, format_category_b_text

__all__ = [
    "analyze_food_image",
    "CategoryAOutput",
    "CategoryBOutput",
    "CategoryCOutput",
    "format_category_a_text",
    "format_category_b_text",
]
