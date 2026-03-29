"""
Shared logic for extracting health information from user messages using LLM.
"""

import logging
from typing import Optional, List
import re
from app.services.whatsapp.utils import llm

logger = logging.getLogger(__name__)

def is_user_providing_information(text: str) -> bool:
    """
    STRICT CHECK: Determine if user is PROVIDING/STATING information about themselves
    vs ASKING questions or making inquiries.
    
    Returns True ONLY if user is clearly stating facts about themselves.
    Returns False if user is asking questions, making inquiries, or being vague.
    """
    if not text:
        return False
    
    text_lower = text.strip().lower()
    
    # CRITICAL: If it has question indicators, it's NOT providing information
    question_indicators = [
        '?',  # Question mark is the strongest indicator
        'what', 'how', 'why', 'when', 'where', 'who', 'which', 'whom', 'whose',
        'can you', 'could you', 'would you', 'should i', 'will you', 'shall i', 'may i', 'might i',
        'do you', 'does it', 'did you', 'is it', 'are there', 'was it', 'were there',
        'tell me', 'show me', 'explain', 'help me', 'recommend',
        'can i', 'could i', 'should i', 'would i', 'will i',
        'do i', 'does', 'did', 'is there', 'are there', 'has it', 'have you',
        'more about', 'tell me about', 'know about', 'learn about', 'hear about',
        'information about', 'details about', 'info about', 'tell me more',
        'what about', 'how about', 'anything about', 'something about'
    ]
    
    # If ANY question indicator is present, user is asking, not stating
    if any(indicator in text_lower for indicator in question_indicators):
        return False
    
    # CRITICAL: Check for inquiry/request patterns
    inquiry_patterns = [
        'tell me', 'show me', 'explain', 'describe', 'help', 'advice',
        'suggest', 'recommend', 'guide', 'assist', 'provide', 'give me',
        'share', 'looking for', 'want to know', 'need to know', 'curious',
        'wondering', 'interested in', 'more info', 'more information',
        'more details', 'elaborate', 'clarify', 'specify'
    ]
    
    if any(pattern in text_lower for pattern in inquiry_patterns):
        return False
    
    # POSITIVE INDICATORS: User is stating facts about themselves
    # These patterns indicate the user is providing information
    statement_indicators = [
        'i have', 'i am', 'i\'m', 'i take', 'i use', 'i suffer from',
        'i experience', 'i get', 'i was diagnosed', 'i\'ve been diagnosed',
        'diagnosed with', 'suffering from', 'dealing with',
        'my condition', 'my health', 'my medication', 'my supplement',
        'i\'m allergic', 'allergic to', 'intolerant to', 'sensitive to',
        'i don\'t have', 'i do not have', 'i\'m not', 'i am not',
        'no health', 'no condition', 'no medication', 'no supplement', 
        'no allergy', 'none', 'not allergic'
    ]
    
    # Check if user is making a statement about themselves
    has_statement_indicator = any(indicator in text_lower for indicator in statement_indicators)
    
    # Additional check: First-person pronouns indicating self-disclosure
    first_person_patterns = ['i ', 'my ', 'me ', 'i\'m ', 'i\'ve ', 'i have ', 'i take ', 'i use ']
    has_first_person = any(text_lower.startswith(pattern) or f' {pattern}' in text_lower for pattern in first_person_patterns)
    
    # User must have BOTH statement indicators AND first-person reference to be providing info
    # OR have strong statement indicators
    if has_statement_indicator or has_first_person:
        # Double-check: make sure it's not a question disguised as a statement
        # e.g., "Should I take medication if I have diabetes?"
        if '?' in text or any(q in text_lower for q in ['should i', 'can i', 'do i', 'would i', 'could i']):
            return False
        return True
    
    # Default: if we can't clearly identify it as a statement, assume it's NOT providing info
    return False

def extract_from_conversation(
    prompt_template: str, 
    current_question: str, 
    conversation_history: Optional[List], 
    existing_data: str,
    prefixes_to_remove: List[str]
) -> str:
    """Helper to execute LLM extraction with standard cleaning."""
    text_to_analyze = current_question
    if conversation_history:
        recent_messages = conversation_history[-10:]
        conversation_text = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
            for msg in recent_messages
        ])
        text_to_analyze = f"{conversation_text}\n\nCurrent question: {current_question}"

    extraction_prompt = prompt_template.format(
        existing_data=existing_data or "None",
        text_to_analyze=text_to_analyze
    )

    try:
        response = llm.invoke(extraction_prompt)
        extracted_data = response.content.strip()
        
        # Clean up the response
        extracted_data = extracted_data.replace('"', '').replace("'", "").strip()
        
        if ":" in extracted_data:
            parts = extracted_data.split(":", 1)
            if len(parts) > 1:
                extracted_data = parts[1].strip()
        
        extracted_data_lower = extracted_data.lower()
        for prefix in prefixes_to_remove:
            if extracted_data_lower.startswith(prefix):
                extracted_data = extracted_data[len(prefix):].strip()
        
        if extracted_data.lower() in ["none", "no", "nothing", "n/a", "na", ""]:
            extracted_data = ""
            
        return extracted_data
    except Exception as e:
        logger.error(f"Error during extraction: {e}")
        return ""

