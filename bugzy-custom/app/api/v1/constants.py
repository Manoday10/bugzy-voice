"""
Constants for the API layer.

Centralizes button mappings, initial state templates, field maps, and regex
patterns used by ams_api.py and gut_cleanse_api.py.
"""
import re

# ==============================================================================
# SHARED STATE & KEY CONSTANTS
# ==============================================================================

# State names
STATE_TRANSITIONING_TO_SNAP = "transitioning_to_snap"
STATE_SNAP_COMPLETE = "snap_complete"
STATE_TRANSITIONING_TO_GUT_COACH = "transitioning_to_gut_coach"
STATE_VERIFIED = "verified"
STATE_POST_PLAN_QNA = "post_plan_qna"
STATE_HEALTH_QNA_ANSWERED = "health_qna_answered"
STATE_PRODUCT_QNA_ANSWERED = "product_qna_answered"
STATE_RESUMING_FROM_SNAP = "resuming_from_snap"

# Session keys
# Session keys
KEY_MEAL_PLAN_SENT = "meal_plan_sent"
KEY_EXERCISE_PLAN_SENT = "exercise_plan_sent"
KEY_PROFILING_COLLECTED = "profiling_collected"
KEY_USER_MSG = "user_msg"
KEY_LAST_QUESTION = "last_question"
KEY_CONVERSATION_HISTORY = "conversation_history"
KEY_FULL_CHAT_HISTORY = "full_chat_history"
KEY_JOURNEY_HISTORY = "journey_history"
KEY_USER_ID = "user_id"

# ==============================================================================
# REGEX PATTERNS — for repetitive button ID families
# ==============================================================================

# Exercise plan day progression (AMS only): yes_day1..yes_day7 → "Yes"
RE_EXERCISE_YES_DAY = re.compile(r"^yes_day[1-7]$")
# Exercise plan day progression (AMS only): no_day1..no_day7 → "Not yet"
RE_EXERCISE_NO_DAY = re.compile(r"^no_day[1-7]$")
# Meal plan day progression (shared): yes_meal_day2..yes_meal_day6 → button_id itself
RE_MEAL_YES_DAY = re.compile(r"^yes_meal_day[2-6]$")


# ==============================================================================
# BUTTON ID → TEXT MAPS
# ==============================================================================

# Buttons used by BOTH AMS and Gut Cleanse
SHARED_BUTTON_MAP = {
    # Meal plan revision
    "make_changes_meal_day1": "make_changes_meal_day1",
    "continue_7day_meal": "continue_7day_meal",
    "more_changes_meal_day1": "more_changes_meal_day1",

    # Meal plan preference
    "yes_meal_plan": "Yes, create plan",
    "no_meal_plan": "No, skip for now",

    # Profiling: Age Eligibility, Gender, Pregnancy
    "age_eligible_yes": "age_eligible_yes",
    "age_eligible_no": "age_eligible_no",
    "gender_male": "gender_male",
    "gender_female": "gender_female",
    "gender_prefer_not_to_say": "gender_prefer_not_to_say",
    "pregnancy_no": "pregnancy_no",
    "pregnancy_yes_pregnant": "pregnancy_yes_pregnant",
    "pregnancy_yes_breastfeeding": "pregnancy_yes_breastfeeding",

    # Health conditions
    "health_none": "None",
    "health_diabetes": "Diabetes",
    "health_ibs": "IBS and gut issues",
    "health_hypertension": "Hypertension",
    "health_thyroid": "Thyroid Issues",
    "health_other": "Other health conditions",

    # Height ranges
    "height_140_150": "140-150 cm / 4'7\"–4'11\"",
    "height_150_160": "150-160 cm / 4'11\"–5'3\"",
    "height_160_170": "160-170 cm / 5'3\"–5'7\"",
    "height_170_180": "170-180 cm / 5'7\"–5'11\"",
    "height_180_190": "180-190 cm / 5'11\"–6'3\"",
    "height_190_200": "190-200 cm / 6'3\"–6'7\"",

    # Weight ranges
    "weight_40_50": "40-50 kg / 88–110 lbs",
    "weight_50_60": "50-60 kg / 110–132 lbs",
    "weight_60_70": "60-70 kg / 132–154 lbs",
    "weight_70_80": "70-80 kg / 154–176 lbs",
    "weight_80_90": "80-90 kg / 176–198 lbs",
    "weight_90_100": "90-100 kg / 198–220 lbs",
    "weight_100_110": "100-110 kg / 220–242 lbs",

    # Diet preference
    "diet_non_veg": "Non-Vegetarian",
    "diet_pure_veg": "Pure Vegetarian",
    "diet_eggitarian": "Eggitarian",
    "diet_vegan": "Vegan",
    "diet_pescatarian": "Pescatarian",
    "diet_flexitarian": "Flexitarian",
    "diet_keto": "Keto",

    # Cuisine preference
    "cuisine_north_indian": "North Indian",
    "cuisine_south_indian": "South Indian",
    "cuisine_gujarati": "Gujarati",
    "cuisine_bengali": "Bengali",
    "cuisine_chinese": "Chinese",
    "cuisine_italian": "Italian",
    "cuisine_mexican": "Mexican",
    "cuisine_all": "All cuisines",

    # Food allergies
    "allergy_none": "No allergies",
    "allergy_dairy": "Dairy allergy",
    "allergy_gluten": "Gluten allergy",
    "allergy_nuts": "Nut allergy",
}

