# ==============================================================================
# NODE CONFIGURATION & MAPPING
# ==============================================================================

# Keys to clear on fresh session start (prevents ghost data across restarts)
AMS_KEYS_TO_CLEAR = [
    "age", "height", "weight", "bmi",
    "health_conditions", "medications",
    "diet_preference", "cuisine_preference", "current_dishes", "allergies",
    "water_intake", "beverages", "supplements", "gut_health", "meal_goals",
    "workout_gut_mobility_gut", "workout_relaxation_gut",
    "workout_gut_awareness_gut", "fitness_level", "activity_types",
    "exercise_frequency", "exercise_intensity", "session_duration",
    "sedentary_time", "exercise_goals", "workout_posture_gut",
    "wants_meal_plan", "wants_exercise_plan", "meal_plan_sent",
    "exercise_plan_sent", "meal_plan", "exercise_plan",
    "meal_day1_plan", "meal_day2_plan", "meal_day3_plan", "meal_day4_plan",
    "meal_day5_plan", "meal_day6_plan", "meal_day7_plan",
    "day5_plan", "day6_plan", "day7_plan",
    "journey_restart_mode", "voice_agent_choice",
    "voice_agent_context", "voice_agent_promotion_shown",
    "voice_agent_declined", "voice_agent_accepted",
]

# Greeting messages — CRM user (personalized with name)
AMS_CRM_GREETING_1 = (
    "Hey {user_name} \U0001f44b I'm Bugzy, your *Metabolic Health Partner*. "
    "I'm here to help you accelerate your metabolism, manage weight, and feel lighter & more energetic! \u26a1"
)
AMS_CRM_GREETING_2 = (
    "Here's how I can help you succeed with the AMS program:\n"
    "\U0001f525 *Metabolic Boost* \u2013 Custom meal & movement plans to fire up your metabolism.\n"
    "\U0001f4f8 *Smart Food Check* \u2013 Snap a pic of your meal to see if it's AMS-friendly.\n"
    "\U0001f9d8 *Daily Wellness* \u2013 Tips to reduce stress and improve sleep for better weight management."
)
AMS_CRM_GREETING_3 = "Ready to transform your metabolic health? Let's start building your personalized plan!"

# Greeting messages — non-CRM user (generic)
AMS_GENERIC_GREETING_1 = (
    "Hey there! \U0001f44b I'm Bugzy, your *Metabolic Health Partner*. "
    "I'm here to help you accelerate your metabolism, manage weight, and feel lighter & more energetic! \u26a1"
)
AMS_GENERIC_GREETING_2 = (
    "Here's how I can help you succeed with the AMS program:\n"
    "\U0001f525 *Metabolic Boost* \u2013 Custom meal & movement plans to fire up your metabolism.\n"
    "\U0001f4f8 *Smart Food Check* \u2013 Snap a pic of your meal to see if it's AMS-friendly."
)
AMS_GENERIC_GREETING_3 = (
    "\U0001f9d8 *Daily Wellness* \u2013 Tips to reduce stress and improve sleep for better weight management.\n\n"
    "Ready to transform your metabolic health? Let's start building your personalized plan!"
)

# BMI text-based category lookup — replaces if-elif chain.
# Each entry: (condition_fn, category_label, bmi_display)
BMI_TEXT_CATEGORIES = [
    (
        lambda w: "underweight" in w or "(underweight)" in w or "weight_underweight" in w,
        "Underweight (below 18.5)",
        "below 18.5",
    ),
    (
        lambda w: "healthy" in w or "(healthy)" in w or "weight_healthy" in w,
        "Healthy Weight (18.5\u201324.9)",
        "18.5\u201324.9",
    ),
    (
        lambda w: "(over)" in w or "overweight" in w or "weight_overweight" in w,
        "Overweight (25.0\u201329.9)",
        "25.0\u201329.9",
    ),
    (
        lambda w: "(ob-i)" in w or "obese1" in w or "obesity i" in w or "weight_obese1" in w,
        "Obesity Class I (30.0\u201334.9)",
        "30.0\u201334.9",
    ),
    (
        lambda w: "(ob-ii)" in w or "obese2" in w or "obesity ii" in w or "weight_obese2" in w,
        "Obesity Class II (35.0\u201339.9)",
        "35.0\u201339.9",
    ),
    (
        lambda w: "(ob-iii)" in w or "obese3" in w or "obesity iii" in w or "weight_obese3" in w,
        "Obesity Class III (40.0 or greater)",
        "40.0+",
    ),
]

