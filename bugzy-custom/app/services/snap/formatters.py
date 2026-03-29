"""
Text Formatting Utilities for Snap Vision Analysis

This module contains functions to format and clean vision analysis outputs
to ensure consistency and proper emoji/bullet point usage.
"""

import re


def format_category_a_text(raw_text: str) -> str:
    """
    Formats Category A output to ensure consistency
    - Replaces dashes with bullet points
    - Ensures proper emoji usage
    - Adds spacing where needed
    """
    formatted = raw_text

    # Replace dash bullets with proper bullets
    formatted = re.sub(r'^- ', '• ', formatted, flags=re.MULTILINE)

    # Ensure emojis are present (add if missing)
    if '📸' not in formatted and '**Image Analysis Results:**' in formatted:
        formatted = formatted.replace('**Image Analysis Results:**', '📸 **Image Analysis Results:**')
    if '🔍' not in formatted and '**Detected Items:**' in formatted:
        formatted = formatted.replace('**Detected Items:**', '🔍 **Detected Items:**')
    if '✅' not in formatted and '**Health Assessment:**' in formatted:
        formatted = formatted.replace('**Health Assessment:**', '✅ **Health Assessment:**')
    if '💡' not in formatted and '**Gut Health Integration:**' in formatted:
        formatted = formatted.replace('**Gut Health Integration:**', '💡 **Gut Health Integration:**')

    # Clean up extra whitespace
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)

    return formatted.strip()


def format_category_b_text(raw_text: str) -> str:
    """
    Formats Category B output to ensure consistency
    """
    formatted = raw_text

    # Replace dash bullets with proper bullets
    formatted = re.sub(r'^- ', '• ', formatted, flags=re.MULTILINE)

    # Ensure emojis are present
    if '🥗' not in formatted and '**Ingredient Analysis Results:**' in formatted:
        formatted = formatted.replace('**Ingredient Analysis Results:**', '🥗 **Ingredient Analysis Results:**')
    if '📋' not in formatted and '**Identified Ingredients:**' in formatted:
        formatted = formatted.replace('**Identified Ingredients:**', '📋 **Identified Ingredients:**')
    if '🍳' not in formatted and '**Suggested Healthy Recipes' in formatted:
        formatted = formatted.replace('**Suggested Healthy Recipes', '🍳 **Suggested Healthy Recipes')
    if '💡' not in formatted and '**General Pro Tips:**' in formatted:
        formatted = formatted.replace('**General Pro Tips:**', '💡 **General Pro Tips:**')

    formatted = re.sub(r'\n{3,}', '\n\n', formatted)

    return formatted.strip()
