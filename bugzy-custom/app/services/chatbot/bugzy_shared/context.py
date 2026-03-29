"""
Shared context and intent detection logic for Bugzy chatbots.
"""

import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Intent Categories
INTENT_MEAL = "meal"
INTENT_EXERCISE = "exercise"
INTENT_PRODUCT = "product"
INTENT_HEALTH = "health"
INTENT_GENERAL = "general"

# Default Keywords (can be overridden)
DEFAULT_MEAL_KEYWORDS = [
    "meal", "food", "diet", "eat", "recipe", "breakfast", "lunch", "dinner", 
    "snack", "cook", "ingredient", "nutrition", "calorie", "protein", "dish",
    "hungry", "serving", "swap", "substitute", "taste", "paneer", "chicken",
    "veg", "non-veg", "vegan", "tofu", "digestibility", "chewing"
]

DEFAULT_EXERCISE_KEYWORDS = [
    "exercise", "workout", "gym", "fitness", "cardio", "strength", "training",
    "run", "walk", "jog", "yoga", "stretch", "muscle", "pain", "sore",
    "recovery", "rep", "set", "weight", "dumbell", "equipment", "movement"
]

DEFAULT_PRODUCT_KEYWORDS = [
    "product", "supplement", "buy", "order", "ship", "delivery", "cost", "price",
    "metabolically lean", "ams", "gut cleanse", "gut balance", "bye bye bloat",
    "smooth move", "ibs rescue", "water kefir", "kombucha", "fermented pickles",
    "shipping", "refund", "policy", "track", "package",
    "sleep and calm", "first defense", "good to glow", "pcos balance",
    "good down there", "happy tummies", "glycemic control", "acidity aid", 
    "metabolic fiber boost", "fiber boost", "happy tummy", "metabolic fiber", 
    "the good bug", "acidity aid", "ibs dnm", "ibs rescue d&m", "ibs c", 
    "ibs d", "ibs m", "gut cleanse detox shot", "gut cleanse shot", 
    "prebiotic fiber boost", "smooth move fiber boost", "constipation bundle", 
    "pcos bundle", "metabolically lean supercharged", "ferments", "squat buddy", 
    "probiotics", "prebiotics"
]

DEFAULT_HEALTH_KEYWORDS = [
    "health", "condition", "disease", "symptom", "doctor", "medical", "pill",
    "medication", "allergy", "intolerance", "blood", "pressure", "sugar",
    "diabetes", "pcos", "thyroid", "bloat", "constipation", "digest", "stomach",
    "gut", "bowel", "stool"
]

def detect_user_intent(
    user_question: str, 
    state: Dict[str, Any],
    product_keywords: List[str] = None,
    meal_keywords: List[str] = None,
    exercise_keywords: List[str] = None,
    health_keywords: List[str] = None
) -> str:
    """
    Classify user question into intent categories.
    
    Args:
        user_question: User's input text
        state: Conversation state
        product_keywords: Optional list of product keywords (defaults to DEFAULT_PRODUCT_KEYWORDS)
        meal_keywords: Optional list of meal keywords (defaults to DEFAULT_MEAL_KEYWORDS)
        exercise_keywords: Optional list of exercise keywords (defaults to DEFAULT_EXERCISE_KEYWORDS)
        health_keywords: Optional list of health keywords (defaults to DEFAULT_HEALTH_KEYWORDS)
        
    Returns:
        Intent string (lowercase)
    """
    if not user_question:
        return INTENT_GENERAL
        
    text = user_question.lower()
    
    # Use provided lists or defaults
    p_keywords = product_keywords if product_keywords is not None else DEFAULT_PRODUCT_KEYWORDS
    m_keywords = meal_keywords if meal_keywords is not None else DEFAULT_MEAL_KEYWORDS
    e_keywords = exercise_keywords if exercise_keywords is not None else DEFAULT_EXERCISE_KEYWORDS
    h_keywords = health_keywords if health_keywords is not None else DEFAULT_HEALTH_KEYWORDS
    
    # 1. Check for product keywords first (specific names often override general categories)
    if any(k in text for k in p_keywords):
        return INTENT_PRODUCT
        
    # 2. Check for meal/exercise specific keywords
    has_meal = any(k in text for k in m_keywords)
    has_exercise = any(k in text for k in e_keywords)
    
    if has_meal and not has_exercise:
        return INTENT_MEAL
    if has_exercise and not has_meal:
        return INTENT_EXERCISE
    
    # 3. Check for specific health keywords
    if any(k in text for k in h_keywords):
        return INTENT_HEALTH
        
    # 4. Fallback to current agent context if ambiguous
    current_agent = state.get("current_agent", "")
    if current_agent == "meal_planner" or current_agent == "meal":
        return INTENT_MEAL
    elif current_agent == "exercise_planner" or current_agent == "exercise":
        return INTENT_EXERCISE
        
    # 5. Default
    return INTENT_GENERAL

