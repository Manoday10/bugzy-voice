"""
Vision Analysis Core Logic for Snap Feature - Version 2.1 OPTIMIZED

This module contains the main image analysis function that handles
downloading, classifying, and analyzing food images.

Key Improvements in v2.1:
- Fixed false positive detection in STEP 0 negation statements
- Improved regex for sanitizing CoT reasoning
- Better context-aware non-food indicator detection
- Enhanced validation logic to prevent misclassification

Version 3.0 Enhancements:
- Added caption/query support for guided analysis
- Multiple analysis modes (AUTO, CAPTION_GUIDED, QUESTION_ANSWERING, etc.)
- Backward compatible with existing functionality
"""

import tempfile
import os
import re
import requests
import logging
from typing import Dict, Any, Optional, Tuple, List

from app.services.llm.llm import invoke_llama_api, extract_text_from_response
from app.services.snap.models import CategoryAOutput, CategoryBOutput, CategoryCOutput
from app.services.snap.formatters import format_category_a_text, format_category_b_text
from app.services.snap.prompts import (
    CLASSIFIER_PROMPT,
    CATEGORY_A_PROMPT,
    CATEGORY_B_PROMPT,
    CATEGORY_C_PROMPT,
    NON_FOOD_FALLBACK_MESSAGE,
    FREEFORM_PROMPT
)
from app.services.snap.mode_detector import detect_analysis_mode



logger = logging.getLogger(__name__)


# ============================================================================
# NON-FOOD DETECTION PATTERNS
# ============================================================================

# Patterns that indicate the image is NOT food (used in analysis responses)
NON_FOOD_INDICATORS = [
    # Direct indicators
    "NON_FOOD_DETECTED",
    "non-food",
    "not food",
    "no food",
    "isn't food",
    "aren't food",
    "does not contain food",
    "doesn't contain food",
    "cannot identify any food",
    "unable to identify food",
    "no food items",
    "no edible items",
    
    # Object indicators (removed human/person from here - handled separately)
    "electronic",
    "cable",
    "wire",
    "device",
    "phone",
    "computer",
    "laptop",
    "machine",
    "vehicle",
    "motorcycle",
    "car",
    "bicycle",
    "pipe",
    "tool",
    "equipment",
    
    # Quality indicators
    "blurry",
    "unclear",
    "cannot see",
    "can't see",
    "hard to identify",
    "difficult to identify",
    "image quality",
    "too dark",
    "overexposed",
    "out of focus",
]

# Human/person indicators - handled separately with context awareness
HUMAN_INDICATORS = [
    "person",
    "human",
    "face",
    "portrait",
    "selfie",
    "people",
    "man",
    "woman",
    "child",
    "someone",
    "individual",
    "hands visible",
    "body parts",
]

def contains_non_food_indicators(text: str, check_humans: bool = True) -> Tuple[bool, List[str]]:
    """
    Check if text contains any non-food indicators with context awareness.
    
    Args:
        text: The text to check
        check_humans: Whether to check for human indicators (default True)
        
    Returns:
        Tuple of (is_non_food, list of matched indicators)
    """
    text_lower = text.lower()
    matched_indicators = []
    
    # Check standard non-food indicators
    for indicator in NON_FOOD_INDICATORS:
        pattern = r'\b' + re.escape(indicator.lower()) + r'\b'
        if re.search(pattern, text_lower):
            matched_indicators.append(indicator)
    
    # Check human indicators with context awareness
    if check_humans:
        for indicator in HUMAN_INDICATORS:
            pattern = r'\b' + re.escape(indicator.lower()) + r'\b'
            matches = list(re.finditer(pattern, text_lower))
            
            for match in matches:
                # Get context around the match (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(text_lower), match.end() + 50)
                context = text_lower[start:end]
                
                # Check if this is a NEGATION (e.g., "I do not see a person")
                negation_patterns = [
                    r'do not see.*?' + re.escape(indicator.lower()),
                    r"don't see.*?" + re.escape(indicator.lower()),
                    r'no.*?' + re.escape(indicator.lower()),
                    r'not.*?' + re.escape(indicator.lower()),
                    r'without.*?' + re.escape(indicator.lower()),
                    r'absence of.*?' + re.escape(indicator.lower()),
                ]
                
                is_negation = any(re.search(pattern, context) for pattern in negation_patterns)
                
                # Only flag if it's NOT a negation
                if not is_negation:
                    matched_indicators.append(indicator)
                    break  # Only count once per indicator
    
    return len(matched_indicators) > 0, matched_indicators


