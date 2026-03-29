"""
Shared QnA logic for Bugzy chatbots.
Contains product detection, reformulation, and response generation utilities.
"""

import re
import logging
import random
from typing import List, Optional

logger = logging.getLogger(__name__)

# --- CONSTANTS ---

# Direct product names for exact matching
DIRECT_PRODUCT_NAMES = [
    "metabolically lean",
    "metabolic fiber boost",
    "ams",
    "metabolically lean - probiotics",
    "advanced metabolic system",
    "gut cleanse",
    "gut balance",
    "bye bye bloat",
    "smooth move",
    "ibs rescue",
    "water kefir",
    "kombucha",
    "fermented pickles",
    "prebiotic shots",
    "sleep and calm",
    "first defense",
    "good to glow",
    "pcos balance",
    "good down there",
    "fiber boost",
    "happy tummy",
    "metabolic fiber",
    "happy tummies",
    "glycemic control",
    "gut cleanse super bundle",
    "acidity aid",
    "ibs dnm",
    "ibs rescue d&m",
    "ibs c",
    "ibs d",
    "ibs m",
    "gut cleanse detox shot",
    "gut cleanse shot",
    "prebiotic fiber boost",
    "smooth move fiber boost",
    "constipation bundle",
    "pcos bundle",
    "metabolically lean supercharged",
    "ferments",
    "squat buddy",
    "probiotics",
    "prebiotics",
    "12 week guided program", 
    "12-week guided program", 
    "12 week guided", 
    "12-week guided", 
    "12 week program", 
    "12-week program",
    "Metabolically Lean AMS",
    "Post Meal Digestive Mints",
    "digestive mints",
    "mints",
    "ACV with Garcinia Cambogia",
    "acv",
    "garcinia",
    "Gluta Glow",
    "gluta",
    "glutathione",
    "12 Week Guided Program",
    "12 week program",
    "Super Gut Powder",
    "Miracle Tea",
    "Probiotic Essentials",
    "Ashwagandha",
    "Magnesium Bisglycinate",
    "Beetroot Kefir",
    "Coconut Kefir"
]

# Phrases that indicate user is asking about their own order
MY_PRODUCT_QUERY_PHRASES = [
    "my product", "my products", "my order", "my orders", "my purchase", "my purchases",
    "what did i buy", "what i bought", "what did i purchase", "what i purchased",
    "what have i bought", "what have i purchased", "what did i order", "what i ordered",
    "which product did i buy", "which product i bought", "which product did i order",
    "which product i ordered", "which product is mine",
    "the product i bought", "the product i ordered", "the product i purchased",
    "my current product", "my latest product", "my last order", "my recent order",
    "what product do i have", "what product i have", "what am i using", "what am i taking",
    "what supplement do i have", "what supplement i bought",
]

# Product names for contextual follow-up detection (includes generic "product(s)")
CONTEXTUAL_PRODUCT_NAMES = [
    "metabolically lean", "ams", "gut cleanse", "gut balance", "bye bye bloat",
    "smooth move", "ibs rescue", "water kefir", "kombucha", "fermented pickles",
    "sleep and calm", "first defense", "good to glow", "pcos balance",
    "good down there", "happy tummies", "glycemic control", "acidity aid", "metabolic fiber boost",
    "fiber boost", "happy tummy", "metabolic fiber", "the good bug", "products", "product",
    "ibs dnm", "ibs rescue d&m", "ibs c", "ibs d", "ibs m",
    "gut cleanse detox shot", "gut cleanse shot", "prebiotic fiber boost",
    "smooth move fiber boost", "constipation bundle", "pcos bundle",
    "metabolically lean supercharged", "ferments", "squat buddy", "probiotics", "prebiotics",
    "Metabolically Lean AMS", "Post Meal Digestive Mints", "ACV with Garcinia Cambogia",
    "Gluta Glow", "12 Week Guided Program", "Super Gut Powder", "Miracle Tea",
    "Probiotic Essentials", "Ashwagandha", "Magnesium Bisglycinate",
    "Beetroot Kefir", "Coconut Kefir"
]

# Product names for extracting from history (no generic terms)
EXTRACT_PRODUCT_NAMES = DIRECT_PRODUCT_NAMES

# For is_product_question heuristic
SPECIFIC_PRODUCT_NAMES = DIRECT_PRODUCT_NAMES

