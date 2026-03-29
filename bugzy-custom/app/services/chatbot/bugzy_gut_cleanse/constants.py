# ==============================================================================
# NODE CONFIGURATION & MAPPING
# ==============================================================================

# Keys to clear on fresh session start (prevents ghost data across restarts)
GUT_CLEANSE_KEYS_TO_CLEAR = [
    # Basic Profiling
    "age", "height", "weight", "bmi",
    "age_eligibility_question_sent",
    # Extended Profiling
    "health_safety_status", "health_safety_warning_sent",
    "detox_experience", "detox_recent_reason",
    # 11-Question Meal Plan Fields
    "dietary_preference", "cuisine_preference",
    "food_allergies_intolerances", "daily_eating_pattern", "foods_avoid",
    "supplements", "digestive_issues", "hydration", "other_beverages",
    "gut_sensitivity",
    # Plan Flags & Content
    "wants_meal_plan", "meal_plan_sent", "meal_plan",
    "meal_plan_preference_question_sent",
    # Daily Plans
    "meal_day1_plan", "meal_day2_plan", "meal_day3_plan", "meal_day4_plan",
    "meal_day5_plan", "meal_day6_plan", "meal_day7_plan",
    # Restart Flags
    "journey_restart_mode",
    # Voice Agent Tracker
    "voice_agent_choice", "voice_agent_context", "voice_agent_promotion_shown",
    "voice_agent_declined", "voice_agent_accepted",
]

# Steps where the user is answering a system-provided list/button selection.
# The API-layer guardrail must NOT fire here — these are not free-form health
# questions. The router/node already handles sending the correct MEDICAL_ADVISORY
# warning (via HEALTH_SAFETY_WARNINGS) and advancing the flow.
GUT_CLEANSE_GUARDRAIL_BYPASS_STEPS = {
    "health_safety_screening",
    "detox_experience",
    "detox_recent_reason",
    "pregnancy_check",
    "age_eligibility",
    "gender",
}

# Greeting messages — CRM user (personalized with name)
GUT_CRM_GREETING_1 = "Hey {user_name} \U0001f44b\nI'm Bugsy, your cleanse buddy \U0001f49b."
GUT_CRM_GREETING_2 = (
    "I help make healthy eating & gut wellness simple! \U0001f331\nI can:\n\n"
    "\U0001f4f8 Analyze any food instantly\n"
    "\U0001f957 Build meal plans for toxin removal & gut repair\n"
    "\U0001f33f Support your gut detox journey\n"
    "\U0001f331 Answer gut health questions"
)

# Greeting messages — non-CRM user (generic)
GUT_GENERIC_GREETING_1 = "Hey! \U0001f44b\nI'm Bugsy, your cleanse buddy \U0001f49b."
GUT_GENERIC_GREETING_2 = (
    "I help make healthy eating & gut wellness simple! \U0001f331\nI can:\n\n"
    "\U0001f4f8 Analyze any food instantly\n"
    "\U0001f957 Build meal plans for toxin removal & gut repair\n"
    "\U0001f33f Support your gut detox journey\n"
    "\U0001f331 Answer gut health questions"
)

# Health safety list items used in collect_health_safety_screening
HEALTH_SAFETY_LIST_ITEMS = [
    {
        "title": "\U0001f6ab Not Recommended",
        "rows": [
            {"id": "health_block_under_18", "title": "\U0001f9d2 Under 18", "description": "Below 18 years"},
            {"id": "health_block_pregnant", "title": "\U0001f930 Pregnant", "description": "Pregnant or nursing"},
            {"id": "health_block_ulcers", "title": "\U0001fa79 Stomach Ulcers", "description": "Gastric ulcers history"},
            {"id": "health_block_diarrhea", "title": "\U0001f6bd Chronic Diarrhea", "description": "Frequent loose motions"},
            {"id": "health_block_ibs_ibd", "title": "\U0001f9a0 IBS / IBD", "description": "Bowel diseases"},
        ],
    },
    {
        "title": "\U0001f7e1 Consult Doctor",
        "rows": [
            {"id": "health_consult_diabetes_bp", "title": "\U0001fa78 Diabetes/BP", "description": "Blood sugar or pressure"},
            {"id": "health_consult_kidney", "title": "\U0001fad8 Kidney Disease", "description": "Kidney conditions"},
            {"id": "health_consult_constipation", "title": "\U0001f9f1 Constipation", "description": "Chronic constipation"},
            {"id": "health_consult_surgery", "title": "\U0001fa7a Recent Surgery", "description": "Surgery in 3 months"},
            {"id": "health_consult_hypothyroid", "title": "\U0001f98b Hypothyroid", "description": "Thyroid imbalance"},
        ],
    },
]