def merge_extracted_data(existing: str, extracted: str) -> str:
    """Merge new extracted items with existing comma-separated list."""
    existing_clean = existing.strip() if existing else ""
    if existing_clean.lower() in ["none", "no", "nothing", "n/a", "na"]:
        existing_clean = ""
        
    if not extracted and not existing_clean:
        return ""
    if not extracted:
        return existing_clean
    if not existing_clean:
        return extracted
        
    existing_list = [i.strip() for i in existing_clean.split(",") if i.strip()]
    extracted_list = [i.strip() for i in extracted.split(",") if i.strip()]
    
    combined = existing_list.copy()
    for item in extracted_list:
        already_exists = False
        for ex in combined:
            if ex.lower() == item.lower():
                already_exists = True
                break
        if not already_exists:
            combined.append(item)
            
    return ", ".join(combined)

def handle_denial(
    current_question: str,
    conversation_history: List,
    existing_data: str,
    denial_patterns: List[str],
    denial_prompt_template: str,
    category_name: str
) -> Optional[str]:
    """Handle user denying/removing a condition."""
    current_lower = current_question.lower()
    is_denial = any(pattern in current_lower for pattern in denial_patterns)
    
    if not is_denial or not existing_data:
        return None
        
    recent_assistant_messages = []
    if conversation_history:
        for msg in reversed(conversation_history[-5:]):
            if msg.get('role') == 'assistant':
                recent_assistant_messages.append(msg.get('content', ''))
                
    denial_prompt = denial_prompt_template.format(
        existing_data=existing_data,
        current_question=current_question,
        recent_messages=chr(10).join(recent_assistant_messages[-2:]) if recent_assistant_messages else 'None'
    )
    
    try:
        denial_response = llm.invoke(denial_prompt)
        denied_items = denial_response.content.strip().lower()
        denied_items = denied_items.replace('"', '').replace("'", "").strip()
        
        if denied_items in ["none", "no", "nothing", "n/a", "na", ""]:
            return None
            
        existing_list = [i.strip() for i in existing_data.split(",") if i.strip()]
        denied_list = [i.strip() for i in denied_items.split(",") if i.strip()]
        
        remaining = []
        for item in existing_list:
            item_lower = item.lower()
            should_remove = False
            for denied in denied_list:
                if denied in item_lower or item_lower in denied:
                    should_remove = True
                    break
            if not should_remove:
                remaining.append(item)
                
        result = ", ".join(remaining) if remaining else ""
        logger.info(f"{category_name.upper()} DENIAL | Denied: {denied_items} | Remaining: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing denial for {category_name}: {e}")
        return None

def extract_health_conditions_intelligently(
    current_question: str, 
    conversation_history: Optional[list], 
    existing_health_conditions: Optional[str]
) -> str:
    """Extract health conditions from user input."""
    if conversation_history is None:
        conversation_history = []
        
    if not is_user_providing_information(current_question):
        return existing_health_conditions or ""
        
    denial_val = handle_denial(
        current_question, conversation_history, existing_health_conditions,
        ["i don't have", "i do not have", "no i don't", "remove", "not true", "incorrect"],
        """The user is saying they don't have a health condition that was mentioned.
Identify which specific health condition(s) they are denying/removing.

EXISTING HEALTH CONDITIONS: {existing_data}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{recent_messages}

Return ONLY the health condition(s) they are denying (comma-separated), or "none" if you can't identify.
Return only the condition name(s), nothing else:""",
        "Health Conditions"
    )
    if denial_val is not None:
        return denial_val

    prompt = """Extract ONLY the health conditions, medical issues, or symptoms that the user EXPLICITLY STATES they have in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they have a condition, NOT asking about it.
- "I have diabetes" -> VALID (user is stating)
- "tell me about diabetes" -> INVALID (user is asking)

CRITICAL RULE: Do NOT infer, assume, or add conditions that are not directly stated by the user.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user HAS.
2. DO NOT extract from questions or inquiries.
3. PRESERVE QUALIFIERS AND SEVERITY as stated by the user.
4. Handle various phrasings: "I'm diabetic" -> diabetes.
5. If user says "none", return empty string.
6. Return ONLY a comma-separated list.
7. DO NOT standardize, infer, or add conditions.

EXISTING HEALTH CONDITIONS FROM PROFILE: {existing_data}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned health conditions that the user STATES they have (preserving qualifiers). Return comma-separated list only, or empty string if none found:"""

    extracted = extract_from_conversation(
        prompt, current_question, conversation_history, existing_health_conditions,
        ["health conditions:", "conditions:", "health issues:", "the user has:", "extracted conditions:", "mentioned:"]
    )
    
    return merge_extracted_data(existing_health_conditions, extracted)

