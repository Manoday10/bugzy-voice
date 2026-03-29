"""
Shared input validation logic for Bugzy chatbots.
"""

import re
import logging
from typing import Dict, Optional, Tuple, Any

from app.services.whatsapp.utils import llm
from app.services.whatsapp.client import send_whatsapp_message

logger = logging.getLogger(__name__)

# Default always valid responses (can be extended)
DEFAULT_ALWAYS_VALID = {
    'health_conditions': {'none', 'no', 'no conditions', 'nothing', 'nil'},
    'health_safety_screening': {'none', 'no', 'no conditions', 'nothing', 'nil'},
    'allergies': {'none', 'no', 'no allergies', 'nothing', 'nil', 'not allergic'},
    'medications': {
        'none', 'no', 'no medications', 'nothing', 'nil', 'n/a', 'na',
        'yes', 'yeah', 'yep', 'yup',
        'not any', 'not taking any', 'no meds',
        'i don\'t take any', 'i\'m not on any', 'idont take any', 'im not on any',
    },
}

def validate_input(
    user_input: str,
    expected_field: str,
    validation_rules: Dict[str, Any],
    always_valid_responses: Optional[Dict[str, set]] = None,
    custom_fallback_guidelines: str = ""
) -> Tuple[bool, str]:
    """
    Validate if user input is appropriate for the expected field.
    
    Args:
        user_input: The text provided by the user
        expected_field: The field name being validated
        validation_rules: Dictionary of rules (valid_options, typo_variations, validation_prompt)
        always_valid_responses: Dictionary of field -> set of valid lowercase strings
        custom_fallback_guidelines: Additional instructions for the fallback LLM prompt
        
    Returns:
        Tuple[bool, str]: (is_valid, reason)
    """
    # Handle empty input
    if not user_input or user_input.strip() == "":
        return False, "Empty response received."

    # Normalize input for better validation
    normalized_input = user_input.strip().lower()
    
    # Merge default and custom always_valid_responses
    valid_responses = DEFAULT_ALWAYS_VALID.copy()
    if always_valid_responses:
        valid_responses.update(always_valid_responses)

    # Check validity based on simple keyword matching
    if expected_field in valid_responses:
        # Use full word matching to avoid partial matches (e.g. "none" matching "nonexistent")
        for response in valid_responses[expected_field]:
            if response == normalized_input or re.search(r'\\b' + re.escape(response) + r'\\b', normalized_input):
                return True, "Valid 'none' response for this field"

    # Check if we have specific validation rules for this field
    if expected_field in validation_rules:
        validation_config = validation_rules[expected_field]
        
        # Check for typo variations if available
        if "typo_variations" in validation_config and "valid_options" in validation_config:
            # Check typo variations
            for option, variations in validation_config.get("typo_variations", {}).items():
                if any(variation in normalized_input for variation in variations):
                    return True, f"Valid {option} response (matched variation)"
            
            # Check direct matches with valid options
            if any(option in normalized_input for option in validation_config.get("valid_options", [])):
                return True, "Valid response matching expected options"
        
        # Use the specific validation prompt for this field
        if "validation_prompt" in validation_config:
            validation_prompt = validation_config["validation_prompt"].format(input=user_input)
            
            try:
                response = llm.invoke(validation_prompt).content.strip()
                lines = [line.strip() for line in response.split('\n') if line.strip()]

                if not lines:
                    return False, "No validation response received."

                first_line = lines[0].upper()
                is_valid = first_line.startswith('VALID')
                reason = lines[1] if len(lines) > 1 else ("Accepted." if is_valid else "Invalid.")

                return is_valid, reason
            except Exception as e:
                logger.error(f"LLM validation error for {expected_field}: {e}")
                return False, f"Validation error: {str(e)}"
    
    # Fallback to generic validation
    fallback_validation_prompt = f"""
    You are validating user input for a comprehensive health and meal planning questionnaire.
    BE EXTREMELY FLEXIBLE AND USER-FRIENDLY in your validation. When in doubt, accept the input if it has any relevant information.

    Question field: {expected_field}
    User response: "{user_input}"

    Is this response appropriate and informative for the {expected_field} field?

    Respond with exactly one word: "VALID" or "INVALID"
    Then on the next line, explain why in one sentence.

    Guidelines:
    {custom_fallback_guidelines}
    - Health conditions: Accept ANY medical terms, "none", "no", "diabetes", "hypertension", etc.
    - Medications: Accept ANY medication terms, "none", "no", "aspirin", "ibuprofen", etc.

    IMPORTANT RULES:
    1. For "none/no" responses: ALWAYS accept for allergies, health conditions, and medications
    2. Be extremely forgiving with typos and informal language
    3. When in doubt, choose VALID
    """

    try:
        response = llm.invoke(fallback_validation_prompt).content.strip()
        lines = [line.strip() for line in response.split('\n') if line.strip()]

        if not lines:
            return False, "No validation response received."

        first_line = lines[0].upper()
        # More robust check: valid if it starts with VALID
        is_valid = first_line.startswith('VALID')
        reason = lines[1] if len(lines) > 1 else ("Accepted." if is_valid else "Invalid.")

        return is_valid, reason
    except Exception as e:
        logger.error(f"Fallback validation error for {expected_field}: {e}")
        return False, f"Validation error: {str(e)}"