# ---------------------------------------------------------------------------
# if-elif replacements for user_verification_nodes.py
# ---------------------------------------------------------------------------

# Detox experience: each entry is (condition_fn, state_value, history_label)
DETOX_EXPERIENCE_MAP = [
    (
        lambda msg, msg_id: "no" in msg or "first" in msg or "detox_exp_no" in msg_id,
        "no",
        "No, first time",
    ),
    (
        lambda msg, msg_id: "long" in msg or "ago" in msg or "detox_exp_long_ago" in msg_id,
        "long_ago",
        "Yes, but long ago",
    ),
]

# Detox recent-reason: each entry is (condition_fn, state_value, history_label)
DETOX_REASON_MAP = [
    (
        lambda msg, msg_id: "incomplete" in msg or "finish" in msg or "detox_reason_incomplete" in msg_id,
        "incomplete",
        "Didn't finish",
    ),
    (
        lambda msg, msg_id: "results" in msg or "detox_reason_no_results" in msg_id,
        "no_results",
        "No results",
    ),
    (
        lambda msg, msg_id: "symptoms" in msg or "back" in msg or "detox_reason_symptoms_back" in msg_id,
        "symptoms_back",
        "Symptoms back",
    ),
    (
        lambda msg, msg_id: "maintenance" in msg or "detox_reason_maintenance" in msg_id,
        "maintenance",
        "Maintenance",
    ),
]

# Block-list button IDs ("Not Recommended" section of health safety screening)
HEALTH_BLOCK_IDS = [
    "health_block_under_18",
    "health_block_pregnant",
    "health_block_ulcers",
    "health_block_diarrhea",
    "health_block_ibs_ibd",
]

# Consult-Doctor button IDs
HEALTH_CONSULT_IDS = [
    "health_consult_diabetes_bp",
    "health_consult_kidney",
    "health_consult_constipation",
    "health_consult_surgery",
    "health_consult_hypothyroid",
]

# Keyword sets that map to each health safety status
HEALTH_STATUS_KEYWORDS = {
    "gut_condition": [
        "ulcer", "diarrhea", "ibd", "ibs", "gut condition",
        "under 18", "pregnant", "breastfeeding",
    ],
    "medical_condition": [
        "diabetes", "kidney", "constipation", "surgery",
        "thyroid", "medical condition", "bp", "blood pressure",
    ],
}