# BMI numeric thresholds — (upper_bound_exclusive, category_label)
# Last entry covers bmi >= 40 (Obesity Class III).
BMI_NUMERIC_CATEGORIES = [
    (18.5, "Underweight"),
    (25.0, "Healthy Weight"),
    (30.0, "Overweight"),
    (35.0, "Obesity Class I"),
    (40.0, "Obesity Class II"),
]
BMI_LAST_CATEGORY = "Obesity Class III"

# Button Response IDs for Meal Plan Preference
MEAL_PLAN_YES = "yes_meal_plan"
MEAL_PLAN_HAS_ONE = "has_meal_plan"
MEAL_PLAN_LATER = "no_meal_plan"
EDIT_EXISTING_MEAL_PLAN = "edit_existing_meal_plan"
CREATE_NEW_MEAL_PLAN = "create_new_meal_plan"

# Button Response IDs for Exercise Plan Preference
EXERCISE_PLAN_YES = "yes_exercise_plan"
EXERCISE_PLAN_HAS_ONE = "has_exercise_plan"
EXERCISE_PLAN_LATER = "no_exercise_plan"
EDIT_EXISTING_EXERCISE_PLAN = "edit_existing_exercise_plan"
CREATE_NEW_EXERCISE_PLAN = "create_new_exercise_plan"

QUESTION_TO_NODE = {
    "age": "collect_age",
    "height": "collect_height",
    "weight": "collect_weight",
    "health_conditions": "collect_health_conditions",
    "medications": "collect_medications",
    # AMS Specific Meal Nodes (Comprehensive)
    "diet_preference": "collect_diet_preference",
    "cuisine_preference": "collect_cuisine_preference",
    "current_dishes": "collect_current_dishes",
    "allergies": "collect_allergies",
    "water_intake": "collect_water_intake",
    "beverages": "collect_beverages",
    "supplements": "collect_supplements",
    "gut_health": "collect_gut_health",
    "meal_goals": "collect_meal_goals",
    # FITT Assessment Nodes
    "fitness_level": "collect_fitness_level",
    "activity_types": "collect_activity_types",
    "exercise_frequency": "collect_exercise_frequency",
    "exercise_intensity": "collect_exercise_intensity",
    "session_duration": "collect_session_duration",
    "sedentary_time": "collect_sedentary_time",
    "exercise_goals": "collect_exercise_goals",
    # Single-call 7-day plan generation nodes
    "generating_remaining_meal_days": "generate_all_remaining_meal_days",
    "generating_remaining_exercise_days": "generate_all_remaining_exercise_days",
    # Meal Plan Nodes
    "handle_meal_day1_review_choice": "handle_meal_day1_review_choice",
    "collect_meal_day1_changes": "collect_meal_day1_changes",
    "regenerate_meal_day1_plan": "regenerate_meal_day1_plan",
    "handle_meal_day1_revised_review": "handle_meal_day1_revised_review",
    "generate_all_remaining_meal_days": "generate_all_remaining_meal_days",
    "meal_day1_plan_review": "handle_meal_day1_review_choice",
    "meal_day1_revised_review": "handle_meal_day1_revised_review",
    "generate_meal_day1_plan": "generate_meal_plan",
    # Exercise Plan Nodes
    "generate_all_remaining_exercise_days": "generate_all_remaining_exercise_days",
    "handle_day1_review_choice": "handle_day1_review_choice",
    "collect_day1_changes": "collect_day1_changes",
    "regenerate_day1_plan": "regenerate_day1_plan",
    "handle_day1_revised_review": "handle_day1_revised_review",
    "day1_plan_review": "handle_day1_review_choice",
    "day1_revised_review": "handle_day1_revised_review",
    "generate_day1_plan": "generate_day1_plan",
    # New Preference Nodes
    "ask_meal_plan_preference": "ask_meal_plan_preference",
    "ask_exercise_plan_preference": "ask_exercise_plan_preference",
    "existing_meal_plan_choice": "ask_existing_meal_plan_choice",
    "existing_exercise_plan_choice": "ask_existing_exercise_plan_choice",
    "voice_agent_promotion_meal": "voice_agent_promotion_meal",
    "voice_agent_promotion_exercise": "voice_agent_promotion_exercise",
}