def extract_allergies_intelligently(
    current_question: str, 
    conversation_history: Optional[list], 
    existing_allergies: Optional[str]
) -> str:
    """Extract allergies from user input."""
    if conversation_history is None:
        conversation_history = []
        
    if not is_user_providing_information(current_question):
        return existing_allergies or ""
        
    denial_val = handle_denial(
        current_question, conversation_history, existing_allergies,
        ["i'm not allergic", "not allergic", "no allergies", "remove", "incorrect"],
        """The user is saying they don't have an allergy that was mentioned.
Identify which specific allergy/allergies they are denying/removing.

EXISTING ALLERGIES: {existing_data}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{recent_messages}

Return ONLY the allergy/allergies they are denying (comma-separated), or "none" if you can't identify.
Return only the allergy name(s), nothing else:""",
        "Allergies"
    )
    if denial_val is not None:
        return denial_val

    prompt = """Extract ONLY the allergies, food intolerances, or sensitivities that the user EXPLICITLY STATES they have in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they have an allergy, NOT asking about it.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user HAS.
2. DO NOT extract from questions or inquiries.
3. PRESERVE QUALIFIERS AND SEVERITY.
4. Handle various phrasings.
5. If user says "none", return empty string.
6. Return ONLY a comma-separated list.

EXISTING ALLERGIES FROM PROFILE: {existing_data}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned allergies/intolerances (preserving qualifiers). Return comma-separated list only, or empty string if none found:"""

    extracted = extract_from_conversation(
        prompt, current_question, conversation_history, existing_allergies,
        ["allergies:", "allergy:", "allergic to:", "the user has:", "extracted allergies:", "food allergies:"]
    )
    
    return merge_extracted_data(existing_allergies, extracted)

def extract_medications_intelligently(
    current_question: str, 
    conversation_history: Optional[list], 
    existing_medications: Optional[str]
) -> str:
    """Extract medications from user input."""
    if conversation_history is None:
        conversation_history = []
        
    if not is_user_providing_information(current_question):
        return existing_medications or ""
        
    denial_val = handle_denial(
        current_question, conversation_history, existing_medications,
        ["i don't take", "not on", "no medications", "remove", "incorrect"],
        """The user is saying they don't take a medication that was mentioned.
Identify which specific medication(s) they are denying/removing.

EXISTING MEDICATIONS: {existing_data}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{recent_messages}

Return ONLY the medication(s) they are denying (comma-separated), or "none" if you can't identify.
Return only the medication name(s), nothing else:""",
        "Medications"
    )
    if denial_val is not None:
        return denial_val

    prompt = """Extract ONLY the medications or drugs that the user EXPLICITLY STATES they take in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they take a medication, NOT asking about it.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user TAKES.
2. DO NOT extract from questions or inquiries.
3. PRESERVE DOSAGE AND FREQUENCY.
4. Handle various phrasings.
5. If user says "none", return empty string.
6. Return ONLY a comma-separated list.

EXISTING MEDICATIONS FROM PROFILE: {existing_data}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned medications/supplements (preserving dosage and frequency). Return comma-separated list only, or empty string if none found:"""

    extracted = extract_from_conversation(
        prompt, current_question, conversation_history, existing_medications,
        ["medications:", "medication:", "drugs:", "the user takes:", "extracted medications:", "prescribed medications:"]
    )
    
    return merge_extracted_data(existing_medications, extracted)