# Safety status → warning message — one entry per selectable option
HEALTH_SAFETY_WARNINGS = {
    # ── Not Recommended (block list) ─────────────────────────────────────────
    "under_18": (
        "🚫 AGE RESTRICTION\n\n"
        "The Gut Cleanse is not recommended for users under 18 years.\n"
        "Your body is still developing and needs proper age-appropriate nutrition.\n\n"
        "We recommend consulting a pediatrician for safe gut health guidance. 💚"
    ),
    "pregnant": (
        "🚫 PREGNANCY ADVISORY\n\n"
        "The Gut Cleanse is NOT recommended during pregnancy or breastfeeding.\n"
        "Your nutritional needs are heightened right now.\n\n"
        "Please consult your OB/GYN or midwife for safe gut health options. 💚"
    ),
    "ulcers": (
        "🚫 STOMACH ULCER ADVISORY\n\n"
        "The Gut Cleanse is NOT recommended if you have active stomach ulcers.\n"
        "Cleansing can irritate ulcers and worsen symptoms.\n\n"
        "Please heal first and consult your gastroenterologist before starting. 💚"
    ),
    "diarrhea": (
        "🚫 CHRONIC DIARRHEA ADVISORY\n\n"
        "The Gut Cleanse is NOT recommended for chronic diarrhea\n"
        "as it may worsen symptoms and further destabilise your gut.\n\n"
        "Please stabilise your gut with your doctor's guidance first. 💚"
    ),
    "ibs_ibd": (
        "🚫 IBS / IBD ADVISORY\n\n"
        "The Gut Cleanse is NOT recommended for IBS or IBD\n"
        "as it may trigger flare-ups.\n\n"
        "We suggest working with a gastroenterologist for a safe,\n"
        "personalised gut protocol before starting. 💚"
    ),
    # ── Consult Doctor First ──────────────────────────────────────────────────
    "diabetes_bp": (
        "🟡 DIABETES / BLOOD PRESSURE ADVISORY\n\n"
        "For diabetes or high blood pressure, please get your doctor's approval\n"
        "before starting the Gut Cleanse.\n\n"
        "Your blood sugar or blood pressure may need monitoring during the cleanse.\n"
        "I'll guide you through, but safety first! 💚"
    ),
    "kidney": (
        "🟡 KIDNEY HEALTH ADVISORY\n\n"
        "For kidney disease, please get your nephrologist's approval\n"
        "before starting the Gut Cleanse.\n\n"
        "Certain detox protocols can put extra load on the kidneys.\n"
        "Your doctor can confirm whether this is safe for you. 💚"
    ),
    "constipation": (
        "🟡 CONSTIPATION ADVISORY\n\n"
        "For chronic constipation, please consult your doctor\n"
        "before starting the Gut Cleanse.\n\n"
        "I'll make sure your meal plan supports gentle bowel movement\n"
        "and keeps things comfortable for you! 💚"
    ),
    "surgery": (
        "🟡 POST-SURGERY ADVISORY\n\n"
        "If you've had surgery in the last 3 months, please get your\n"
        "surgeon's clearance before starting the Gut Cleanse.\n\n"
        "Your body is still recovering and needs special nutritional care.\n"
        "Follow your surgeon's advice on nutrition and supplements. 💚"
    ),
    "hypothyroid": (
        "🟡 THYROID ADVISORY\n\n"
        "For hypothyroidism, please consult your endocrinologist\n"
        "before starting the Gut Cleanse.\n\n"
        "Some foods in the cleanse can affect thyroid medication absorption.\n"
        "Your doctor can help you time it safely. 💚"
    ),
    # ── Fallbacks (backward-compat) ───────────────────────────────────────────
    "gut_condition": (
        "🚫 IMPORTANT NOTICE\n\nThe Gut Cleanse is NOT recommended for:\n"
        "• Ulcers\n• Chronic diarrhea\n• IBD or severe IBS\n\n"
        "You can proceed, but please consult your doctor first 💚"
    ),
    "medical_condition": (
        "🟡 MEDICAL ADVISORY\n\nFor conditions like diabetes, hypertension, or "
        "chronic kidney disease, please get your doctor's approval before starting.\n\n"
        "I'll guide you through, but safety first! 💚"
    ),
}

# Maps each button ID (and keyword fallbacks) to its specific HEALTH_SAFETY_WARNINGS key.
# Used in both the router AND the node so both resolve the same granular status.
from typing import Optional

def resolve_health_safety_status(msg: str, msg_id: str) -> Optional[str]:
    """Resolves specific health status from button ID or message keywords."""
    specific_status = HEALTH_SAFETY_CONDITION_MAP.get(msg_id)
    if not specific_status:
        # Keyword scan (longest match first to avoid false positives)
        for keyword in sorted(HEALTH_SAFETY_CONDITION_MAP, key=len, reverse=True):
            if keyword in msg:
                return HEALTH_SAFETY_CONDITION_MAP[keyword]
    return specific_status


HEALTH_SAFETY_CONDITION_MAP = {
    # ── button IDs ────────────────────────────────────────────────────────────
    "health_block_under_18":        "under_18",
    "health_block_pregnant":        "pregnant",
    "health_block_ulcers":          "ulcers",
    "health_block_diarrhea":        "diarrhea",
    "health_block_ibs_ibd":         "ibs_ibd",
    "health_consult_diabetes_bp":   "diabetes_bp",
    "health_consult_kidney":        "kidney",
    "health_consult_constipation":  "constipation",
    "health_consult_surgery":       "surgery",
    "health_consult_hypothyroid":   "hypothyroid",
    # ── text keyword fallbacks (for users who type a response) ────────────────
    "under 18":                     "under_18",
    "pregnant":                     "pregnant",
    "breastfeeding":                "pregnant",
    "ulcer":                        "ulcers",
    "diarrhea":                     "diarrhea",
    "ibd":                          "ibs_ibd",
    "ibs":                          "ibs_ibd",
    "gut condition":                "ibs_ibd",
    "diabetes":                     "diabetes_bp",
    "bp":                           "diabetes_bp",
    "blood pressure":               "diabetes_bp",
    "kidney":                       "kidney",
    "constipation":                 "constipation",
    "surgery":                      "surgery",
    "thyroid":                      "hypothyroid",
    "medical condition":            "medical_condition",
}


