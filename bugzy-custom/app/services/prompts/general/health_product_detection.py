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


def is_health_question(user_msg: str) -> bool:
    """
    Check if user message is a health-related question or advice query using OpenAI Turbo model.
    Applies validation for question length and type with enhanced coverage.
    """
    
    # Basic input sanity checks
    msg_lower = user_msg.strip().lower()
    words = msg_lower.split()
    
    # FIRST: Check if it mentions any product - if so, NOT a health question
    product_names = [
        'metabolically lean', 'ams', 'almond milk smoothie', 'gut cleanse', 'gut balance', 'bye bye bloat',
        'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
        'sleep and calm', 'first defense', 'good to glow', 'pcos balance',
        'good down there', 'happy tummies', 'glycemic control', 'acidity aid', 
        'metabolic fiber boost', 'fiber boost', 'happy tummy', 'metabolic fiber', 'the good bug', 'products', 'product', 'probiotics', 'prebiotics',
    ]
    
    # If any product name is mentioned, this is a product question, not health
    # IMPROVED: Use word boundary matching to avoid false positives
    if any(re.search(r'\b' + re.escape(product_name) + r'\b', msg_lower) for product_name in product_names):
        return False
    
    # Expanded question/advice-seeking indicators (including profile-related queries)
    question_indicators = [
        '?', 'how', 'what', 'should', 'can', 'why', 'when', 'is it', 'could', 'would',
        'do you', 'give me', 'any tips', 'advice', 'advise', 'suggest', 'help', 'recommend',
        'tell me', 'show me', 'explain', 'guide', 'ways to', 'need', 'want', 'looking for',
        'i want', 'i need', 'please', 'pls', 'plz', 'share', 'provide', 'assist',
        'cure', 'treat', 'prevent', 'manage', 'deal with', 'handle', 'improve', 'better',
        'reduce', 'increase', 'fix', 'solve', 'relief', 'relieve',
        # Profile/data-related indicators
        'know about', 'know about me', 'remember', 'recall', 'my', 'about me', 'about myself',
        'my health', 'my condition', 'my conditions', 'my profile', 'my data', 'my information',
        'what are', 'what is my', 'what\'s my', 'whats my', 'tell me about', 'show me my'
    ]
    
    # Special handling for short profile questions (e.g., "what do you know about me")
    profile_question_patterns = [
        r'what.*know.*(about.*me|me)',
        r'tell.*me.*(about.*me|myself)',
        r'what.*are.*my',
        r'what.*is.*my',
        r'what.*my',
        r'show.*me.*my',
        r'my.*(health|condition|conditions|profile|data|information|allergies|allergy|bmi|weight|height|age|meal|diet|exercise|plan)',
        r'what.*you.*know',
        r'do.*you.*remember',
        r'do.*you.*know.*me'
    ]
    
    # Check for profile questions first (allow shorter messages - minimum 2 words)
    is_profile_question = any(re.search(pattern, msg_lower) for pattern in profile_question_patterns)
    
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
        if not any(q in msg_lower for q in question_indicators):
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
        health_keywords = [
            'gut health', 'digestion', 'bloating', 'constipation', 'diarrhea', 
            'ibs', 'crohn', 'colitis', 'acid reflux', 'gerd', 'stomach',
            'inflammation', 'acidity', 'gas', 'indigestion', 'heartburn', 'nausea',
            'symptom', 'disease', 'condition', 'wellness', 'immunity', 'energy',
            'sleep', 'stress', 'anxiety', 'weight', 'nutrition', 'diet', 'fiber',
            'probiotic', 'microbiome', 'healthy', 'health', 'remedy', 'cure',
            'headache', 'fatigue', 'pain', 'discomfort', 'issue', 'problem',
            # Profile/data-related keywords
            'my health', 'my condition', 'my conditions', 'my profile', 'my data', 'my information',
            'my allergies', 'my allergy', 'my bmi', 'my weight', 'my height', 'my age',
            'my meal', 'my diet', 'my exercise', 'my plan', 'my routine',
            'what are my', 'what is my', 'what\'s my', 'whats my', 'what do you know',
            'tell me about me', 'tell me about myself', 'about myself', 'about me',
            'do you know', 'do you remember', 'know about me', 'remember me',
            'show me my', 'tell me my', 'what you know', 'my issues', 'my problems'
        ]
        return any(keyword in msg_lower for keyword in health_keywords)