PRODUCT_SPECIFIC_KEYWORDS = [
    "stick", "sticks", "shots", "bottles", "jar", "scoop", "serving",
    "variants", "flavors", "kala khatta", "strawberry lemonade",
    "coconut water", "ginger ale", "lemongrass basil", "apple cinnamon",
    "pineapple basil", "kimchi", "sauerkraut",
    "15 days", "1 month", "2 months", "3 months", "subscription",
    "regular price", "sale price", "₹", "rupees", "cost", "pricing",
    "how to take", "when to take", "dosage instructions", "mix with water",
    "good bug", "the good bug", "your product", "this product", "your company",
    "buy", "purchase", "order", "shipping", "delivery", "refund", "return",
    "certification", "gmp", "fda", "peta", "iso", "haccp",
    "ingredients in", "contains", "formulation", "bacterial strains in", "probiotics", "prebiotics", "products", "product",
    "12 week guided program", "12-week guided program", "12 week guided", "12-week guided", "12 week program", "12-week program",
    "Metabolically Lean AMS", "Post Meal Digestive Mints", "ACV with Garcinia Cambogia",
    "Gluta Glow", "12 Week Guided Program", "Gut Cleanse", "Super Gut Powder", "Miracle Tea",
    "Probiotic Essentials", "Ashwagandha", "Magnesium Bisglycinate",
    "Water Kefir", "Beetroot Kefir", "Coconut Kefir",
    "stomach", "bloating", "weight", "metabolism", "energy", "cravings", "hunger", "sachet", "fiber", "probiotic", "scoop", "powder",
    "mints", "digestive", "post meal", "gas", "digestion", "heavy", "relief",
    "acv", "vinegar", "garcinia", "fat", "appetite",
    "skin", "glow", "glutathione", "acne", "radiance", "hydration", "pigmentation",
    "program", "guided", "12 week", "journey", "coach", "plan", "support",
    "cleanse", "detox", "gut", "acid", "day 1"
]

COMPANY_KEYWORDS = [
    "privacy policy", "terms", "cancellation", "tracking", "dispatch",
    "international shipping", "domestic shipping", "money back guarantee",
    "exchange", "quality assurance", "seven turns",
]

GENERAL_HEALTH_PATTERNS = [
    "meal plan", "diet plan", "nutrition plan", "eating plan",
    "weight loss", "weight gain", "fitness", "exercise", "workout",
    "health advice", "nutrition advice", "diet advice", "lifestyle advice",
    "general health", "overall health", "wellness", "healthy lifestyle",
    "ingredients", "my meals", "my meal", "for my meals", "for my meal",
    "grocery", "shopping list", "recipe", "recipes", "to order for",
    "what to buy", "what to order", "ingredients for", "ingredients to",
    "food items", "grocery list", "meal prep", "meal preparation",
    "cooking", "prepare", "make my meals", "cook my meals",
]

FOLLOW_UP_PATTERNS = [
    "how to take", "how to consume", "how to use", "when to take",
    "can i take", "can i mix", "can i use", "can i consume",
    "with other", "with drinks", "with food", "with milk", "with water",
    "side effects", "dosage", "timing", "take it", "use it", "consume it",
    "mix it", "how much", "how often", "is it safe", "best time",
    "empty stomach", "with meals", "before eating", "after eating",
    "how do i", "how should i", "when should i", "instructions", "direction",
    "how many", "benefits", "effect", "work", "does it", "is it", "can it",
    "price", "cost", "where", "buy", "purchase", "order", "precaustions", "precautions",
    "what about", "how about", "tell me about", "explain", "describe",
    "is this", "is that", "are these", "are those", "will it", "would it",
    "can i use", "should i use", "when can i", "how can i", "why should i",
    "how long", "how long should", "how long does", "how long to", "how long will",
    "when will", "when should", "how soon", "how quickly", "how fast",
    "time to", "wait to", "see results", "take effect", "start working",
]


# --- FUNCTIONS ---

def determine_llm_temperature(
    user_question: str,
    detected_intent: str,
    is_followup: bool,
    conversation_history: list
) -> float:
    """
    Determine optimal temperature for LLM based on question type and context.
    
    Strategy:
    - Follow-ups: 0.0 (deterministic - maintain context consistency)
    - Meal queries: 0.5 (medium - allow variety in suggestions)
    - General health: 0.6 (medium-high - diverse, insightful responses)
    - Health conditions: 0.3 (low - accuracy important)
    - Default: 0.4 (balanced)
    
    Args:
        user_question: The user's question text
        detected_intent: Intent category (meal, product, health, general)
        is_followup: Whether this is a follow-up question
        conversation_history: Recent conversation context
    
    Returns:
        float: Temperature value (0.0 to 1.0)
    """
    
    # PRIORITY 1: Follow-up questions (maintain context consistency)
    if is_followup:
        logger.debug(f"Temperature: 0.0 (follow-up question)")
        return 0.0
    
    # PRIORITY 2: Intent-specific temperatures
    if detected_intent == "meal":
        # Allow variety in meal suggestions and alternatives
        logger.debug(f"Temperature: 0.5 (meal intent)")
        return 0.5
    elif detected_intent == "health":
        # Check if it's about specific conditions (lower temp) or general wellness (higher temp)
        user_question_lower = user_question.lower()
        condition_keywords = [
            "diabetes", "pcos", "thyroid", "disease", "condition", "syndrome",
            "disorder", "infection", "cancer", "heart", "kidney", "liver"
        ]
        if any(keyword in user_question_lower for keyword in condition_keywords):
            # Specific health conditions - more accuracy needed
            logger.debug(f"Temperature: 0.3 (specific health condition)")
            return 0.3
        else:
            # General health/wellness - allow diverse, insightful responses
            logger.debug(f"Temperature: 0.6 (general health/wellness)")
            return 0.6
    elif detected_intent == "general":
        # General queries - diverse and insightful
        logger.debug(f"Temperature: 0.6 (general intent)")
        return 0.6
    
    # Default: balanced approach
    logger.debug(f"Temperature: 0.4 (default)")
    return 0.4