def detect_followup_question(user_question: str, conversation_history: List[Dict]) -> bool:
    """
    Detect if the current question is a follow-up to the previous conversation.
    
    Returns: True if this appears to be a follow-up question
    """
    if not conversation_history or len(conversation_history) < 2:
        return False
    
    user_msg_lower = user_question.lower()
    
    # Strong follow-up indicators (high confidence)
    strong_followup_patterns = [
        # Direct follow-up phrases
        'breakdown', 'break down', 'explain more', 'tell me more', 'more about',
        'what about it', 'how about it', 'elaborate',
        
        # Scientific/detail requests (when short/vague)
        'scientific components', 'science behind', 'mechanism', 'how does it',
        'how it works', 'why does it', 'what makes it', 'research on', 'studies on',
        
        # Direct pronoun references
        ' it ', ' this ', ' that ', ' these ', ' those ', ' they ', ' them ',
        'about it', 'about this', 'about that', 'with it', 'with this',
        
        # Benefit/effect questions with pronouns
        'its benefits', 'its effects', 'its advantages', 'its side effects',
        
        # Usage questions with pronouns
        'how to use it', 'when to take it', 'how much of it',
        
        # Explain/describe with "the" (referring to previously mentioned concept)
        'explain the', 'describe the', 'what is the', 'how does the',
    ]
    
    # Weak follow-up indicators (need additional context)
    weak_followup_patterns = [
        'explain', 'describe', 'benefits', 'effects', 'how does', 'why does',
        'how to', 'when to', 'how much', 'how often',
    ]
    
    # New topic indicators (these suggest it's NOT a follow-up)
    new_topic_indicators = [
        'what exercises', 'what workout', 'what meal', 'what diet',
        'what should i eat', 'what should i do', 'what can i do',
        'how can i lose', 'how can i gain', 'how can i improve',
        'tell me about', 'what is', 'what are', 'who is', 'where is',
        'i want to', 'i need to', 'i would like to',
    ]
    
    # Check for new topic indicators first
    has_new_topic = any(pattern in user_msg_lower for pattern in new_topic_indicators)
    if has_new_topic:
        return False
    
    # Check for strong follow-up patterns
    has_strong_followup = any(pattern in user_msg_lower for pattern in strong_followup_patterns)
    if has_strong_followup:
        return True
    
    # Check for weak follow-up patterns with additional context
    has_weak_followup = any(pattern in user_msg_lower for pattern in weak_followup_patterns)
    
    # Check if question is short (likely a follow-up if combined with other signals)
    is_short = len(user_msg_lower.split()) <= 6
    
    # Check if question has pronouns (strong signal for follow-up)
    pronouns = ['it', 'this', 'that', 'these', 'those', 'they', 'them', 'its']
    has_pronoun = any(f' {pronoun} ' in f' {user_msg_lower} ' or 
                      user_msg_lower.startswith(f'{pronoun} ') or 
                      user_msg_lower.endswith(f' {pronoun}')
                      for pronoun in pronouns)
    
    # A question is likely a follow-up if:
    # 1. It has a weak follow-up pattern AND is short (< 6 words) AND has a pronoun, OR
    # 2. It's very short (< 4 words) AND has a pronoun
    is_very_short = len(user_msg_lower.split()) <= 3
    return (has_weak_followup and is_short and has_pronoun) or (is_very_short and has_pronoun)


