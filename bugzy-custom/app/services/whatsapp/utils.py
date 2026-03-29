import time
import requests
import pytz
import os
import re
from datetime import datetime, timezone
from typing import TypedDict, Optional, Literal, TYPE_CHECKING
from app.services.llm.bedrock_llm import ChatBedRockLLM
from dotenv import load_dotenv
from pymongo import MongoClient
import logging

logger = logging.getLogger(__name__)

# Import State from agent for type hints (using TYPE_CHECKING to avoid circular imports)
# For runtime, we'll use string annotations or import at function level where needed
if TYPE_CHECKING:
    from agent import State
else:
    # Use string annotation for State type to avoid circular import at runtime
    State = "State"  # This is just for type checking, actual State comes from agent

load_dotenv()

# --- WhatsApp Sender Injection ---
WHATSAPP_SENDER = None

# WhatsApp API credentials
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

# --- CRM Config ---
CRM_BASE_URL = os.getenv("CRM_BASE_URL")
CRM_API_TOKEN = os.getenv("CRM_API_TOKEN")
CRM_HEADERS = {
    "Authorization": f"Bearer {CRM_API_TOKEN}",
    "Content-Type": "application/json"
}

SESSIONS = {}

# --- Scheduler ---
_scheduler = None
_sending_message = False

# --- Session Persistence (MongoDB) ---
MONGO_URI = os.getenv("MONGO_URI")
_mongo_client: MongoClient | None = None
_mongo_db = None


def _store_question_in_history(state: State, question: str, question_type: str = None):
    """
    Store a question in conversation history with a placeholder for the answer.
    The answer will be filled in when the user responds.
    """
    if state.get("journey_history") is None:
        state["journey_history"] = []
    
    # Store question with empty answer placeholder
    state["journey_history"].append({
        "question": question,
        "answer": None,  # Will be filled when user responds
        "question_type": question_type  # Optional: to identify what was asked
    })
    
    # Keep conversation history manageable (last 50 Q&A pairs)
    if len(state["journey_history"]) > 50:
        state["journey_history"] = state["journey_history"][-50:]
    
    return state


def _update_last_answer_in_history(state: State, answer: str):
    """
    Update the last question in conversation history with the user's answer.
    """
    if state.get("journey_history") is None or len(state["journey_history"]) == 0:
        return state
    
    # Update the last entry's answer
    state["journey_history"][-1]["answer"] = answer
    
    return state


def _store_system_message(state: State, message: str):
    """
    Store a system message (like empathetic responses) as a complete Q&A entry.
    System messages don't expect user responses, so answer is set to empty string.
    """
    if state.get("journey_history") is None:
        state["journey_history"] = []
    
    # Store system message as complete entry with empty answer
    state["journey_history"].append({
        "question": message,
        "answer": "",  # System messages don't have user responses
        "question_type": "system_message"
    })
    
    # Keep conversation history manageable
    if len(state["journey_history"]) > 50:
        state["journey_history"] = state["journey_history"][-50:]
    
    return state

# Affirmations that must NOT overwrite weight (voice often captures these instead of numbers)
_WEIGHT_AFFIRMATIONS = frozenset(
    {"okay", "ok", "yes", "yeah", "yep", "sure", "alright", "got it", "fine"}
)

# --- Safe field setter to avoid overwriting on Q&A resumes ---
def _set_if_expected(state: dict, expected_last_q: str, field: str) -> None:
    if state.get("last_question") != expected_last_q:
        return
    user_msg = state.get("user_msg", "").strip()
    if field == "age":
        extracted_age = extract_age(user_msg)
        state[field] = extracted_age if extracted_age else user_msg
    elif field == "weight":
        # Reject affirmations (e.g. "Okay") that STT may capture instead of "75"
        um_lower = user_msg.lower().rstrip(".")
        if um_lower in _WEIGHT_AFFIRMATIONS:
            return
        # Must have digits or weight units
        has_digits = bool(re.search(r"\d", user_msg))
        has_units = any(kw in user_msg.lower() for kw in ("kg", "k g", "kgs", "lb", "lbs", "pound"))
        if has_digits or has_units:
            state[field] = user_msg
    else:
        state[field] = user_msg