# QnA response category → emoji options (replaces if-elif in transition_to_gut_coach)
CATEGORY_EMOJI_MAP = {
    "product":  ["\U0001f9a0", "\U0001f9ec", "\U0001f9ea", "\U0001f52c"],
    "shipping": ["\U0001f4e6", "\U0001f69a", "\U0001f6a2", "\u2708\ufe0f"],
    "refund":   ["\U0001f4b0", "\U0001f4b3", "\U0001f9fe", "\U0001f504"],
    "policy":   ["\U0001f4cb", "\U0001f4dc", "\U0001f4d6", "\u2696\ufe0f"],
}
CATEGORY_EMOJI_DEFAULT = ["\U0001f49a", "\u2764\ufe0f", "\U0001f499", "\U0001f49c"]
MEAL_PLAN_YES = "yes_meal_plan"
MEAL_PLAN_HAS_ONE = "has_meal_plan"
MEAL_PLAN_LATER = "no_meal_plan"
EDIT_EXISTING_MEAL_PLAN = "edit_existing_meal_plan"
CREATE_NEW_MEAL_PLAN = "create_new_meal_plan"


QUESTION_TO_NODE = {
    # New profiling flow
    "age_eligibility": "collect_age_eligibility",
    "age_warning_confirmation": "collect_age_warning_confirmation",
    "gender": "collect_gender",
    "pregnancy_check": "collect_pregnancy_check",
    "pregnancy_warning_confirmation": "collect_pregnancy_warning_confirmation",
    "health_safety_screening": "collect_health_safety_screening",
    "detox_experience": "collect_detox_experience",
    "detox_recent_reason": "collect_detox_experience",  # Note: routed back to collect_detox_experience to handle the follow-up internally
    # New 11-Question Meal Plan Flow
    "dietary_preference": "collect_dietary_preference",
    "cuisine_preference": "collect_cuisine_preference",
    "food_allergies_intolerances": "collect_food_allergies_intolerances",
    "daily_eating_pattern": "collect_daily_eating_pattern",
    "foods_avoid": "collect_foods_avoid",
    "supplements": "collect_supplements",
    "digestive_issues": "collect_digestive_issues",
    "hydration": "collect_hydration",
    "other_beverages": "collect_other_beverages",
    "gut_sensitivity": "collect_gut_sensitivity",
    # Single-call 7-day plan generation nodes
    "generating_remaining_meal_days": "generate_all_remaining_meal_days",
    # Meal Plan Nodes
    "handle_meal_day1_review_choice": "handle_meal_day1_review_choice",
    "collect_meal_day1_changes": "collect_meal_day1_changes",
    "regenerate_meal_day1_plan": "regenerate_meal_day1_plan",
    "handle_meal_day1_revised_review": "handle_meal_day1_revised_review",
    "generate_all_remaining_meal_days": "generate_all_remaining_meal_days",
    "meal_day1_plan_review": "handle_meal_day1_review_choice",
    "awaiting_meal_day1_changes": "collect_meal_day1_changes",
    "meal_day1_revised_review": "handle_meal_day1_revised_review",
    "generate_meal_day1_plan": "generate_meal_plan",
    # New Preference Nodes
    "ask_meal_plan_preference": "ask_meal_plan_preference",
    "existing_meal_plan_choice": "ask_existing_meal_plan_choice",
    "voice_agent_promotion_meal": "voice_agent_promotion_meal",
}

MEAL_PLAN_QUESTION = (
    "Great! Now, would you like me to create a personalized meal plan for you?"
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
        "condition": lambda s: is_valid_snap_image(s.get("snap_analysis_result", "")) and s.get("wants_meal_plan"),
        "template": "✨ All set, {user_name}! I've analyzed your image and completed your meal plan.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
    {
        "condition": lambda s: is_valid_snap_image(s.get("snap_analysis_result", "")) and not s.get("wants_meal_plan"),
        "template": "✨ All set, {user_name}! I've analyzed your image.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },

    # --- INVALID OR NO IMAGE CASES ---
    {
        "condition": lambda s: not is_valid_snap_image(s.get("snap_analysis_result", "")) and s.get("wants_meal_plan"),
        "template": "✨ All set, {user_name}! I've completed your meal plan.\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },

    # --- FALLBACK (No Valid Image, No Plans) ---
    {
        "condition": lambda s: True,
        "template": "✨ All set, {user_name}!\n\nFeel free to ask me anything about gut health, nutrition, fitness, or our products!",
    },
]

# ---------------------------------------------------------------------------
# Health / product question detection constants
# (imported by app/services/prompts/gut_cleanse/health_product_detection.py)
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
    'regular price', 'sale price', '₹', 'rupees', 'cost', 'pricing',
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