def is_meal_edit_request(user_msg: str) -> bool:
    """
    Detect if user wants to edit their meal plan.
    Returns True if meal edit intent is detected.
    """
    if not user_msg:
        return False
    
    user_msg_lower = user_msg.lower()
    
    # Meal-related keywords
    meal_keywords = [
        # Core meal terms
        "meal", "diet", "food", "breakfast", "lunch", "dinner", "snack", "brunch",
        "eating", "nutrition", "meal plan", "diet plan", "menu", "recipe",
        
        # Food-related actions
        "cook", "prepare", "eat", "consume", "feed", "nourish",
        
        # Diet types and approaches
        "keto", "vegan", "vegetarian", "paleo", "mediterranean", "carnivore",
        "intermittent fasting", "calorie", "macro", "protein", "carb",
        
        # Meal-related nouns
        "dish", "cuisine", "supper", "appetizer", "entree", "dessert",
        "portion", "serving", "ration", "fare", "feast",
        
        # Health/nutrition terms
        "nutrition plan", "eating plan", "dietary", "nourishment", "sustenance",
        "meal prep", "food plan", "daily meals", "weekly meals"
    ]

    # Edit-related keywords
    edit_keywords = [
        # Direct edit terms
        "edit", "change", "modify", "update", "revise", "adjust",
        "alter", "replace", "swap", "switch", "redo", "regenerate",
        
        # Transformation verbs
        "customize", "personalize", "adapt", "tailor", "tweak", "refine",
        "improve", "enhance", "transform", "redesign", "rework", "rewrite",
        
        # Removal/addition terms
        "remove", "delete", "add", "include", "exclude", "substitute",
        "swap out", "take out", "put in", "exchange", "trade",
        
        # Preference expressions
        "different", "another", "new", "fresh", "alternative", "varied"
    ]

    
    # Check for combinations of meal + edit keywords
    has_meal_keyword = any(keyword in user_msg_lower for keyword in meal_keywords)
    has_edit_keyword = any(keyword in user_msg_lower for keyword in edit_keywords)
    
    # Common phrases that indicate meal edit intent
    meal_edit_phrases = [
        # Direct edit requests
        "edit my meal", "change my meal", "modify my meal",
        "edit meal plan", "change meal plan", "modify meal plan",
        "edit my diet", "change my diet", "modify my diet",
        "edit the meal", "change the meal", "modify the meal",
        
        # Want/need expressions
        "want to edit", "want to change", "want to modify",
        "need to edit", "need to change", "need to modify",
        "would like to edit", "would like to change", "would like to modify",
        "wish to edit", "wish to change", "wish to modify",
        
        # Permission/ability questions
        "can i edit", "can i change", "can i modify",
        "could i edit", "could i change", "could i modify",
        "may i edit", "may i change", "may i modify",
        "how do i edit", "how to edit", "how can i change",
        
        # Combined phrases
        "i want to edit my meal", "i want to change my diet", "i want to modify my diet",
        "i want to edit my diet", "i want to change my meal", "i want to modify my meal",
        "i want to edit my meal plan", "i want to change my diet plan", "i want to modify my diet plan",
        "i want to edit my diet plan", "i want to change my meal plan", "i want to modify my meal plan",
        
        # Creation requests
        "make my meal plan", "create my meal plan", "generate my meal plan",
        "build my meal plan", "design my meal plan", "set up my meal plan",
        "make me a meal plan", "create me a meal plan", "give me a meal plan",
        "make a meal plan", "create a meal plan", "plan my meals",
        
        # Adjustment phrases
        "adjust my meal", "customize my meal", "personalize my diet",
        "tailor my meal plan", "adapt my diet", "refine my meals",
        "update my nutrition", "revise my eating plan", "redo my meal plan",
        
        # Substitution phrases
        "replace my meal", "swap my meal", "substitute my meal",
        "switch my diet", "exchange my meals", "different meal plan",
        "another meal plan", "new meal plan", "alternative diet"
    ]
    
    has_meal_edit_phrase = any(phrase in user_msg_lower for phrase in meal_edit_phrases)
    
    return has_meal_edit_phrase or (has_meal_keyword and has_edit_keyword)


