"""
WhatsApp Parser Utilities

This module contains parsing functions for extracting and processing user input data.
Functions include age extraction, height/weight parsing, and other input validation utilities.
"""

import re
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ---------------- UTILITY FUNCTIONS ---------------- #
def parse_date(date_str):
    """Parse ISO date string to readable format."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except:
        return "N/A"


def extract_age(text: str) -> Optional[str]:
    """
    Intelligently extract age number from various user input formats.
    
    Handles variations like:
    - "im 22"
    - "hey im 22"
    - "my age is 22"
    - "im 22 years older"
    - "my age is 22"
    - "22"
    - "I'm 22 years old"
    - "22 years"
    - "age 22"
    - etc.
    
    Args:
        text: User input text containing age information
        
    Returns:
        Age as string if found, None otherwise
    """
    if not text:
        return None
    
    # Clean and normalize the text
    text = text.strip().lower()
    
    # Remove common punctuation and extra spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Pattern 1: Look for "im/i'm" followed by number
    pattern1 = r'\b(?:i\s*[a\']?m|im|i\s+am)\s+(\d{1,3})\b'
    match = re.search(pattern1, text)
    if match:
        age = match.group(1)
        if 1 <= int(age) <= 120:
            return age
    
    # Pattern 2: Look for "age" followed by "is" and number, or "age" directly before number
    pattern2 = r'\bage\s+(?:is\s+)?(\d{1,3})\b'
    match = re.search(pattern2, text)
    if match:
        age = match.group(1)
        if 1 <= int(age) <= 120:
            return age
    
    # Pattern 3: Look for "my age is" or "age is"
    pattern3 = r'\b(?:my\s+)?age\s+is\s+(\d{1,3})\b'
    match = re.search(pattern3, text)
    if match:
        age = match.group(1)
        if 1 <= int(age) <= 120:
            return age
    
    # Pattern 4: Look for number followed by "years old" or "years"
    pattern4 = r'\b(\d{1,3})\s+years?\s+(?:old|of\s+age)?\b'
    match = re.search(pattern4, text)
    if match:
        age = match.group(1)
        if 1 <= int(age) <= 120:
            return age
    
    # Pattern 5: Look for standalone numbers (1-120) that are likely ages
    # This is more permissive - check if there's context around it
    pattern5 = r'\b(\d{1,3})\b'
    matches = re.findall(pattern5, text)
    for potential_age in matches:
        age_num = int(potential_age)
        if 1 <= age_num <= 120:
            # Check if there's context that suggests it's an age
            # Look for age-related words nearby
            idx = text.find(potential_age)
            context_start = max(0, idx - 20)
            context_end = min(len(text), idx + 20)
            context = text[context_start:context_end]
            
            age_indicators = [
                'age', 'old', 'years', 'year', 'turning', 'almost', 
                'about', 'around', 'approximately', 'im', "i'm", 'am'
            ]
            
            # If we find age-related context, it's likely an age
            if any(indicator in context for indicator in age_indicators):
                return potential_age
            
            # If it's a standalone number and the text is short, it's likely an age
            if len(text.split()) <= 5:
                # Check if it's not part of a date, phone number, etc.
                # Avoid numbers that look like years (1900-2100)
                if not (1900 <= age_num <= 2100):
                    return potential_age
    
    # If no pattern matches, return None
    return None


def parse_height_weight(height_str: str, weight_str: str) -> tuple:
    """
    Parse height and weight from user input.
    
    Args:
        height_str: Height input (e.g., "5'10", "172cm", "5.8", "5 feet 10")
        weight_str: Weight input (e.g., "75kg", "165 lbs", "60-70", "150")
    
    Returns:
        tuple: (height_cm, weight_kg) or (None, None) if parsing fails
    """
    
    try:
        height_cm = None
        weight_kg = None
        
        # === PARSE HEIGHT ===
        height_str = height_str.strip().lower()
        
        # Extended list of apostrophe-like characters for feet/inches
        apostrophe_chars = [
            "'",           # Regular apostrophe (ASCII 39)
            "\u2018",      # Left single quote '
            "\u2019",      # Right single quote '
            "\u2032",      # Prime ′
            "\u2033",      # Double prime ″
            "`",           # Backtick
            "´",           # Acute accent
            "′",           # Prime symbol
            '"',           # Double quote
            "\u201c",      # Left double quote "
            "\u201d",      # Right double quote "
        ]
        
        # Check if it's feet/inches format - expanded with common typos
        feet_indicators = [
            # Standard
            "'", '"', 'feet', 'foot', 'ft', '\u2032', '\u2033', 
            '\u2018', '\u2019', '\u201c', '\u201d', '`', '´', '′',
            # Typos/Variations
            'feey', 'feeet', 'fett', 'ftt', 'feat', 'feett', 'fet'
        ]
        
        has_feet_indicator = any(indicator in height_str for indicator in feet_indicators)
        
        if has_feet_indicator:
            # Pattern 1: 5'10 or 5'10" or 5′10″ (with various apostrophe types)
            # Matches: feet[apostrophe]inches
            match = re.search(r"(\d+)\s*['\"\u2018\u2019\u2032\u2033\u201c\u201d`´′]\s*(\d+)", height_str)
            
            if not match:
                # Pattern 2: Relaxed "feet" word matching
                # Matches: feet[word/typo]inches
                # "6 feey 2" or "6ft 2"
                match = re.search(r"(\d+)\s*[a-zA-Z']+\s*(\d+)", height_str)
                # Verify the grouping char looks like a feet indicator
                if match:
                    # Double check if the text between numbers contains one of our indicators
                    # matching original logic but relaxed
                    pass

            if not match:
                 # Pattern 3: Just feet (e.g. "6 feey", "6 feet")
                 # Matches number followed by text that likely contains a feet indicator
                 match = re.search(r"(\d+)\s*([a-zA-Z'\"]+)", height_str)
                 if match and not any(ind in match.group(2) for ind in feet_indicators):
                     match = None # Reset if the word isn't a feet indicator
            
            if match:
                feet = float(match.group(1))
                # Check if we captured inches (group 2 exists and is numeric)
                # Note: Pattern 3 capture group 2 is text, so we need to be careful
                inches = 0
                if match.lastindex >= 2:
                    val = match.group(2)
                    if val.isdigit():
                         inches = float(val)
                
                # If we parsed safely
                height_cm = (feet * 30.48) + (inches * 2.54)
                
                # Validate reasonable height in feet (3' to 8')
                if not (3 <= feet <= 8):
                    height_cm = None 
            
            # Fallback: if regex failed but we saw an indicator (e.g. "Height 6 feey")
            # Try to grab the first reasonable number (3-8)
            if not height_cm:
                 # Find all numbers
                 numbers = re.findall(r'(\d+\.?\d*)', height_str)
                 for num in numbers:
                     val = float(num)
                     if 3 <= val <= 8:
                         # Assume this is feet
                         height_cm = val * 30.48
                         break
        else:
            # No feet indicator found - try to parse as numeric value
            cm_match = re.search(r'(\d+\.?\d*)', height_str)
            if cm_match:
                value = float(cm_match.group(1))
                
                # If value is between 3 and 8, it's likely feet in decimal format
                # e.g., 5.8 means 5 feet 8 inches (not 5.8 feet)
                if 3 <= value < 8:
                    feet = int(value)
                    decimal_part = value - feet
                    inches = decimal_part * 10  # 5.8 -> 5 feet 8 inches
                    height_cm = (feet * 30.48) + (inches * 2.54)
                elif value < 3:
                    # Too small to be valid height
                    return None, None
                else:
                    # Value >= 8, treat as centimeters
                    height_cm = value
        
        # === PARSE WEIGHT ===
        weight_str = weight_str.strip().lower()
        
        # Check for range format (e.g., "60-70 kg", "130-140 lbs")
        range_match = re.search(r'(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)', weight_str)
        
        if range_match:
            # Take the average of the range
            low = float(range_match.group(1))
            high = float(range_match.group(2))
            avg_value = (low + high) / 2
            
            # Determine unit
            if 'kg' in weight_str or 'kgs' in weight_str or 'kilogram' in weight_str:
                weight_kg = avg_value
            elif 'lb' in weight_str or 'pound' in weight_str:
                weight_kg = avg_value * 0.453592
            else:
                # No unit specified - heuristic: if < 200, assume kg; else lbs
                weight_kg = avg_value if avg_value < 200 else avg_value * 0.453592
        else:
            # Single value
            value_match = re.search(r'(\d+\.?\d*)', weight_str)
            if value_match:
                value = float(value_match.group(1))
                
                # Determine unit
                if 'kg' in weight_str or 'kgs' in weight_str or 'kilogram' in weight_str:
                    weight_kg = value
                elif 'lb' in weight_str or 'pound' in weight_str:
                    weight_kg = value * 0.453592
                else:
                    # No unit specified - heuristic: if < 200, assume kg; else lbs
                    weight_kg = value if value < 200 else value * 0.453592
        
        # === VALIDATE REASONABLE VALUES ===
        if height_cm and weight_kg:
            # Height: 100cm (3'3") to 250cm (8'2")
            # Weight: 20kg (44 lbs) to 300kg (661 lbs)
            if 100 <= height_cm <= 250 and 20 <= weight_kg <= 300:
                return height_cm, weight_kg
        
        return None, None
        
    except Exception as e:
        logger.error("Error parsing height/weight: %s", e)
        return None, None