# AMS-only buttons
AMS_BUTTON_MAP = {
    # Exercise plan revision (Day 1 review uses make_changes_exercise_day1; other flows use make_changes_day1)
    "make_changes_exercise_day1": "make_changes_exercise_day1",
    "make_changes_day1": "make_changes_day1",
    "continue_7day": "continue_7day",
    "continue_7day_exercise": "continue_7day_exercise",
    "more_changes_day1": "more_changes_day1",

    # Exercise plan preference
    "yes_exercise_plan": "Yes, create plan",
    "no_exercise_plan": "No, skip for now",

    # Meal Environment
    "env_home_table": "Home (Dining Table)",
    "env_work_desk": "Work Desk",
    "env_on_go": "On the Go",
    "env_tv": "Watching TV",
    "env_varying": "Varies",

    # Meal Mood
    "mood_stress": "Stress Eating",
    "mood_happy": "Happy/Social",
    "mood_bored": "Boredom",
    "mood_sad": "Emotional",
    "mood_none": "No Effect",

    # Meal Cravings
    "crave_sweet": "Sweets/Desserts",
    "crave_salty": "Salty/Savory",
    "crave_fried": "Fried/Oily",
    "crave_spicy": "Spicy",
    "crave_carbs": "Carbs/Breads",
    "crave_none": "None",

    # Workout Motivation
    "motiv_weight": "Weight Loss",
    "motiv_muscle": "Muscle Gain",
    "motiv_mental": "Mental Clarity",
    "motiv_energy": "Increased Energy",
    "motiv_health": "General Health",

    # Workout Environment
    "spot_gym": "Gym",
    "spot_home": "Home",
    "spot_outdoor": "Outdoors",
    "spot_class": "Studio/Class",
    "spot_mixed": "Mixed",

    # Workout Recovery
    "rec_stretch": "Stretching",
    "rec_sleep": "Sleep/Nap",
    "rec_nutrition": "Protein/Meal",
    "rec_active": "Active Recovery",
    "rec_none": "Nothing Specific",
}