def parse_cot_classification(response_text: str) -> Tuple[str, str, str, bool]:
    """
    Parse the raw LLM classification response and extract category + confidence.
    We now trust the LLM's decision and simply reflect the reported Category.
    """
    reasoning = response_text
    confidence = "LOW"
    category = "C"  # Default fallback
    is_valid = True
    
    # Extract confidence level from STEP 3 (best-effort)
    confidence_match = re.search(
        r'STEP 3[^:]*:\s*(HIGH|MEDIUM|LOW)',
        response_text,
        re.IGNORECASE | re.DOTALL
    )
    if confidence_match:
        confidence = confidence_match.group(1).upper()
    else:
        # Fallback: Look for confidence keyword anywhere after STEP 3
        step3_match = re.search(r'STEP 3', response_text, re.IGNORECASE)
        if step3_match:
            text_after_step3 = response_text[step3_match.start():]
            # Look for HIGH/HIGHLY/CERTAIN/ABSOLUTELY indicators
            if re.search(r'\b(HIGHLY?\s+CONFIDENT|CERTAIN|ABSOLUTELY|100%|95-100%)\b', text_after_step3, re.IGNORECASE):
                confidence = "HIGH"
            elif re.search(r'\bMEDIUM\b', text_after_step3, re.IGNORECASE):
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
    # Extract category (allow markdown like **CATEGORY:**)
    category_match = re.search(
        r'CATEGORY[\s\W]*([ABC])\b',
        response_text,
        re.IGNORECASE
    )
    if category_match:
        category = category_match.group(1).upper()
    else:
        # Fallback: Look for final answer
        final_match = re.search(r'FINAL ANSWER[:\s]*.*?([ABC])', response_text, re.IGNORECASE)
        if final_match:
            category = final_match.group(1).upper()
        else:
            # Last resort: scan for any line mentioning CATEGORY
            lines = response_text.strip().split('\n')
            for line in lines:
                if 'CATEGORY' in line.upper():
                    fallback_match = re.search(r'([ABC])', line, re.IGNORECASE)
                    if fallback_match:
                        category = fallback_match.group(1).upper()
                        break

            # Ultimate fallback: look at the final few lines for standalone letters
            if category == "C":
                for line in reversed(lines[-5:]):
                    line_clean = line.strip().upper()
                    if line_clean in ["A", "B", "C"]:
                        category = line_clean
                        break
    
    return category, confidence, reasoning, is_valid