def is_product_question(user_msg: str) -> bool:
    """Check if user message is a question about The Good Bug products (self-contained heuristic)."""
    msg_lower = user_msg.strip().lower()
    words = msg_lower.split()
    if len(words) < 3:
        return False
        
    personal_meal_plan_patterns = [
        r"\bmy meal\b", r"\bmy meals\b", r"\bmy meal plan\b", r"\bmy meal plans\b", r"\bmy diet\b",
        r"\bmy diet plan\b", r"\bmy food\b", r"\bmy exercise\b", r"\bmy exercise plan\b",
        r"\bmy workout\b", r"\bmy workout plan\b", r"\bmy fitness\b",
    ]
    if any(re.search(p, msg_lower) for p in personal_meal_plan_patterns):
        return False
        
    question_indicators = [
        "?", "how", "what", "should", "can", "why", "when", "is it", "could", "would",
        "do you", "give me", "tell me", "show me", "explain", "need to know", "want to know",
        "looking for", "please", "which", "does", "is there", "price", "cost", "buy", "purchase", "order",
    ]
    if not any(indicator in msg_lower for indicator in question_indicators):
        return False
        
    statement_patterns = [
        " works well", " helped me", " is good", " is great", " is amazing",
        " is effective", " helped", " worked", " like", " love", " prefer", " enjoy", " helps me", " works",
    ]
    if any(p in msg_lower for p in statement_patterns):
        strong = ["?", "how", "what", "should", "can", "why", "when", "tell me", "explain"]
        if not any(ind in msg_lower for ind in strong):
            return False
            
    if any(re.search(r"\b" + re.escape(p) + r"\b", msg_lower) for p in SPECIFIC_PRODUCT_NAMES):
        return True
    if any(keyword in msg_lower for keyword in PRODUCT_SPECIFIC_KEYWORDS):
        return True
    if any(keyword in msg_lower for keyword in COMPANY_KEYWORDS):
        return True
    return False


def is_contextual_product_question(user_msg: str, conversation_history: list) -> bool:
    """Check if the question is likely about products based on recent conversation context."""
    if not conversation_history:
        return False
    
    conversation_length = len(conversation_history)
    window_size = 8 if conversation_length <= 10 else (12 if conversation_length <= 20 else 16)
    
    recent_messages = conversation_history[-window_size:]
    product_mentioned = False
    mentioned_product = None
    product_position = -1
    
    for i, msg in enumerate(recent_messages):
        content = msg.get("content", "").lower()
        for product in CONTEXTUAL_PRODUCT_NAMES:
            if re.search(r"\b" + re.escape(product) + r"\b", content):
                product_mentioned = True
                mentioned_product = product
                product_position = i
                break
        if product_mentioned:
            break
            
    if not product_mentioned:
        return False
        
    user_msg_lower = user_msg.lower()
    
    direct_match = any(p in user_msg_lower for p in FOLLOW_UP_PATTERNS)
    is_general_health = any(p in user_msg_lower for p in GENERAL_HEALTH_PATTERNS)
    pronoun_patterns = ["it", "this", "that", "these", "those", "they", "them", "its", "itself"]
    has_pronoun = any(pronoun in user_msg_lower.split() for pronoun in pronoun_patterns)
    product_in_question = mentioned_product and mentioned_product in user_msg_lower
    
    is_short_question = len(user_msg_lower.split()) <= 6
    is_recent_product_mention = product_position >= (len(recent_messages) - 6)
    
    is_contextual = (
        (direct_match and not is_general_health)
        or (has_pronoun and is_short_question and not is_general_health)
        or product_in_question
        or (is_recent_product_mention and is_short_question and has_pronoun and not is_general_health)
        or (has_pronoun and is_recent_product_mention and not is_general_health)
    )
    
    return is_contextual