MEAL_PLAN_QUESTION = (
    "Great! Now, would you like me to create a personalized meal plan for you?"
)
EXERCISE_PLAN_QUESTION = (
    "Would you like me to create a personalized workout plan for you?"
)

TRANSITION_MESSAGES = [
    "💚 Let's pick up where we left off...",
    "🌟 Now, back to your personalized plan...",
    "✨ Great! Let's continue with your wellness journey...",
    "💫 Perfect! Now let's get back to creating your plan...",
    "🌸 Awesome! Let's continue where we paused...",
    "💝 I hope you're feeling better! Now, back to your plan...",
    "🌿 Got it! Let's resume building your wellness plan...",
    "💖 Take care of yourself! Now, let's continue...",
    "🌺 Wonderful! Let's get back to your personalized journey...",
    "✨ That's sorted! Now, back to crafting your plan...",
    "💚 Perfect! Let's continue with the next step...",
    "🌟 Great! Now, let's pick up where we were...",
]

INVALID_SNAP_INDICATORS = [
    "I can't provide nutritional advice",
    "I couldn't analyze that image",
    "doesn't contain food items",
]


def is_valid_snap_image(snap_result: str) -> bool:
    return bool(
        snap_result
        and not any(indicator in snap_result for indicator in INVALID_SNAP_INDICATORS)
    )