def handle_validated_input(
    state: Dict,
    expected_field: str,
    validation_rules: Dict[str, Any],
    field_feedback_map: Optional[Dict[str, str]] = None,
    always_valid_responses: Optional[Dict[str, set]] = None,
    custom_fallback_guidelines: str = "",
    max_attempts: int = 3
) -> str:
    """
    Handle validated input with improved error messaging based on field type.
    
    Args:
        state: Conversation state
        expected_field: Field to validate
        validation_rules: Validation rules configuration
        field_feedback_map: Dictionary mapping field names to specific error messages
        always_valid_responses: Override for always valid responses
        custom_fallback_guidelines: Guidelines for fallback LLM check
        max_attempts: Max retry attempts before forced acceptance
        
    Returns:
        str: 'valid', 'retry', or 'accepted' (forced)
    """
    user_input = state.get("user_msg", "").strip()
    validation_key = f"{expected_field}_validation_attempts"
    attempts = state.get(validation_key, 0)

    is_valid, reason = validate_input(
        user_input, 
        expected_field, 
        validation_rules, 
        always_valid_responses, 
        custom_fallback_guidelines
    )
    
    if is_valid:
        if validation_key in state:
            del state[validation_key]
        return "valid"
    else:
        attempts += 1
        state[validation_key] = attempts
        if attempts < max_attempts:
            # Deterministic conversational openers
            openers = [
                "I didn't quite catch that.",
                "Quick check — can you share that again?",
                "Just to confirm — what should I note here?",
                "Sorry, I may have missed that.",
            ]
            opener = openers[(attempts - 1) % len(openers)]

            feedback_message = f"{opener}\nCould you say it a bit differently?"
            
            # Use specific feedback if available
            if field_feedback_map and expected_field in field_feedback_map:
                try:
                    # Attempt to format with user_input if the template expects it
                    formatted_feedback = field_feedback_map[expected_field].format(user_input=user_input)
                except KeyError:
                    # Fallback if the map string doesn't use {user_input} or uses other keys
                    formatted_feedback = field_feedback_map[expected_field]
                    
                feedback_message = f"{opener}\n{formatted_feedback}"

            if state.get("interaction_mode") == "voice":
                state.setdefault("messages", []).append(
                    {"role": "assistant", "content": feedback_message.replace("\n", " ")}
                )
            else:
                send_whatsapp_message(state["user_id"], feedback_message)
            return "retry"
        else:
            feedback_message = f"💙 I'll work with what you've shared: '{user_input}'"
            if state.get("interaction_mode") == "voice":
                state.setdefault("messages", []).append(
                    {"role": "assistant", "content": feedback_message}
                )
            else:
                send_whatsapp_message(state["user_id"], feedback_message)
            if validation_key in state:
                del state[validation_key]
            return "accepted"