def extract_supplements_intelligently(
    current_question: str,
    conversation_history: Optional[list],
    existing_supplements: Optional[str]
) -> str:
    """Extract supplements from user input."""
    if conversation_history is None:
        conversation_history = []
        
    if not is_user_providing_information(current_question):
        return existing_supplements or ""
        
    denial_val = handle_denial(
        current_question, conversation_history, existing_supplements,
        ["i don't take", "not on", "no supplements", "remove", "incorrect"],
        """The user is saying they don't take a supplement that was mentioned.
Identify which specific supplement(s) they are denying/removing.

EXISTING SUPPLEMENTS: {existing_data}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{recent_messages}

Return ONLY the supplement(s) they are denying (comma-separated), or "none" if you can't identify.
Return only the supplement name(s), nothing else:""",
        "Supplements"
    )
    if denial_val is not None:
        return denial_val

    prompt = """Extract ONLY the supplements or vitamins that the user EXPLICITLY STATES they take in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they take a supplement, NOT asking about it.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user TAKES.
2. DO NOT extract from questions or inquiries.
3. PRESERVE DOSAGE AND FREQUENCY.
4. Handle various phrasings.
5. If user says "none", return empty string.
6. Return ONLY a comma-separated list.

EXISTING SUPPLEMENTS FROM PROFILE: {existing_data}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned supplements (preserving dosage and frequency). Return comma-separated list only, or empty string if none found:"""

    extracted = extract_from_conversation(
        prompt, current_question, conversation_history, existing_supplements,
        ["supplements:", "supplement:", "vitamins:", "vitamin:", "the user takes:", "extracted supplements:"]
    )
    
    return merge_extracted_data(existing_supplements, extracted)

def extract_gut_health_intelligently(
    current_question: str,
    conversation_history: Optional[list],
    existing_gut_health: Optional[str]
) -> str:
    """Extract gut health info from user input."""
    if conversation_history is None:
        conversation_history = []
        
    if not is_user_providing_information(current_question):
        return existing_gut_health or ""
        
    denial_val = handle_denial(
        current_question, conversation_history, existing_gut_health,
        ["incorrect", "wrong", "i don't have", "remove", "not true"],
        """The user is saying information about gut health is not correct.
Identify which specific gut health issue(s) or information they are denying/removing.

EXISTING GUT HEALTH INFO: {existing_data}
CURRENT USER MESSAGE: {current_question}
RECENT ASSISTANT MESSAGES (for context):
{recent_messages}

Return ONLY the gut health issue(s) they are denying (comma-separated), or "none" if you can't identify.
Return only the condition name(s), nothing else:""",
        "Gut Health"
    )
    if denial_val is not None:
        return denial_val

    prompt = """Extract ONLY the gut health issues, digestive conditions, or microbiome-related information that the user EXPLICITLY STATES they have in the conversation below.

CRITICAL VALIDATION: The user must be STATING/DECLARING they have a gut health issue, NOT asking about it.

STRICT GUIDELINES:
1. Extract ONLY what is explicitly STATED as something the user HAS/EXPERIENCES.
2. DO NOT extract from questions or inquiries.
3. PRESERVE DESCRIPTORS AND SEVERITY.
4. If user says "none", return empty string.
5. Return ONLY a comma-separated list.

EXISTING GUT HEALTH INFO FROM PROFILE: {existing_data}

CONVERSATION AND CURRENT QUESTION:
{text_to_analyze}

Extract ONLY explicitly mentioned gut health issues/conditions (preserving severity and descriptors). Return comma-separated list only, or empty string if none found:"""

    extracted = extract_from_conversation(
        prompt, current_question, conversation_history, existing_gut_health,
        ["gut health issues:", "gut health:", "digestive issues:", "conditions:", "digestive conditions:"]
    )
    
    return merge_extracted_data(existing_gut_health, extracted)


def extract_day_number(user_msg: str) -> Optional[int]:
    """
    Extract day number from user message.
    Supports formats like "Day 3", "day 2", "third day", etc.
    Returns day number (1-7) or None if not found.
    """
    if not user_msg:
        return None
    
    user_msg_lower = user_msg.lower()
    
    # Check for numeric day formats (Day 1, day 2, etc.)
    numeric_pattern = r'\bday\s*(\d)\b'
    match = re.search(numeric_pattern, user_msg_lower)
    if match:
        day_num = int(match.group(1))
        if 1 <= day_num <= 7:
            return day_num
    
    # Check for ordinal day formats (first day, second day, etc.)
    ordinal_map = {
        'first': 1, '1st': 1,
        'second': 2, '2nd': 2,
        'third': 3, '3rd': 3,
        'fourth': 4, '4th': 4,
        'fifth': 5, '5th': 5,
        'sixth': 6, '6th': 6,
        'seventh': 7, '7th': 7
    }
    
    for ordinal, num in ordinal_map.items():
        if ordinal in user_msg_lower:
            return num
    
    return None