def is_exercise_edit_request(user_msg: str) -> bool:
    """
    Detect if user wants to edit their exercise plan.
    Returns True if exercise edit intent is detected.
    """
    if not user_msg:
        return False
    
    user_msg_lower = user_msg.lower()
    
    # Exercise-related keywords
    exercise_keywords = [
        # Core exercise terms
        "exercise", "workout", "fitness", "training", "gym", "sport",
        "exercise plan", "workout plan", "fitness plan", "training plan",
        
        # Exercise types
        "cardio", "strength", "weights", "yoga", "pilates", "hiit",
        "crossfit", "running", "jogging", "cycling", "swimming", "lifting",
        "calisthenics", "aerobics", "stretching", "mobility",
        
        # Exercise actions
        "train", "work out", "exercise", "move", "sweat", "practice",
        "drill", "condition", "tone", "build", "strengthen",
        
        # Fitness terms
        "fitness routine", "workout routine", "training routine", "exercise routine",
        "gym routine", "workout regimen", "training regimen", "fitness program",
        "workout program", "training program", "exercise program",
        
        # Body/health terms
        "muscle", "endurance", "stamina", "flexibility", "mobility", "agility",
        "conditioning", "physical fitness", "athletic", "bodybuilding"
    ]

    # Edit-related keywords (same as above, included for completeness)
    edit_keywords = [
        # Direct edit terms
        "edit", "change", "modify", "update", "revise", "adjust",
        "alter", "replace", "swap", "switch", "redo", "regenerate",
        
        # Transformation verbs
        "customize", "personalize", "adapt", "tailor", "tweak", "refine",
        "improve", "enhance", "transform", "redesign", "rework", "rewrite",
        
        # Removal/addition terms
        "remove", "delete", "add", "include", "exclude", "substitute",
        "swap out", "take out", "put in", "exchange", "trade",
        
        # Preference expressions
        "different", "another", "new", "fresh", "alternative", "varied"
    ]
    
    # Check for combinations of exercise + edit keywords
    has_exercise_keyword = any(keyword in user_msg_lower for keyword in exercise_keywords)
    has_edit_keyword = any(keyword in user_msg_lower for keyword in edit_keywords)
    
    # Common phrases that indicate exercise edit intent
    exercise_edit_phrases = [
        # Direct edit requests
        "edit my exercise", "change my exercise", "modify my exercise",
        "edit exercise plan", "change exercise plan", "modify exercise plan",
        "edit my workout", "change my workout", "modify my workout",
        "edit workout plan", "change workout plan", "modify workout plan",
        "edit the exercise", "change the exercise", "modify the exercise",
        "edit my training", "change my training", "modify my training",
        "edit my fitness", "change my fitness", "modify my fitness",
        
        # Want/need expressions
        "want to edit", "want to change", "want to modify",
        "need to edit", "need to change", "need to modify",
        "would like to edit", "would like to change", "would like to modify",
        "wish to edit", "wish to change", "wish to modify",
        
        # Permission/ability questions
        "can i edit", "can i change", "can i modify",
        "could i edit", "could i change", "could i modify",
        "may i edit", "may i change", "may i modify",
        "how do i edit", "how to edit", "how can i change",
        
        # Combined phrases
        "i want to edit my exercise", "i want to change my workout", "i want to modify my workout",
        "i want to edit my workout", "i want to change my exercise", "i want to modify my exercise",
        "i want to edit my fitness", "i want to change my training", "i want to modify my training",
        "i want to edit my training", "i want to change my fitness", "i want to modify my fitness",
        "i want to edit my exercise plan", "i want to change my workout plan", "i want to modify my workout plan",
        "i want to edit my workout plan", "i want to change my exercise plan", "i want to modify my exercise plan",
        "i want to edit my fitness plan", "i want to change my training plan", "i want to modify my training plan",
        "i want to edit my training plan", "i want to change my fitness plan", "i want to modify my fitness plan",
        
        # Creation requests
        "make my workout plan", "create my workout plan", "generate my workout plan",
        "make my exercise plan", "create my exercise plan", "generate my exercise plan",
        "make my training plan", "create my training plan", "generate my training plan",
        "make my fitness plan", "create my fitness plan", "generate my fitness plan",
        "build my workout", "design my workout", "set up my exercise routine",
        "make me a workout", "create me an exercise plan", "give me a training plan",
        "plan my workouts", "plan my exercises", "schedule my training",
        
        # Adjustment phrases
        "adjust my workout", "customize my exercise", "personalize my training",
        "tailor my workout plan", "adapt my fitness", "refine my exercises",
        "update my training", "revise my workout", "redo my exercise plan",
        "tweak my routine", "improve my workout", "enhance my training",
        
        # Substitution phrases
        "replace my workout", "swap my exercise", "substitute my training",
        "switch my workout", "exchange my exercises", "different workout plan",
        "another workout plan", "new exercise plan", "alternative training",
        "varied workout", "fresh routine", "different exercises"
    ]

    
    has_exercise_edit_phrase = any(phrase in user_msg_lower for phrase in exercise_edit_phrases)
    
    return has_exercise_edit_phrase or (has_exercise_keyword and has_edit_keyword)

def build_profile_memory_from_mapping(state: Dict[str, Any], mapping: List[Dict[str, Any]], separator: str = "; ") -> str:
    """
    Build a concise profile string based on a mapping configuration.
    
    Each mapping entry can have:
    - key: The state key to check
    - label: The label to use in the output (e.g., 'Name')
    - suffix: Optional string to append (e.g., ' cm')
    - transform: Optional function (val, state) -> str
    - include_if: Optional key that must be truthy for this field to be included
    """
    parts = []
    for field in mapping:
        key = field.get("key")
        label = field.get("label")
        suffix = field.get("suffix", "")
        transform = field.get("transform")
        include_if = field.get("include_if")

        if include_if and not state.get(include_if):
            continue

        if key:
            val = state.get(key)
            if val is not None and val != "":
                if transform:
                    val = transform(val, state)
                if val:
                    parts.append(f"{label}: {val}{suffix}")
        elif transform:
            # Handle complex multi-field combinations
            res = transform(None, state)
            if res:
                parts.append(res)
    
    return separator.join(parts)
