"""
AI Classification Module

This module handles message classification using LLM and heuristics.
Includes:
- Health question detection
- Product question detection
"""

import re
from app.services.llm.bedrock_llm import ChatBedRockLLM
import logging

logger = logging.getLogger(__name__)

from app.services.chatbot.bugzy_gut_cleanse.constants import (
    HEALTH_CHECK_PRODUCT_NAMES,
    PROFILE_QUESTION_PATTERNS,
    HEALTH_QUESTION_INDICATORS,
    HEALTH_FALLBACK_KEYWORDS,
    ORDER_TRACKING_KEYWORDS,
    PERSONAL_MEAL_PLAN_PATTERNS,
    PRODUCT_QUESTION_INDICATORS,
    STATEMENT_PATTERNS,
    STRONG_QUESTION_INDICATORS,
    SPECIFIC_PRODUCT_NAMES,
    PRODUCT_SPECIFIC_KEYWORDS,
    COMPANY_KEYWORDS,
)


def is_health_question(user_msg: str) -> bool:
    """
    Check if user message is a health-related question or advice query using OpenAI Turbo model.
    Applies validation for question length and type with enhanced coverage.
    """

    # Basic input sanity checks
    msg_lower = user_msg.strip().lower()
    words = msg_lower.split()

    # FIRST: Check if it mentions any product - if so, NOT a health question
    # IMPROVED: Use word boundary matching to avoid false positives
    if any(re.search(r'\b' + re.escape(p) + r'\b', msg_lower) for p in HEALTH_CHECK_PRODUCT_NAMES):
        return False

    # Check for profile questions first (allow shorter messages - minimum 2 words)
    is_profile_question = any(re.search(pattern, msg_lower) for pattern in PROFILE_QUESTION_PATTERNS)

    # Word count validation: profile questions need at least 2 words, others need at least 3
    if is_profile_question:
        if len(words) < 2:
            return False
        # Profile questions can proceed with 2+ words
    else:
        # Non-profile questions need at least 3 words
        if len(words) < 3:
            return False
        # Also need question indicators for non-profile questions
        if not any(q in msg_lower for q in HEALTH_QUESTION_INDICATORS):
            return False

    # Initialize Turbo model
    model = ChatBedRockLLM(temperature=0.0)

    # Enhanced classification prompt
    prompt = f"""
You are a precise classifier determining if a message is a genuine health-related question or advice request.

Health-related questions include:
- Requests for advice, tips, guidance, suggestions, or recommendations about health
- Questions about gut health, digestion, nutrition, diet, wellness
- Questions about symptoms, conditions, diseases, or medical issues
- Requests for ways to improve, manage, prevent, or treat health conditions
- Questions about lifestyle changes for health improvement
- Mental health and stress-related queries
- Sleep, energy, and general wellness questions
- Questions asking about the user's OWN profile, health data, or stored information
- Questions asking what the assistant knows about the user's health, conditions, allergies, BMI, diet, exercise plans, etc.

PROFILE-RELATED QUESTIONS (these are HEALTH questions):
- Questions asking about the user's own health information (e.g., "what are my health conditions", "what do you know about me", "tell me about myself")
- Questions about user's stored data (e.g., "what is my BMI", "what are my allergies", "show me my meal plan", "what's my exercise routine")
- Questions asking the assistant to recall or share user's profile information
- Questions about the user's own health status, conditions, allergies, diet preferences, meal plans, exercise plans
- Any question where the user is asking "what do you know about me" or similar variations
- Questions asking about "my health", "my conditions", "my profile", "my data", "my information"

The user may use various phrases like: "advice", "advise", "help", "suggest", "tips", "recommend", 
"tell me", "show me", "guide", "ways to", "how to", "what can I do", "please help", 
"what do you know", "what are my", "what is my", "tell me about me", "about myself", etc.

CRITICAL: If the message mentions ANY specific product name, product usage, or pricing, respond 'NO'.
Only respond 'YES' if it's clearly a health-related query without product mentions.

Examples:

Message: "help me with 3 tips to reduce bloating"
Answer: YES

Message: "advise me on gut health improvement"
Answer: YES

Message: "pls suggest ways to sleep better"
Answer: YES

Message: "tell me how to manage stress"
Answer: YES

Message: "i need recommendations for constipation"
Answer: YES

Message: "what can i do for acidity"
Answer: YES

Message: "looking for natural remedies for headaches"
Answer: YES

Message: "share tips for weight management"
Answer: YES

Message: "ways to boost immunity"
Answer: YES

Message: "what do you know about me"
Answer: YES

Message: "what are my health conditions"
Answer: YES

Message: "tell me about myself"
Answer: YES

Message: "what is my BMI"
Answer: YES

Message: "what are my allergies"
Answer: YES

Message: "show me my meal plan"
Answer: YES

Message: "what's my exercise routine"
Answer: YES

Message: "what do you remember about me"
Answer: YES

Message: "tell me about my health"
Answer: YES

Message: "what information do you have about me"
Answer: YES

Message: "what are my health issues"
Answer: YES

Message: "how to use gut cleanse?"
Answer: NO

Message: "what is the price of AMS?"
Answer: NO

Message: "tell me about metabolically lean"
Answer: NO

Message: "what products do you have"
Answer: NO

Message: "show me products"
Answer: NO

Now classify this message:
Message: "{user_msg}"
Is this a health-related question? Answer only YES or NO.
"""

    try:
        response = model.invoke(prompt)
        classification = response.content.strip().upper()
        return classification == "YES"

    except Exception as e:
        logger.error("⚠️ Error classifying message: %s", e)
        # Enhanced fallback with broader keyword coverage including profile-related queries
        return any(keyword in msg_lower for keyword in HEALTH_FALLBACK_KEYWORDS)