_WORD_TO_NUM: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100,
}


def parse_number_from_text(text: str) -> Optional[int]:
    """
    Extract a numeric value from text (digits or word numbers).
    Used in voice branches for age/weight parsing.
    """
    if not text or not text.strip():
        return None
    try:
        cleaned = re.sub(r"[^\w\s]", " ", text).lower()
        words = cleaned.split()
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
        for i, word in enumerate(words):
            if word in _WORD_TO_NUM:
                val = _WORD_TO_NUM[word]
                if i + 1 < len(words) and words[i + 1] in _WORD_TO_NUM:
                    val += _WORD_TO_NUM[words[i + 1]]
                if i + 1 < len(words) and words[i + 1] == "hundred":
                    val *= 100
                    if i + 2 < len(words) and words[i + 2] in _WORD_TO_NUM:
                        val += _WORD_TO_NUM[words[i + 2]]
                return val
    except Exception as e:
        logger.warning("parse_number_from_text error: %s", e)
    return None


def _words_to_age(tokens: list[str]) -> Optional[int]:
    """Parse word tokens to age (e.g. 'twenty two' -> 22). Handles 1-120."""
    if not tokens:
        return None
    total = 0
    for t in tokens:
        n = _WORD_TO_NUM.get(t)
        if n is None:
            return None
        if n >= 20:
            total += n
        else:
            total = total * 10 + n if total < 10 else total + n
    return total if 1 <= total <= 120 else None


def _words_to_cm(tokens: list[str]) -> Optional[int]:
    """Parse word tokens to cm (e.g. 'one seventy six' -> 176). Handles 100-250."""
    if not tokens or len(tokens) > 4:
        return None
    nums = [_WORD_TO_NUM.get(t) for t in tokens]
    if any(n is None for n in nums):
        return None
    # "one seventy six" = 100+70+6; "seventy six" = 76; "one hundred seventy six" = 176
    if len(nums) == 3 and nums[0] in (1, 2) and 20 <= nums[1] <= 90 and 1 <= nums[2] <= 9:
        return nums[0] * 100 + nums[1] + nums[2]
    if len(nums) == 2 and 20 <= nums[0] <= 90 and 1 <= nums[1] <= 9:
        return nums[0] + nums[1]
    if len(nums) == 1 and 100 <= nums[0] <= 250:
        return nums[0]
    val = _words_to_age(tokens)
    return val if val and 100 <= val <= 250 else None


def extract_age(text: str) -> Optional[str]:
    """
    Intelligently extract age number from various user input formats.
    
    Handles variations like:
    - "im 22"
    - "twenty two"
    - "hey im 22"
    - "my age is 22"
    - "22"
    - "I'm 22 years old"
    - etc.
    
    Args:
        text: User input text containing age information
        
    Returns:
        Age as string if found, None otherwise
    """
    if not text:
        return None
    
    # Clean and normalize the text
    text_clean = text.strip().lower()
    text_clean = re.sub(r'[^\w\s]', ' ', text_clean)
    text_clean = re.sub(r'\s+', ' ', text_clean)
    text = text_clean
    
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
    pattern5 = r'\b(\d{1,3})\b'
    matches = re.findall(pattern5, text)
    for potential_age in matches:
        age_num = int(potential_age)
        if 1 <= age_num <= 120:
            idx = text.find(potential_age)
            context_start = max(0, idx - 20)
            context_end = min(len(text), idx + 20)
            context = text[context_start:context_end]
            age_indicators = [
                'age', 'old', 'years', 'year', 'turning', 'almost',
                'about', 'around', 'approximately', 'im', "i'm", 'am'
            ]
            if any(indicator in context for indicator in age_indicators):
                return potential_age
            if len(text.split()) <= 5 and not (1900 <= age_num <= 2100):
                return potential_age

    # Pattern 6: Word numbers (e.g. "twenty two", "thirty five")
    # Skip if text clearly describes height/weight (cm, feet, kg, etc.)
    if any(kw in text for kw in ("cm", "centimeter", "feet", "foot", "inch", "meter", "kg", "pound", "lb")):
        return None
    tokens = [t for t in text.split() if t in _WORD_TO_NUM]
    # "one seventy six" parses as 77 via _words_to_age but is height 176 — skip if height-like
    if len(tokens) == 3:
        cm_val = _words_to_cm(tokens)
        if cm_val is not None:
            return None
    if 1 <= len(tokens) <= 3:
        age_val = _words_to_age(tokens)
        if age_val is not None:
            return str(age_val)

    return None