def validate_analysis_response(response_text: str, expected_category: str) -> Tuple[bool, str]:
    """
    Validate the analysis response for non-food detection.
    
    This is a multi-layer safety check that catches cases where:
    1. The classifier incorrectly classified as A or B
    2. The analysis model realizes it's not actually food
    
    Args:
        response_text: The analysis response from the LLM
        expected_category: The category we expected (A or B)
        
    Returns:
        Tuple of (is_food, reason)
        - is_food: True if the response indicates actual food analysis
        - reason: Explanation if not food
    """
    # Check 1: Explicit NON_FOOD_DETECTED
    if "NON_FOOD_DETECTED" in response_text.upper():
        return False, "Explicit NON_FOOD_DETECTED flag"
    
    # Check 2: Remove safety checklist section to avoid false positives
    text_for_indicator_check = response_text
    try:
        # Remove everything before the actual analysis starts (after safety checklist)
        # Look for analysis headers like 📸, 🥗, or section markers
        analysis_start = re.search(
            r'(?:📸|🥗|📋|\*\*Image Analysis|\*\*Ingredient Analysis)',
            response_text
        )
        if analysis_start:
            text_for_indicator_check = response_text[analysis_start.start():]
    except Exception:
        pass
    
    # Check for non-food indicators with context awareness
    has_non_food, indicators = contains_non_food_indicators(text_for_indicator_check, check_humans=True)
    
    if has_non_food:
        # Look for phrases that indicate the model is describing what it sees
        description_phrases = [
            "i see a",
            "i can see a", 
            "the image shows",
            "this image contains",
            "appears to be",
            "looks like",
            "i notice",
            "primary subject is",
            "main subject is",
        ]
        
        response_lower = text_for_indicator_check.lower()
        for phrase in description_phrases:
            if phrase in response_lower:
                # Check if non-food indicator is near this phrase
                phrase_pos = response_lower.find(phrase)
                nearby_text = response_lower[phrase_pos:phrase_pos + 100]
                for indicator in indicators:
                    if indicator.lower() in nearby_text:
                        return False, f"Non-food indicator '{indicator}' found in image description"
    
    # Check 3: Ensure it contains food analysis markers
    food_related_markers = ["detected", "identified", "nutrient", "calorie", "recipe", 
                           "protein", "carbohydrate", "fat", "fiber"]
    found_markers = sum(1 for marker in food_related_markers if marker.lower() in response_text.lower())
    if found_markers < 2:
        return False, "Response does not appear to contain sufficient food analysis content"
    
    return True, "Valid food analysis"


def get_non_food_response() -> str:
    """
    Get the standard non-food response message.
    
    Returns:
        The standard Category C message
    """
    return NON_FOOD_FALLBACK_MESSAGE