# Gut Cleanse-only buttons
GUT_CLEANSE_BUTTON_MAP = {
    # Food allergies (extended)
    "allergy_eggs": "Egg allergy",
    "allergy_multiple": "Multiple allergies",

    # Food intolerances
    "intolerance_lactose": "Lactose intolerant",
    "intolerance_gluten": "Gluten sensitive",
    "intolerance_spicy": "Spice intolerant",
    "intolerance_multiple": "Multiple intolerances",

    # Digestive issues
    "digestive_none": "None currently",
    "digestive_bloating": "Bloating",
    "digestive_constipation": "Constipation",
    "digestive_acidity": "Acidity or heartburn",
    "digestive_gas": "Gas",
    "digestive_irregular": "Irregular bowel movements",
    "digestive_heavy": "Heavy or slow digestion",
    "digestive_sugar": "Sugar cravings",

    # Hydration
    "hydration_less_1l": "Less than 1 liter",
    "hydration_1_2l": "1–2 liters",
    "hydration_2_3l": "2–3 liters",
    "hydration_more_3l": "More than 3 liters",

    # Other beverages
    "beverages_none": "None – No regular beverages",
    "beverages_1_2": "1–2 cups daily",
    "beverages_3_4": "3–4 cups daily",
    "beverages_5_plus": "5+ cups daily",

    # Gut sensitivity
    "sensitivity_very": "Very sensitive",
    "sensitivity_moderate": "Moderately sensitive",
    "sensitivity_not": "Not sensitive",

    # Extended profiling – health conditions
    "health_cond_none": "None",
    "health_cond_diabetes": "Diabetes",
    "health_cond_ibs": "IBS/Gut issues",
    "health_cond_hypertension": "Hypertension",
    "health_cond_thyroid": "Thyroid",
    "health_cond_other": "Other",

    # Health safety screening
    "health_safe_healthy": "Healthy",
    "health_safe_ulcers": "Ulcers",
    "health_safe_diarrhea": "Chronic Diarrhea",
    "health_safe_ibd": "IBD",
    "health_safe_ibs": "IBS",
    "health_safe_gut_condition": "Gut Condition",
    "health_safe_diabetes": "Diabetes",
    "health_safe_kidney": "Chronic Kidney Disease",
    "health_safe_constipation": "Chronic Constipation",
    "health_safe_meds": "Prescribed Meds",
    "health_safe_surgery": "Recent Gut Surgery",
    "health_safe_medical_condition": "Medical Condition",

    # Detox experience
    "detox_exp_no": "No, first time",
    "detox_exp_recent": "Yes, recently",
    "detox_exp_long_ago": "Yes, but long ago",

    # Detox reason
    "detox_reason_incomplete": "Didn't finish",
    "detox_reason_no_results": "No results",
    "detox_reason_symptoms_back": "Symptoms back",
    "detox_reason_maintenance": "Maintenance",

    # Pregnancy warning confirmation
    "pregnancy_proceed_yes": "pregnancy_proceed_yes",
}


# ==============================================================================
# INITIAL STATE TEMPLATES
# Only immutable defaults (None / False / str). Mutable fields
# (conversation_history, journey_history, full_chat_history) must be set
# at the call site to avoid shared-reference bugs.
# ==============================================================================

AMS_INITIAL_STATE_TEMPLATE = {
    # Core session (overridden at call site)
    "user_id": None,
    "user_msg": None,
    "last_question": None,
    "conversation_history": None,   # set to [] at call site
    "journey_history": None,        # set to [] at call site
    "full_chat_history": None,      # set to [] or [{...}] at call site

    # Profiling
    "age": None,
    "height": None,
    "weight": None,
    "bmi": None,
    "health_conditions": None,
    "medications": None,

    # AMS Comprehensive Meal Fields
    "diet_preference": None,
    "cuisine_preference": None,
    "current_dishes": None,
    "allergies": None,
    "water_intake": None,
    "beverages": None,
    "supplements": None,
    "gut_health": None,
    "meal_goals": None,

    # AMS Specific Exercise Fields (FITT)
    "fitness_level": None,
    "activity_types": None,
    "exercise_frequency": None,
    "exercise_intensity": None,
    "session_duration": None,
    "sedentary_time": None,
    "exercise_goals": None,

    # Plan fields
    "meal_plan": None,
    "meal_plan_sent": None,
    "exercise_plan": None,
    "exercise_plan_sent": None,

    # User context
    "current_agent": None,
    "user_name": None,
    "phone_number": None,
    "crm_user_data": None,

    # Order fields
    "user_order": None,
    "user_order_date": None,
    "has_orders": False,

    # Profiling tracking flags
    "profiling_collected": False,
    "profiling_collected_in_meal": False,
    "profiling_collected_in_exercise": False,
    "bmi_calculated": False,
}