TRANSITION_TO_GUT_COACH_MESSAGES = [
    # --- VALID IMAGE CASES ---
    {
        "condition": lambda s: is_valid_snap_image(s.get("snap_analysis_result", "")) and s.get("wants_meal_plan") and s.get("wants_exercise_plan"),
        "template": "✨ All set, {user_name}! I've analyzed your image and completed your wellness plans.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    {
        "condition": lambda s: is_valid_snap_image(s.get("snap_analysis_result", "")) and s.get("wants_meal_plan") and not s.get("wants_exercise_plan"),
        "template": "✨ All set, {user_name}! I've analyzed your image and completed your meal plan.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    {
        "condition": lambda s: is_valid_snap_image(s.get("snap_analysis_result", "")) and not s.get("wants_meal_plan") and s.get("wants_exercise_plan"),
        "template": "✨ All set, {user_name}! I've analyzed your image and completed your exercise plan.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    {
        "condition": lambda s: is_valid_snap_image(s.get("snap_analysis_result", "")) and not s.get("wants_meal_plan") and not s.get("wants_exercise_plan"),
        "template": "✨ All set, {user_name}! I've analyzed your image.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    
    # --- INVALID OR NO IMAGE CASES ---
    {
        "condition": lambda s: not is_valid_snap_image(s.get("snap_analysis_result", "")) and s.get("wants_meal_plan") and s.get("wants_exercise_plan"),
        "template": "✨ All set, {user_name}! I've completed your wellness plans.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    {
        "condition": lambda s: not is_valid_snap_image(s.get("snap_analysis_result", "")) and s.get("wants_meal_plan") and not s.get("wants_exercise_plan"),
        "template": "✨ All set, {user_name}! I've completed your meal plan.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    {
        "condition": lambda s: not is_valid_snap_image(s.get("snap_analysis_result", "")) and not s.get("wants_meal_plan") and s.get("wants_exercise_plan"),
        "template": "✨ All set, {user_name}! I've completed your exercise plan.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    
    # --- FALLBACK (No Valid Image, No Plans) ---
    {
        "condition": lambda s: True,
        "template": "✨ All set, {user_name}!\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
]

CATEGORY_EMOJI_MAP = {
    "product":  ["\U0001f9ec"],
    "shipping": ["\U0001f4e6"],
    "refund":   ["\U0001f4b0"],
    "policy":   ["\U0001f4cb"],
}
CATEGORY_EMOJI_DEFAULT = "\U0001f49a"

# ---------------------------------------------------------------------------
# Health / product question detection constants
# (imported by app/services/prompts/ams/health_product_detection.py)
# ---------------------------------------------------------------------------

# Product names that disqualify a message from being a health question
HEALTH_CHECK_PRODUCT_NAMES = [
    'metabolically lean', 'ams', 'almond milk smoothie', 'gut cleanse', 'gut balance', 'bye bye bloat',
    'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
    'sleep and calm', 'first defense', 'good to glow', 'pcos balance',
    'good down there', 'happy tummies', 'glycemic control', 'acidity aid',
    'metabolic fiber boost', 'fiber boost', 'happy tummy', 'metabolic fiber',
    'the good bug', 'products', 'product', 'probiotics', 'prebiotics',
    '12 week guided program', '12-week guided program', '12 week guided', '12-week guided',
    '12 week program', '12-week program',
]

# Regex patterns that identify a profile/self-referential health question
PROFILE_QUESTION_PATTERNS = [
    r'what.*know.*(about.*me|me)',
    r'tell.*me.*(about.*me|myself)',
    r'what.*are.*my',
    r'what.*is.*my',
    r'what.*my',
    r'show.*me.*my',
    r'my.*(health|condition|conditions|profile|data|information|allergies|allergy|bmi|weight|height|age|meal|diet|exercise|plan)',
    r'what.*you.*know',
    r'do.*you.*remember',
    r'do.*you.*know.*me',
]

# General question / advice-seeking indicators (used in is_health_question)
HEALTH_QUESTION_INDICATORS = [
    '?', 'how', 'what', 'should', 'can', 'why', 'when', 'is it', 'could', 'would',
    'do you', 'give me', 'any tips', 'advice', 'advise', 'suggest', 'help', 'recommend',
    'tell me', 'show me', 'explain', 'guide', 'ways to', 'need', 'want', 'looking for',
    'i want', 'i need', 'please', 'pls', 'plz', 'share', 'provide', 'assist',
    'cure', 'treat', 'prevent', 'manage', 'deal with', 'handle', 'improve', 'better',
    'reduce', 'increase', 'fix', 'solve', 'relief', 'relieve',
    'know about', 'know about me', 'remember', 'recall', 'my', 'about me', 'about myself',
    'my health', 'my condition', 'my conditions', 'my profile', 'my data', 'my information',
    'what are', 'what is my', "what's my", 'whats my', 'tell me about', 'show me my',
]

# Keyword fallback used in the except block of is_health_question
HEALTH_FALLBACK_KEYWORDS = [
    'gut health', 'digestion', 'bloating', 'constipation', 'diarrhea',
    'ibs', 'crohn', 'colitis', 'acid reflux', 'gerd', 'stomach',
    'inflammation', 'acidity', 'gas', 'indigestion', 'heartburn', 'nausea',
    'symptom', 'disease', 'condition', 'wellness', 'immunity', 'energy',
    'sleep', 'stress', 'anxiety', 'weight', 'nutrition', 'diet', 'fiber',
    'probiotic', 'microbiome', 'healthy', 'health', 'remedy', 'cure',
    'headache', 'fatigue', 'pain', 'discomfort', 'issue', 'problem',
    'my health', 'my condition', 'my conditions', 'my profile', 'my data', 'my information',
    'my allergies', 'my allergy', 'my bmi', 'my weight', 'my height', 'my age',
    'my meal', 'my diet', 'my exercise', 'my plan', 'my routine',
    'what are my', 'what is my', "what's my", 'whats my', 'what do you know',
    'tell me about me', 'tell me about myself', 'about myself', 'about me',
    'do you know', 'do you remember', 'know about me', 'remember me',
    'show me my', 'tell me my', 'what you know', 'my issues', 'my problems',
]

# Order-tracking keywords — always route to product QnA
ORDER_TRACKING_KEYWORDS = [
    "track", "tracking", "where is my order", "where is my package",
    "order status", "order id", "delivery status", "delivery update",
    "shipped", "shipment", "dispatch", "dispatched", "in transit",
    "when will", "when will i receive", "when will it arrive",
    "not delivered", "out for delivery", "expected delivery",
    "return my order", "refund my order", "cancel my order",
    "exchange my order", "wrong order", "damaged order",
]

# Regex patterns for personal meal/diet/exercise plan references
PERSONAL_MEAL_PLAN_PATTERNS = [
    r'\bmy meal\b', r'\bmy meals\b', r'\bmy meal plan\b', r'\bmy diet\b',
    r'\bmy diet plan\b', r'\bmy food\b', r'\bmy breakfast\b', r'\bmy lunch\b',
    r'\bmy dinner\b', r'\bmy snack\b', r'\bmy snacks\b', r'\bmy eating\b',
    r'\bmy nutrition\b', r'\bmy nutrition plan\b', r'\bmy daily meal\b',
    r'\bmy daily meals\b', r'\bmy weekly meal\b', r'\bmy weekly meals\b',
    r'\bmy menu\b', r'\bmy food plan\b', r'\bmy eating plan\b',
    r'\bingredients.*for.*my meal', r'\bingredients.*for.*my diet',
    r'\bingredients.*to order.*for.*my', r'\bwhat to eat.*in.*my',
    r'\bmy exercise\b', r'\bmy exercise plan\b', r'\bmy workout\b',
    r'\bmy workout plan\b', r'\bmy fitness\b', r'\bmy fitness plan\b',
]

# Question / inquiry indicators used in is_product_question
PRODUCT_QUESTION_INDICATORS = [
    '?', 'how', 'what', 'should', 'can', 'why', 'when', 'is it', 'could', 'would',
    'do you', 'give me', 'any tips', 'advice', 'advise', 'suggest', 'help', 'recommend',
    'tell me', 'show me', 'explain', 'guide', 'ways to', 'need to know', 'want to know',
    'looking for', 'please', 'pls', 'plz', 'share', 'provide', 'assist',
    'which', 'does', 'is there', 'are there', 'will', 'difference between',
    'compare', 'vs', 'versus', 'or', 'better', 'best', 'recommend',
    'where can i', 'how do i', 'where to', 'when to', 'price', 'cost',
    'buy', 'purchase', 'order', 'shipping', 'delivery', 'refund', 'return',
]

# Statement patterns that suggest the message is NOT a question
STATEMENT_PATTERNS = [
    ' works well', ' helped me', ' is good', ' is great', ' is amazing',
    ' is effective', ' is useful', ' is helpful',
    ' helped', ' worked', ' like', ' love', ' prefer', ' enjoy',
    ' helps me', ' helps', ' works',
]

# Strong question indicators used to override statement pattern exclusion
STRONG_QUESTION_INDICATORS = [
    '?', 'how', 'what', 'should', 'can', 'why', 'when', 'tell me', 'explain',
]

# Specific TGB product names (for word-boundary matching)
SPECIFIC_PRODUCT_NAMES = [
    'metabolically lean', 'metabolic fiber boost', 'ams', 'metabolically lean - probiotics',
    'advanced metabolic system', 'gut cleanse', 'gut balance', 'bye bye bloat',
    'smooth move', 'ibs rescue', 'water kefir', 'kombucha', 'fermented pickles',
    'prebiotic shots', 'sleep and calm', 'first defense', 'good to glow',
    'pcos balance', 'good down there', 'fiber boost', 'happy tummy', 'metabolic fiber',
    'happy tummies', 'glycemic control', 'gut cleanse super bundle',
    'acidity aid', 'ibs dnm', 'ibs rescue d&m', 'ibs c', 'ibs d', 'ibs m',
    'gut cleanse detox shot', 'gut cleanse shot', 'prebiotic fiber boost',
    'smooth move fiber boost', 'constipation bundle', 'pcos bundle',
    'metabolically lean supercharged', 'ferments', 'squat buddy',
    '12 week guided program', '12-week guided program', '12 week guided', '12-week guided',
    '12 week program', '12-week program',
]

# Product-specific keywords (excluding general terms)
PRODUCT_SPECIFIC_KEYWORDS = [
    'stick', 'sticks', 'shots', 'bottles', 'jar', 'scoop', 'serving',
    'variants', 'flavors', 'kala khatta', 'strawberry lemonade',
    'coconut water', 'ginger ale', 'lemongrass basil', 'apple cinnamon',
    'pineapple basil', 'kimchi', 'sauerkraut',
    '15 days', '1 month', '2 months', '3 months', 'subscription',
    'regular price', 'sale price', '\u20b9', 'rupees', 'cost', 'pricing',
    'how to take', 'when to take', 'dosage instructions', 'mix with water',
    'good bug', 'the good bug', 'your product', 'this product', 'your company',
    'buy', 'purchase', 'order', 'shipping', 'delivery', 'refund', 'return',
    'certification', 'gmp', 'fda', 'peta', 'iso', 'haccp',
    'ingredients in', 'contains', 'formulation', 'bacterial strains in',
    'probiotics', 'prebiotics', 'products', 'product',
    '12 week guided program', '12-week guided program', '12 week guided', '12-week guided',
    '12 week program', '12-week program',
]

# Company-related keywords
COMPANY_KEYWORDS = [
    'privacy policy', 'terms', 'cancellation', 'tracking', 'dispatch',
    'international shipping', 'domestic shipping', 'money back guarantee',
    'exchange', 'quality assurance', 'seven turns',
]