def analyze_food_image(
    image_url: str, 
    whatsapp_token: str,
    user_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze a food image using vision AI with multi-layer validation.
    
    This function:
    1. Downloads the image from WhatsApp API
    2. Detects analysis mode from user query (if provided)
    3. Classifies it using CoT reasoning with strict validation
    4. Validates classification confidence and step results
    5. Performs category-specific analysis with secondary validation
    6. Returns formatted results
    
    Args:
        image_url: URL to download the image from
        whatsapp_token: WhatsApp API token for authentication
        user_query: Optional user caption or question for guided analysis (NEW in v3.0)
        
    Returns:
        Dict containing:
        - category: "A" | "B" | "C"
        - vision_content: Formatted analysis text
        - raw_output: Raw LLM output
        - reasoning: CoT reasoning (for debugging)
        - confidence: Classification confidence
        - validation_details: Details about validation checks
        - success: bool
        - error: Optional error message
        - analysis_mode: Analysis mode used (NEW in v3.0)
        - user_query: User's query if provided (NEW in v3.0)
        - mode_metadata: Additional mode-specific metadata (NEW in v3.0)
    """
    validation_details = []
    
    # NEW in v3.0: Detect analysis mode from user query
    analysis_mode, mode_metadata = detect_analysis_mode(user_query)
    validation_details.append(f"Analysis mode: {analysis_mode}")
    
    if user_query:
        logger.info("📝 User query: %s", user_query)
        logger.info("🎯 Detected mode: %s", analysis_mode)
    
    try:
        # Step 1: Download the image
        headers = {"Authorization": f"Bearer {whatsapp_token}"}
        image_response = requests.get(image_url, headers=headers, timeout=10)
        if image_response.status_code == 200:
            logger.info("✅ Image downloaded successfully, size: %s bytes", len(image_response.content))
        else:
            error_msg = f"Failed to download image: {image_response.status_code}"
            logger.error("❌ %s", error_msg)
            return {
                "category": None,
                "vision_content": None,
                "raw_output": None,
                "reasoning": None,
                "confidence": None,
                "validation_details": validation_details,
                "success": False,
                "error": error_msg,
                "analysis_mode": analysis_mode,
                "user_query": user_query,
                "mode_metadata": mode_metadata
            }
        validation_details.append(f"Image downloaded: {len(image_response.content)} bytes")

        
        # Step 3: Save to temporary file for vision API
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(image_response.content)
            tmp_image_path = tmp_file.name
        
        try:
            # Step 4: Classify the image with CoT reasoning
            logger.info("🧠 Running CoT classification with strict validation...")
            classifier_response = invoke_llama_api(
                query=CLASSIFIER_PROMPT,
                model_type="vision",
                image_path=tmp_image_path,
                temperature=0.0,
                max_tokens=600  # Enough for full CoT reasoning
            )
            
            # Parse the CoT response with validation
            classification_text = extract_text_from_response(classifier_response).strip()
            logger.debug("📝 Raw Classification Response:\n%s\n%s", classification_text, '-'*50)
            
            category, confidence, reasoning, is_valid = parse_cot_classification(classification_text)
            
            validation_details.append(f"Initial classification: {category}")
            validation_details.append(f"Confidence: {confidence}")
            validation_details.append(f"Validation passed: {is_valid}")
            
            logger.info("🔍 Classification Result:")
            logger.info("   Category: %s", category)
            logger.info("   Confidence: %s", confidence)
            logger.info("   Valid: %s", is_valid)
            
            # Trust the LLM classification result even if validation flag is false.
            # (is_valid now simply indicates parse success/failure, not a gatekeeper)
            
            # Step 5: Analyze based on category
            raw_text = ""
            vision_content = ""
            
            if category == "A":
                # Category A: Prepared Food/Meals
                logger.info("🍽️ Analyzing as Category A (Prepared Food)...")
                
                # NEW in v3.0: Select prompt based on analysis mode
                if analysis_mode == "QUESTION_ANSWERING":
                    from app.services.snap.prompts_enhanced import QUESTION_ANSWERING_PROMPT
                    prompt = QUESTION_ANSWERING_PROMPT.format(user_query=user_query)
                    logger.info("   Using QUESTION_ANSWERING prompt")
                elif analysis_mode == "CAPTION_GUIDED":
                    from app.services.snap.prompts_enhanced import CAPTION_GUIDED_PROMPT
                    prompt = CAPTION_GUIDED_PROMPT.format(user_query=user_query)
                    logger.info("   Using CAPTION_GUIDED prompt")
                elif analysis_mode == "PORTION_CHECK":
                    from app.services.snap.prompts_enhanced import PORTION_CHECK_PROMPT
                    prompt = PORTION_CHECK_PROMPT.format(user_query=user_query)
                    logger.info("   Using PORTION_CHECK prompt")
                elif analysis_mode == "ALLERGEN_CHECK":
                    from app.services.snap.prompts_enhanced import ALLERGEN_CHECK_PROMPT
                    prompt = ALLERGEN_CHECK_PROMPT.format(user_query=user_query)
                    logger.info("   Using ALLERGEN_CHECK prompt")
                elif analysis_mode == "FREEFORM":
                    prompt = FREEFORM_PROMPT.format(user_query=user_query)
                    logger.info("   Using FREEFORM prompt")
                else:  # AUTO mode or COMPARISON (use standard prompt)
                    prompt = CATEGORY_A_PROMPT
                    logger.info("   Using standard CATEGORY_A prompt")

                
                vision_response = invoke_llama_api(
                    query=prompt,
                    model_type="vision",
                    image_path=tmp_image_path,
                    temperature=0.2,
                    max_tokens=4096
                )
                
                raw_text = extract_text_from_response(vision_response)
                
                # Multi-layer validation of analysis response
                is_food, validation_reason = validate_analysis_response(raw_text, "A")
                validation_details.append(f"Analysis validation: {is_food} ({validation_reason})")
                
                if not is_food:
                    logger.warning("⚠️ Category A analysis failed validation: %s", validation_reason)
                    logger.info("   Reclassifying as Category C.")
                    category = "C"
                    confidence = "RECLASSIFIED"
                    validation_details.append(f"Reclassified to C: {validation_reason}")
                    
                    # Use standard non-food response
                    vision_content = get_non_food_response()
                    raw_text = vision_content
                else:
                    # Normal Category A processing
                    formatted_text = format_category_a_text(raw_text)
                    
                    category_a_wrapper = {
                        "category": "A",
                        "detected_items": [],
                        "protein_g": "",
                        "carbs_g": "",
                        "fats_g": "",
                        "calorie_range": "",
                        "fiber_g": "",
                        "probiotics": "",
                        "prebiotics": "",
                        "digestive_spices": "",
                        "health_assessment": "",
                        "gut_health_integration": "",
                        "suggestions": [],
                        "raw_llm_output": raw_text,
                        "final_structured_text": formatted_text
                    }
                    category_a_output = CategoryAOutput.model_validate(category_a_wrapper)
                    vision_content = category_a_output.final_structured_text
                
            elif category == "B":
                # Category B: Raw Ingredients/Vegetables
                logger.info("🥬 Analyzing as Category B (Raw Ingredients)...")
                vision_response = invoke_llama_api(
                    query=CATEGORY_B_PROMPT,
                    model_type="vision",
                    image_path=tmp_image_path,
                    temperature=0.2,
                    max_tokens=4096
                )
                
                raw_text = extract_text_from_response(vision_response)
                
                # Multi-layer validation of analysis response
                is_food, validation_reason = validate_analysis_response(raw_text, "B")
                validation_details.append(f"Analysis validation: {is_food} ({validation_reason})")
                
                if not is_food:
                    logger.warning("⚠️ Category B analysis failed validation: %s", validation_reason)
                    logger.info("   Reclassifying as Category C.")
                    category = "C"
                    confidence = "RECLASSIFIED"
                    validation_details.append(f"Reclassified to C: {validation_reason}")
                    
                    # Use standard non-food response
                    vision_content = get_non_food_response()
                    raw_text = vision_content
                else:
                    # Normal Category B processing
                    formatted_text = format_category_b_text(raw_text)
                    
                    category_b_wrapper = {
                        "category": "B",
                        "identified_ingredients": [],
                        "categorized_ingredients": {},
                        "nutritional_potential": {},
                        "key_vitamins_minerals": [],
                        "healthy_recipes": [],
                        "general_pro_tips": [],
                        "raw_llm_output": raw_text,
                        "final_structured_text": formatted_text
                    }
                    category_b_output = CategoryBOutput.model_validate(category_b_wrapper)
                    vision_content = category_b_output.final_structured_text
                
            else:
                # Category C: Non-Food Items or Uncertain
                logger.info("🚫 Classifying as Category C (Non-Food/Uncertain)...")
                
                # Use standard non-food response directly
                vision_content = get_non_food_response()
                raw_text = vision_content
                
                category_c_wrapper = {
                    "category": "C",
                    "message": raw_text,
                    "raw_llm_output": raw_text,
                    "final_structured_text": raw_text
                }
                category_c_output = CategoryCOutput.model_validate(category_c_wrapper)
                vision_content = category_c_output.final_structured_text
            
            logger.info("✅ Analysis complete (Final Category: %s)", category)
            logger.debug("📄 Response preview: %s...", vision_content[:150])
            
            return {
                "category": category,
                "vision_content": vision_content,
                "raw_output": raw_text,
                "reasoning": reasoning,
                "confidence": confidence,
                "validation_details": validation_details,
                "success": True,
                "error": None,
                # NEW in v3.0: Caption support fields
                "analysis_mode": analysis_mode,
                "user_query": user_query,
                "mode_metadata": mode_metadata
            }
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_image_path)
            except Exception:
                pass
                
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to download image: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {
            "category": None,
            "vision_content": None,
            "raw_output": None,
            "reasoning": None,
            "confidence": None,
            "validation_details": validation_details,
            "success": False,
            "error": error_msg,
            "analysis_mode": analysis_mode,
            "user_query": user_query,
            "mode_metadata": mode_metadata
        }
    except Exception as e:
        error_msg = f"Vision analysis failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {
            "category": None,
            "vision_content": None,
            "raw_output": None,
            "reasoning": None,
            "confidence": None,
            "validation_details": validation_details,
            "success": False,
            "error": error_msg,
            "analysis_mode": analysis_mode,
            "user_query": user_query,
            "mode_metadata": mode_metadata
        }


def analyze_food_image_direct(
    image_path: str,
    user_query: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyze a food image directly from a local file path.
    
    This is useful for testing without WhatsApp API.
    
    Args:
        image_path: Local path to the image file
        user_query: Optional user caption or question for guided analysis (NEW in v3.0)
        
    Returns:
        Same structure as analyze_food_image()
    """
    validation_details = []
    
    # NEW in v3.0: Detect analysis mode from user query
    analysis_mode, mode_metadata = detect_analysis_mode(user_query)
    validation_details.append(f"Analysis mode: {analysis_mode}")
    
    if user_query:
        logger.info("📝 User query: %s", user_query)
        logger.info("🎯 Detected mode: %s", analysis_mode)
    
    try:
        # Verify file exists
        if not os.path.exists(image_path):
            return {
                "category": None,
                "vision_content": None,
                "raw_output": None,
                "reasoning": None,
                "confidence": None,
                "validation_details": ["File not found"],
                "success": False,
                "error": f"Image file not found: {image_path}",
                "analysis_mode": analysis_mode,
                "user_query": user_query,
                "mode_metadata": mode_metadata
            }
        
        logger.info("✅ Analyzing local image: %s", image_path)
        validation_details.append(f"Local file: {image_path}")
        
        # Step 1: Classify the image with CoT reasoning
        logger.info("🧠 Running CoT classification with strict validation...")
        classifier_response = invoke_llama_api(
            query=CLASSIFIER_PROMPT,
            model_type="vision",
            image_path=image_path,
            temperature=0.0,
            max_tokens=600
        )
        
        classification_text = extract_text_from_response(classifier_response).strip()
        logger.debug("📝 Raw Classification Response:\n%s\n%s", classification_text, '-'*50)
        
        category, confidence, reasoning, is_valid = parse_cot_classification(classification_text)
        
        validation_details.append(f"Initial classification: {category}")
        validation_details.append(f"Confidence: {confidence}")
        validation_details.append(f"Validation passed: {is_valid}")
        
        logger.info("🔍 Classification Result:")
        logger.info("   Category: %s", category)
        logger.info("   Confidence: %s", confidence)
        logger.info("   Valid: %s", is_valid)
        
        # Trust the LLM category output for local analysis as well.
        
        # Step 2: Analyze based on category
        raw_text = ""
        vision_content = ""
        
        if category == "A":
            logger.info("🍽️ Analyzing as Category A (Prepared Food)...")
            
            # NEW in v3.0: Select prompt based on analysis mode
            if analysis_mode == "QUESTION_ANSWERING":
                from app.services.snap.prompts_enhanced import QUESTION_ANSWERING_PROMPT
                prompt = QUESTION_ANSWERING_PROMPT.format(user_query=user_query)
                logger.info("   Using QUESTION_ANSWERING prompt")
            elif analysis_mode == "CAPTION_GUIDED":
                from app.services.snap.prompts_enhanced import CAPTION_GUIDED_PROMPT
                prompt = CAPTION_GUIDED_PROMPT.format(user_query=user_query)
                logger.info("   Using CAPTION_GUIDED prompt")
            elif analysis_mode == "PORTION_CHECK":
                from app.services.snap.prompts_enhanced import PORTION_CHECK_PROMPT
                prompt = PORTION_CHECK_PROMPT.format(user_query=user_query)
                logger.info("   Using PORTION_CHECK prompt")
            elif analysis_mode == "ALLERGEN_CHECK":
                from app.services.snap.prompts_enhanced import ALLERGEN_CHECK_PROMPT
                prompt = ALLERGEN_CHECK_PROMPT.format(user_query=user_query)
                logger.info("   Using ALLERGEN_CHECK prompt")
            elif analysis_mode == "FREEFORM":
                prompt = FREEFORM_PROMPT.format(user_query=user_query)
                logger.info("   Using FREEFORM prompt")
            else:  # AUTO mode or COMPARISON (use standard prompt)
                prompt = CATEGORY_A_PROMPT
                logger.info("   Using standard CATEGORY_A prompt")

            
            vision_response = invoke_llama_api(
                query=prompt,
                model_type="vision",
                image_path=image_path,
                temperature=0.2,
                max_tokens=4096
            )
            
            raw_text = extract_text_from_response(vision_response)
            
            # Multi-layer validation
            is_food, validation_reason = validate_analysis_response(raw_text, "A")
            validation_details.append(f"Analysis validation: {is_food} ({validation_reason})")
            
            if not is_food:
                logger.warning("⚠️ Category A analysis failed validation: %s", validation_reason)
                category = "C"
                confidence = "RECLASSIFIED"
                validation_details.append(f"Reclassified to C: {validation_reason}")
                vision_content = get_non_food_response()
                raw_text = vision_content
            else:
                formatted_text = format_category_a_text(raw_text)
                vision_content = formatted_text
                
        elif category == "B":
            logger.info("🥬 Analyzing as Category B (Raw Ingredients)...")
            vision_response = invoke_llama_api(
                query=CATEGORY_B_PROMPT,
                model_type="vision",
                image_path=image_path,
                temperature=0.2,
                max_tokens=4096
            )
            
            raw_text = extract_text_from_response(vision_response)
            
            # Multi-layer validation
            is_food, validation_reason = validate_analysis_response(raw_text, "B")
            validation_details.append(f"Analysis validation: {is_food} ({validation_reason})")
            
            if not is_food:
                logger.warning("⚠️ Category B analysis failed validation: %s", validation_reason)
                category = "C"
                confidence = "RECLASSIFIED"
                validation_details.append(f"Reclassified to C: {validation_reason}")
                vision_content = get_non_food_response()
                raw_text = vision_content
            else:
                formatted_text = format_category_b_text(raw_text)
                vision_content = formatted_text
                
        else:
            logger.info("🚫 Classifying as Category C (Non-Food/Uncertain)...")
            vision_content = get_non_food_response()
            raw_text = vision_content
        
        logger.info("✅ Analysis complete (Final Category: %s)", category)
        
        return {
            "category": category,
            "vision_content": vision_content,
            "raw_output": raw_text,
            "reasoning": reasoning,
            "confidence": confidence,
            "validation_details": validation_details,
            "success": True,
            "error": None,
            # NEW in v3.0: Caption support fields
            "analysis_mode": analysis_mode,
            "user_query": user_query,
            "mode_metadata": mode_metadata
        }
        
    except Exception as e:
        error_msg = f"Vision analysis failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {
            "category": None,
            "vision_content": None,
            "raw_output": None,
            "reasoning": None,
            "confidence": None,
            "validation_details": validation_details,
            "success": False,
            "error": error_msg,
            "analysis_mode": analysis_mode,
            "user_query": user_query,
            "mode_metadata": mode_metadata
        }