GUT_CLEANSE_INITIAL_STATE_TEMPLATE = {
    # Core session (overridden at call site)
    "user_id": None,
    "user_msg": None,
    "last_question": None,
    "conversation_history": None,   # set to [] at call site
    "journey_history": None,        # set to [] at call site
    "full_chat_history": None,      # set to [] or [{...}] at call site

    # Session context
    "current_agent": None,
    "pending_node": None,
    "product": "gut_cleanse",

    # User context
    "user_name": None,
    "phone_number": None,
    "crm_user_data": None,

    # Order fields
    "user_order": None,
    "user_order_date": None,
    "has_orders": False,

    # Required questions (profiling) – Gut Cleanse only
    "age_eligible": None,
    "gender": None,
    "is_pregnant": None,
    "is_breastfeeding": None,
    "health_safety_status": None,
    "health_safety_warning_sent": None,
    "detox_experience": None,
    "detox_recent_reason": None,
    "specific_health_condition": None,
    "age_eligibility_warning_sent": None,

    # Meal plan 11-question flow
    "dietary_preference": None,
    "cuisine_preference": None,
    "food_allergies_intolerances": None,
    "daily_eating_pattern": None,
    "foods_avoid": None,
    "supplements": None,
    "digestive_issues": None,
    "hydration": None,
    "other_beverages": None,
    "gut_sensitivity": None,

    # Plan fields
    "meal_plan": None,
    "meal_plan_sent": None,
    "wants_meal_plan": None,
    "journey_restart_mode": None,

    # Profiling tracking
    "profiling_collected": False,
    "profiling_collected_in_meal": False,
}


# ==============================================================================
# FIELD MAPS — last_question → state key for direct assignment
# (state[key] = combined_text).  "age" is excluded because it needs
# extract_age() and is handled inline as a special case.
# ==============================================================================

AMS_DIRECT_FIELD_MAP = {
    "height": "height",
    "weight": "weight",
    "health_conditions": "health_conditions",
    "medications": "medications",
    # AMS Comprehensive Meal Info
    "diet_preference": "diet_preference",
    "cuisine_preference": "cuisine_preference",
    "current_dishes": "current_dishes",
    "allergies": "allergies",
    "water_intake": "water_intake",
    "beverages": "beverages",
    "supplements": "supplements",
    "gut_health": "gut_health",
    "meal_goals": "meal_goals",
    # AMS Specific Exercise (FITT)
    "fitness_level": "fitness_level",
    "activity_types": "activity_types",
    "exercise_frequency": "exercise_frequency",
    "exercise_intensity": "exercise_intensity",
    "session_duration": "session_duration",
    "sedentary_time": "sedentary_time",
    "exercise_goals": "exercise_goals",
    # Exercise plan change request
    "awaiting_day1_changes": "day1_change_request",
}

GUT_CLEANSE_DIRECT_FIELD_MAP = {
    "height": "height",
    "weight": "weight",
    "health_conditions": "health_conditions",
    "medications": "medications",
    # 11-Question Meal Plan Flow
    "dietary_preference": "dietary_preference",
    "cuisine_preference": "cuisine_preference",
    "food_allergies_intolerances": "food_allergies_intolerances",
    "daily_eating_pattern": "daily_eating_pattern",
    "foods_avoid": "foods_avoid",
    "supplements": "supplements",
    "digestive_issues": "digestive_issues",
    "hydration": "hydration",
    "other_beverages": "other_beverages",
    "gut_sensitivity": "gut_sensitivity",
    # Extended Profiling
    "health_safety_screening": "health_safety_status",
    "detox_experience": "detox_experience",
    "detox_recent_reason": "detox_recent_reason",
}