# --- LLM ---
llm = ChatBedRockLLM(temperature=0)

def calculate_bmi(height_cm: float, weight_kg: float) -> tuple:
    """Calculate BMI and return feedback."""
    bmi = weight_kg / ((height_cm / 100) ** 2)
    
    if bmi < 18.5:
        feedback = "underweight range. Let's work on nourishing your body!"
    elif 18.5 <= bmi < 25:
        feedback = "healthy range. Great job maintaining your health!"
    elif 25 <= bmi < 30:
        feedback = "overweight range. We can work together on a balanced approach."
    else:
        feedback = "obese range. I'm here to support you with gentle, sustainable changes."
    
    return round(bmi, 1), feedback

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

        # Voice: "one seventy six centimeters" — convert word numbers to digits when cm present
        if any(kw in height_str for kw in ("cm", "centimeter", "centimeters", "meter", "metre")):
            tokens = [t for t in re.sub(r"[^\w\s]", " ", height_str).split() if t in _WORD_TO_NUM]
            if 1 <= len(tokens) <= 4:
                h_val = _words_to_cm(tokens)
                if h_val is None:
                    a = _words_to_age(tokens)
                    h_val = a if a and 100 <= a <= 250 else None
                if h_val is not None:
                    word_seq = " ".join(tokens)
                    height_str = height_str.replace(word_seq, str(h_val), 1).strip()

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
        
        # Check if it's feet/inches format
        has_feet_indicator = any(
            indicator in height_str 
            for indicator in ["'", '"', 'feet', 'foot', 'ft', '\u2032', '\u2033', 
                             '\u2018', '\u2019', '\u201c', '\u201d', '`', '´', '′']
        )
        
        if has_feet_indicator:
            # Pattern 1: 5'10 or 5'10" or 5′10″ (with various apostrophe types)
            # Matches: feet[apostrophe]inches
            match = re.search(r"(\d+)\s*['\"\u2018\u2019\u2032\u2033\u201c\u201d`´′]\s*(\d+)", height_str)
            
            if not match:
                # Pattern 2: 5 feet 10, 5ft 10, 5foot10
                # Matches: feet[word]inches
                match = re.search(r"(\d+)\s*(?:feet|foot|ft)\s*(\d+)", height_str)
            
            if not match:
                # Pattern 3: Just feet with no inches (5', 5 feet, 6')
                # Matches: feet[apostrophe or word] with no inches
                match = re.search(r"(\d+)\s*(?:['\"\u2018\u2019\u2032\u2033\u201c\u201d`´′]|feet|foot|ft)\s*$", height_str)
            
            if match:
                feet = float(match.group(1))
                # Check if we captured inches (group 2 exists and is not None)
                inches = float(match.group(2)) if match.lastindex >= 2 and match.group(2) else 0
                height_cm = (feet * 30.48) + (inches * 2.54)
                
                # Validate reasonable height in feet (3' to 8')
                if not (3 <= feet <= 8):
                    return None, None
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

        # Voice: "seventy five k g" — convert word numbers to digits when kg/lb present
        if any(kw in weight_str for kw in ("kg", "k g", "kgs", "kilogram", "lb", "lbs", "pound")):
            tokens = [t for t in re.sub(r"[^\w\s]", " ", weight_str).split() if t in _WORD_TO_NUM]
            if 1 <= len(tokens) <= 4:
                w_val = _words_to_age(tokens)
                if w_val is not None and 20 <= w_val <= 300:
                    # Replace word sequence with numeric (e.g. "seventy five k g" -> "75 k g")
                    word_seq = " ".join(tokens)
                    weight_str = weight_str.replace(word_seq, str(w_val), 1).strip()

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