def is_product_question(user_msg: str) -> bool:
    """Check if user message is a QUESTION about The Good Bug products or company."""

    msg_lower = user_msg.strip().lower()

    # ---------------------------------------------------------
    # ORDER-RELATED QUERIES: Always route to product QnA (RAG handles with correct prompts)
    # ---------------------------------------------------------
    if any(keyword in msg_lower for keyword in ORDER_TRACKING_KEYWORDS):
        return True
    # ---------------------------------------------------------

    words = msg_lower.split()

    # Must have at least 3 words to be a meaningful question
    if len(words) < 3:
        return False

    # CRITICAL: Check if this is about the user's PERSONAL meal plan/diet/meals
    # These should be handled as health/plan questions, NOT product questions
    if any(re.search(pattern, msg_lower) for pattern in PERSONAL_MEAL_PLAN_PATTERNS):
        return False

    # FIRST: Check if user is actually ASKING something (question/advice-seeking intent)
    if not any(indicator in msg_lower for indicator in PRODUCT_QUESTION_INDICATORS):
        return False

    # IMPROVED: Check for statement patterns that should be excluded
    # Only exclude if it's clearly a statement, not a question
    if any(pattern in msg_lower for pattern in STATEMENT_PATTERNS):
        # Double-check: if it has strong question indicators, still consider it a question
        if not any(indicator in msg_lower for indicator in STRONG_QUESTION_INDICATORS):
            return False

    # IMPROVED: Specific TGB product names (exclude general terms like 'probiotics')
    # IMPROVED: Use word boundary matching to avoid false positives
    if any(re.search(r'\b' + re.escape(p) + r'\b', msg_lower) for p in SPECIFIC_PRODUCT_NAMES):
        return True

    # IMPROVED: Product-specific keywords (excluding general terms)
    if any(keyword in msg_lower for keyword in PRODUCT_SPECIFIC_KEYWORDS):
        return True

    # Company-related keywords
    if any(keyword in msg_lower for keyword in COMPANY_KEYWORDS):
        return True

    return False