# ==============================================================================
# HELPER — generic button lookup used by both APIs
# ==============================================================================

def resolve_button_text(button_id, button_title, extra_map=None):
    """
    Look up button_id in the shared map, then an optional product-specific map,
    then check regex patterns.  Falls back to button_title.
    """
    # Static dict lookups
    text = SHARED_BUTTON_MAP.get(button_id)
    if text is not None:
        return text

    if extra_map:
        text = extra_map.get(button_id)
        if text is not None:
            return text

    # Regex patterns — exercise day progression
    if RE_EXERCISE_YES_DAY.match(button_id):
        return "Yes"
    if RE_EXERCISE_NO_DAY.match(button_id):
        return "Not yet"
    # Meal day progression — value IS the button_id
    if RE_MEAL_YES_DAY.match(button_id):
        return button_id

    # Default
    return button_title or ""


# ==============================================================================
# NODE REACTION RULES
# ==============================================================================

# Helper to choose random emoji
import random

def _choose(options):
    return random.choice(options)

# Shared private rules (tuple format: pattern, emojis, reason)
# Pattern can be: str (substring), list (OR), tuple (AND)
_RULE_VERIFY = ("verify_user", ["👋🏻", "✨", "🌟"], "verify_user")
_RULE_AGE = ("age", ["🎂", "🧒", "✨"], "age")
_RULE_HEIGHT = ("height", ["📏", "📐", "✨"], "height")
_RULE_WEIGHT = ("weight", ["⚖️", "🏋️", "✨"], "weight")
_RULE_BMI = (["bmi", "calculate_bmi"], ["🧮", "📊", "ℹ️"], "bmi")
_RULE_HEALTH = ("health_conditions", ["🩺", "💚", "✨"], "health")
_RULE_MEDS = ("medications", ["💊", "💚", "✨"], "medications")
_RULE_CUISINE = ("cuisine_preference", ["🌮", "🍛", "🍝", "🍜", "🍣"], "cuisine_preference")
_RULE_SUPPLEMENTS = ("supplements", ["💊", "🧴", "✨"], "supplements")
_RULE_PLAN_REVIEW = (["plan", "review"], ["✅", "📄", "📝"], "plan_review")
_RULE_MEAL_PREF_ASK = ("ask_meal_plan_preference", ["🍱", "🥗", "✅"], "meal_preference")
_RULE_QNA = (["post_plan_qna", "qna"], ["❓", "💬", "🤝"], "qna")
_RULE_GENERATE_MEAL = (("generate", "meal"), ["⚙️", "🍱", "⏳"], "generate_meal")

# GUT CLEANSE Specific Rules
GUT_CLEANSE_REACTION_RULES = [
    _RULE_VERIFY,
    ("age_eligibility", ["🔞", "📅", "✅"], "age_verification"),
    ("gender", ["🚻", "👤", "✨"], "gender_collection"),
    ("pregnancy_check", ["🤰", "👶", "🤱"], "pregnancy_check"),
    ("health_safety_screening", ["🩺", "🛡️", "📋"], "health_safety"),
    ("detox_experience", ["🔄", "🌿", "🧘"], "detox_experience"),
    ("detox_recent_reason", ["🤔", "📝", "💭"], "detox_reason"),
    # Gut-specific naming
    ("dietary_preference", ["🌱", "🥗", "🥦"], "dietary_preference"),
    _RULE_CUISINE,
    ("food_allergies_intolerances", ["⚠️", "🌰", "🥜"], "food_allergies_intolerances"),
    ("daily_eating_pattern", ["🍽️", "🍱", "🥘"], "daily_eating_pattern"),
    ("foods_avoid", ["🚫", "❌", "⚠️"], "foods_avoid"),
    _RULE_SUPPLEMENTS,
    ("digestive_issues", ["💩", "🦠", "🌿"], "digestive_issues"),
    ("hydration", ["💧", "🚰", "🫗"], "hydration"),
    ("other_beverages", ["☕", "🧋", "🍵"], "other_beverages"),
    ("gut_sensitivity", ["🌿", "😣", "💪"], "gut_sensitivity"),
    _RULE_GENERATE_MEAL,
    _RULE_PLAN_REVIEW,
    _RULE_MEAL_PREF_ASK,
    _RULE_QNA
]