def is_product_question(user_msg: str) -> bool:
    """Check if user message is a QUESTION about The Good Bug products or company."""
    
    msg_lower = user_msg.strip().lower()
    words = msg_lower.split()
    
    # Must have at least 3 words to be a meaningful question
    if len(words) < 3:
        return False
    
    # CRITICAL: Check if this is about the user's PERSONAL meal plan/diet/meals
    # These should be handled as health/plan questions, NOT product questions
    personal_meal_plan_patterns = [
        r'\bmy meal\b', r'\bmy meals\b', r'\bmy meal plan\b', r'\bmy diet\b',
        r'\bmy diet plan\b', r'\bmy food\b', r'\bmy breakfast\b', r'\bmy lunch\b',
        r'\bmy dinner\b', r'\bmy snack\b', r'\bmy snacks\b', r'\bmy eating\b',
        r'\bmy nutrition\b', r'\bmy nutrition plan\b', r'\bmy daily meal\b',
        r'\bmy daily meals\b', r'\bmy weekly meal\b', r'\bmy weekly meals\b',
        r'\bmy menu\b', r'\bmy food plan\b', r'\bmy eating plan\b',
        r'\bingredients.*for.*my meal', r'\bingredients.*for.*my diet',
        r'\bingredients.*to order.*for.*my', r'\bwhat to eat.*in.*my',
        r'\bmy exercise\b', r'\bmy exercise plan\b', r'\bmy workout\b',
        r'\bmy workout plan\b', r'\bmy fitness\b', r'\bmy fitness plan\b'
    ]
    
    # If asking about their personal meal/diet/exercise plan, it's NOT a product question
    if any(re.search(pattern, msg_lower) for pattern in personal_meal_plan_patterns):
        return False
    
    # FIRST: Check if user is actually ASKING something (question/advice-seeking intent)
    question_indicators = [
        '?', 'how', 'what', 'should', 'can', 'why', 'when', 'is it', 'could', 'would',
        'do you', 'give me', 'any tips', 'advice', 'advise', 'suggest', 'help', 'recommend',
        'tell me', 'show me', 'explain', 'guide', 'ways to', 'need to know', 'want to know',
        'looking for', 'please', 'pls', 'plz', 'share', 'provide', 'assist',
        'which', 'does', 'is there', 'are there', 'will', 'difference between',
        'compare', 'vs', 'versus', 'or', 'better', 'best', 'recommend',
        'where can i', 'how do i', 'where to', 'when to', 'price', 'cost',
        'buy', 'purchase', 'order', 'shipping', 'delivery', 'refund', 'return'
    ]
    
    # If no question/inquiry indicators, it's just a statement/response - NOT a question
    if not any(indicator in msg_lower for indicator in question_indicators):
        return False
    
    # IMPROVED: Check for statement patterns that should be excluded
    # Only exclude if it's clearly a statement, not a question
    statement_patterns = [
        ' works well', ' helped me', ' is good', ' is great', ' is amazing',
        ' is effective', ' is useful', ' is helpful',
        ' helped', ' worked', ' like', ' love', ' prefer', ' enjoy',
        ' helps me', ' helps', ' works'  # Additional patterns for statements
    ]
    
    # If it matches statement patterns AND has no question indicators, it's likely a statement
    if any(pattern in msg_lower for pattern in statement_patterns):
        # Double-check: if it has strong question indicators, still consider it a question
        strong_question_indicators = ['?', 'how', 'what', 'should', 'can', 'why', 'when', 'tell me', 'explain']
        if not any(indicator in msg_lower for indicator in strong_question_indicators):
            return False
    
    # IMPROVED: Specific TGB product names (exclude general terms like 'probiotics')
    specific_product_names = [
        'metabolically lean', 'metabolic fiber boost', 'ams', 'metabolically lean - probiotics', 
        'advanced metabolic system', 'gut cleanse', 'gut balance', 'bye bye bloat', 
        'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles', 
        'prebiotic shots', 'sleep and calm', 'first defense', 'good to glow', 
        'pcos balance', 'good down there', 'fiber boost', 'happy tummy', 'metabolic fiber',
        'happy tummies', 'glycemic control', 'gut cleanse super bundle',
        
        # Additional specific product names from FAQ
        'acidity aid', 'ibs dnm', 'ibs rescue d&m', 'ibs c', 'ibs d', 'ibs m', 
        'gut cleanse detox shot', 'gut cleanse shot', 'prebiotic fiber boost', 
        'smooth move fiber boost', 'constipation bundle', 'pcos bundle', 
        'metabolically lean supercharged', 'ferments', 'squat buddy'
    ]
    
    # Check for specific TGB product mentions
    # IMPROVED: Use word boundary matching to avoid false positives
    if any(re.search(r'\b' + re.escape(product_name) + r'\b', msg_lower) for product_name in specific_product_names):
        return True
    
    # IMPROVED: Product-specific keywords (excluding general terms)
    product_specific_keywords = [
        'stick', 'sticks', 'shots', 'bottles', 'jar', 'scoop', 'serving',
        'variants', 'flavors', 'kala khatta', 'strawberry lemonade',
        'coconut water', 'ginger ale', 'lemongrass basil', 'apple cinnamon',
        'pineapple basil', 'kimchi', 'sauerkraut',
        '15 days', '1 month', '2 months', '3 months', 'subscription',
        'regular price', 'sale price', '₹', 'rupees', 'cost', 'pricing',
        'how to take', 'when to take', 'dosage instructions', 'mix with water',
        'good bug', 'the good bug', 'your product', 'this product', 'your company',
        'buy', 'purchase', 'order', 'shipping', 'delivery', 'refund', 'return',
        'certification', 'gmp', 'fda', 'peta', 'iso', 'haccp',
        'ingredients in', 'contains', 'formulation', 'bacterial strains in', 'probiotics', 'prebiotics', 'products', 'product'
    ]
    
    # Check for product-specific keywords
    if any(keyword in msg_lower for keyword in product_specific_keywords):
        return True
    
    # Company-related keywords
    company_keywords = [
        'privacy policy', 'terms', 'cancellation', 'tracking', 'dispatch',
        'international shipping', 'domestic shipping', 'money back guarantee',
        'exchange', 'quality assurance', 'seven turns'
    ]
    
    if any(keyword in msg_lower for keyword in company_keywords):
        return True
    
    return False