def is_any_product_query(user_msg: str, conversation_history: list = None) -> bool:
    """
    Unified product detection helper.
    Checks for direct product names (with word boundaries) AND contextual follow-ups.
    """
    if not user_msg:
        return False
        
    msg_lower = user_msg.lower()
    
    # 1. Direct Name Check (Word Boundaries)
    has_direct_name = False
    for product in DIRECT_PRODUCT_NAMES:
        # Avoid matching generic terms like 'probiotics' too loosely if they are part of a health question
        # But if they are the only thing or in a product context, they count.
        pattern = r'\b' + re.escape(product) + r'\b'
        if re.search(pattern, msg_lower):
            # Special case: don't count generic "probiotics"/"prebiotics" alone as a product question 
            # if the user is asking about "probiotics in food" etc.
            if product in ["probiotics", "prebiotics"] and any(w in msg_lower for w in ["food", "diet", "rich", "natural", "source"]):
                continue
            has_direct_name = True
            break
            
    if has_direct_name:
        return True
        
    # 2. Heuristic check (keywords like 'ingredients in', 'how to take it' etc)
    if is_product_question(user_msg):
        return True
        
    # 3. Contextual check (follow-up)
    if conversation_history and is_contextual_product_question(user_msg, conversation_history):
        return True
        
    return False


def extract_relevant_product_from_history(recent_messages: list, current_question: str) -> str:
    """Extract the most relevant product name from recent conversation history."""
    current_question_lower = current_question.lower()
    
    if any(p in current_question_lower for p in GENERAL_HEALTH_PATTERNS):
        return ""
        
    # Check current question first
    for product in EXTRACT_PRODUCT_NAMES:
        if re.search(r"\b" + re.escape(product) + r"\b", current_question_lower):
            return product
            
    # Check history backwards
    for message in reversed(recent_messages):
        content = message.get("content", "").lower()
        for product in EXTRACT_PRODUCT_NAMES:
            if re.search(r"\b" + re.escape(product) + r"\b", content):
                return product
                
    return ""


def reformulate_followup_fallback(question: str, product: str) -> str:
    """Fallback rule-based reformulation if LLM fails."""
    question_lower = question.lower()
    if any(w in question_lower for w in ["how do i take", "how to take", "how should i take"]):
        return f"how to take {product}"
    if any(w in question_lower for w in ["how do i use", "how to use", "how should i use"]):
        return f"how to use {product}"
    if any(w in question_lower for w in ["price", "cost", "how much"]):
        return f"what is the price of {product}"
    if any(w in question_lower for w in ["safe", "side effect", "risk", "interaction"]):
        return f"is {product} safe"
    if any(w in question_lower for w in ["work", "effect", "result", "benefit"]):
        return f"how does {product} work"
    if any(w in question_lower for w in ["when", "time", "duration"]):
        return f"when to take {product}"
    if any(w in question_lower for w in ["how long"]):
        return f"how long does {product} take to work"
    if question_lower.startswith(("what", "how", "when", "where", "why", "is", "can", "does")):
        return f"{question} {product}"
    return f"{question} about {product}"


def reformulate_with_gpt(question: str, product: str, recent_messages: list) -> str:
    """Use Bedrock LLM to reformulate follow-up questions to be self-contained."""
    try:
        from app.services.llm.bedrock_llm import BedrockLLM
        client = BedrockLLM(temperature=0.1, max_tokens=50)
        
        conversation_context = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in recent_messages[-3:]
        ])
        
        reformulation_prompt = f"""Your task is to create a simple, self-contained question by combining a product name with a user's follow-up question.
Do NOT change the user's original phrasing or add any new information. Just add the product name to make the question specific and clear.
Rules: Keep the user's wording; only add the product name; one sentence only; no explanations.

Examples:
- CURRENT PRODUCT: bye bye bloat | FOLLOW-UP: how do i take it? → how do i take bye bye bloat?
- CURRENT PRODUCT: metabolically lean | FOLLOW-UP: what about the price → what is the price for metabolically lean?
- CURRENT PRODUCT: gut cleanse | FOLLOW-UP: when should i use this → when should i use gut cleanse?

CONVERSATION CONTEXT:
{conversation_context}

CURRENT PRODUCT: {product}
FOLLOW-UP QUESTION: {question}

Reformulated Question:"""

        messages = [
            {"role": "system", "content": "You reformulate follow-up questions to be self-contained by adding product names. Respond with only the reformulated question."},
            {"role": "user", "content": reformulation_prompt},
        ]
        
        response = client.invoke(messages)
        reformulated = response.content.strip().replace('"', '').replace("'", "")
        
        if product.lower() not in reformulated.lower():
            return f"{question} about {product}"
            
        return reformulated
        
    except Exception as e:
        logger.debug("reformulate_with_gpt error: %s", e)
        return reformulate_followup_fallback(question, product)