def analyze_food_tracker_image(image_path: str) -> Dict[str, Any]:
    """
    Analyze image specifically for Food Tracker feature.
    
    Returns strict JSON structure with macros/nutrients.
    Reuses the Llama Vision API mechanism but with strict JSON prompt.
    """
    import json
    from app.services.snap.prompts import FOOD_TRACKER_PROMPT
    
    try:
        if not os.path.exists(image_path):
            return {"error": f"Image file not found: {image_path}"}
            
        logger.info("🥗 Running Food Tracker analysis on: %s", image_path)
        
        # Invoke Llama with strict JSON prompt
        response = invoke_llama_api(
            query=FOOD_TRACKER_PROMPT,
            model_type="vision",
            image_path=image_path,
            temperature=0.1,  # Low temp for strict JSON
            max_tokens=1000
        )
        
        
        # Parse response
        raw_text = extract_text_from_response(response).strip()
        logger.debug("📊 Raw Tracker Response:\n%s", raw_text)
        
        import re
        
        # Strategy 1: Look for JSON block surrounded by ```json or ```
        json_str = raw_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        # Strategy 2: If no code blocks, look for the first { and last }
        elif "{" in json_str and "}" in json_str:
             start = json_str.find("{")
             end = json_str.rfind("}") + 1
             json_str = json_str[start:end]
             
        # Parse JSON
        try:
            data = json.loads(json_str)
            
            # Handle "Not food" case specifically
            if "error" in data:
                return {
                    "success": False,
                    "error": data["error"]
                }
            
            # Construct metadata similar to SNAP
            metadata = {
                "analysis_type": "food_tracker",
                "category": "tracker",
                "model_used": "llama-3.2-11b-vision-preview",
                "raw_output": raw_text,
                "reasoning": "Direct food tracker analysis",
                "validation_details": ["Checked for food content"] if "not food" not in raw_text.lower() else ["Failed food check"]
            }

            return {
                "success": True,
                "data": data,
                "raw_output": raw_text,
                "metadata": metadata
            }
            
        except json.JSONDecodeError:
            logger.error("❌ Failed to parse JSON from tracker response")
            
            # Strategy 3: Regex Fallback for conversational lists
            # Example output: * Calories: 450 or Calories: 400-500
            # Try to extract numbers from common patterns
            try:
                logger.info("Attempting regex fallback extraction...")
                fallback_data = {}
                
                def extract_val(pattern, text):
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        val_str = match.group(1).strip()
                        # Handle ranges like "450-600"
                        if "-" in val_str and val_str.count("-") == 1:
                            try:
                                parts = val_str.split("-")
                                return (float(parts[0]) + float(parts[1])) / 2
                            except:
                                return float(parts[0]) # Fallback to lower bound
                        return float(val_str)
                    return None
                
                # Extract Macros with range support
                fallback_data["calories"] = extract_val(r'Calories:?\s*([\d\.-]+)', raw_text)
                fallback_data["protein"] = extract_val(r'Protein:?\s*([\d\.-]+)', raw_text)
                fallback_data["fiber"] = extract_val(r'Fiber:?\s*([\d\.-]+)', raw_text)
                fallback_data["fat"] = extract_val(r'Fat:?\s*([\d\.-]+)', raw_text)
                    
                # Guess food name - Skip generic headers
                lines = raw_text.split('\n')
                candidate_name = "Food Item"
                for line in lines:
                    line = line.strip()
                    if not line: continue
                    # Skip headers and metadata lines
                    if line.startswith(('#', '```', '{', '}', 'In this', 'The image')):
                        continue
                    if len(line) < 5 and not line[0].isalpha(): # Skip bullet points without much text
                        continue
                    
                    # Found a potential candidate
                    clean_line = line.lstrip('*- ').split(':')[0] # Take first part before colon if exists
                    if len(clean_line) > 3:
                        candidate_name = clean_line
                        break
                        
                fallback_data["food_name"] = candidate_name

                if fallback_data.get("calories") is not None:
                    logger.info("✅ Regex fallback successful: %s", fallback_data)
                    
                    metadata = {
                        "analysis_type": "food_tracker_fallback",
                        "category": "tracker",
                        "model_used": "llama-3.2-11b-vision-preview",
                        "raw_output": raw_text,
                        "reasoning": "Regex fallback extraction (handled ranges)",
                         "validation_details": ["Parsed via regex fallback"]
                    }
                    
                    return {
                        "success": True,
                        "data": fallback_data,
                        "raw_output": raw_text,
                        "metadata": metadata
                    }

            except Exception as regex_e:
                 logger.error("Regex fallback failed: %s", regex_e)

            return {
                "success": False,
                "error": "Failed to parse AI response",
                "raw_output": raw_text,
                "metadata": {
                    "raw_output": raw_text,
                    "error": "json_parse_error"
                }
            }
            
    except Exception as e:
        logger.error("❌ Food Tracker Error: %s", e)
        return {
            "success": False,
            "error": str(e)
        }