# AMS Specific Rules
AMS_REACTION_RULES = [
    _RULE_VERIFY,
    _RULE_AGE,
    _RULE_HEIGHT,
    _RULE_WEIGHT,
    _RULE_BMI,
    _RULE_HEALTH,
    _RULE_MEDS,
    # AMS-specific naming
    ("diet_preference", ["🥗", "🥬", "🥘"], "diet_preference"),
    _RULE_CUISINE,
    ("current_dishes", ["🍲", "🥣", "😋"], "current_dishes"),
    ("allergies", ["🚫", "⚠️", "🥜"], "allergies"), # Generic allergies for AMS
    ("water_intake", ["💧", "🥤", "🌊"], "water_intake"),
    ("beverages", ["☕", "🍵", "🥤"], "beverages"),
    _RULE_SUPPLEMENTS,
    ("gut_health", ["🦠", "🧬", "🧪"], "gut_health"),
    ("meal_goals", ["🎯", "⚡", "💪"], "meal_goals"),
    # Exercise specific
    ("fitness_level", ["💪", "⚡", "📊"], "fitness_level"),
    ("activity_types", ["🏃", "🧘", "🚲"], "activity_types"),
    ("exercise_frequency", ["📅", "🗓️", "⏱️"], "exercise_frequency"),
    ("exercise_intensity", ["🔥", "💨", "💪"], "exercise_intensity"),
    ("session_duration", ["⏳", "⏱️", "🕐"], "session_duration"),
    ("sedentary_time", ["🪑", "🛋️", "📺"], "sedentary_time"),
    ("exercise_goals", ["🎯", "🏆", "🌟"], "exercise_goals"),
    (("generate", "exercise"), ["⚙️", "🏋️", "⏳"], "generate_exercise"),
    _RULE_GENERATE_MEAL,
    _RULE_PLAN_REVIEW,
    _RULE_MEAL_PREF_ASK,
    ("ask_exercise_plan_preference", ["🏋️", "💪", "✅"], "exercise_preference"),
    _RULE_QNA
]


def resolve_node_reaction(node: str, rules: list) -> tuple[str, str]:
    """
    Resolves a reaction emoji based on the node name and a list of rules.

    Args:
        node: The current node name (string).
        rules: List of tuples (pattern, emojis, reason).
               Pattern can be:
               - str: substring check (or exact match for 'verify_user')
               - list: OR check (any of these substrings)
               - tuple: AND check (all of these substrings)

    Returns:
        (emoji, reason) or (None, None)
    """
    if not node:
        return None, None

    node_lower = node.lower()

    for pattern, emojis, reason in rules:
        matched = False

        if isinstance(pattern, str):
            # Special case for verify_user (exact match preferred in original logic,
            # though original logic was just checking 'in' list ["verify_user"])
            if pattern == "verify_user":
                if node_lower == "verify_user":
                    matched = True
            elif pattern in node_lower:
                matched = True

        elif isinstance(pattern, list): # OR logic
            if any(p in node_lower for p in pattern):
                matched = True

        elif isinstance(pattern, tuple): # AND logic
            if all(p in node_lower for p in pattern):
                matched = True

        if matched:
            return random.choice(emojis), reason

    return None, None
