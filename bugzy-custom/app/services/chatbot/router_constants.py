"""
Shared constants for chatbot routers.

This module consolidates common constants used across different chatbot agents
(AMS, Gut Cleanse, Free Form) to strictly type state keys, flow names,
and common values, reducing magic string usage and improving maintainability.
"""

# --- State Keys ---
# Keys used in the State TypedDict
KEY_USER_ID = "user_id"
KEY_USER_MSG = "user_msg"
KEY_USER_NAME = "user_name"
KEY_LAST_QUESTION = "last_question"
KEY_CURRENT_AGENT = "current_agent"
KEY_PENDING_NODE = "pending_node"
KEY_CONVERSATION_HISTORY = "conversation_history"
KEY_JOURNEY_HISTORY = "journey_history"
KEY_FULL_CHAT_HISTORY = "full_chat_history"
KEY_PRODUCT = "product"

# User Profile Keys
KEY_PHONE_NUMBER = "phone_number"
KEY_CRM_USER_DATA = "crm_user_data"
KEY_WHATSAPP_PUSH_NAME = "whatsapp_push_name"
KEY_AGE = "age"
KEY_HEIGHT = "height"
KEY_WEIGHT = "weight"
KEY_BMI = "bmi"

# Order Keys
KEY_USER_ORDER = "user_order"
KEY_USER_ORDER_DATE = "user_order_date"
KEY_HAS_ORDERS = "has_orders"

# --- Agent Names ---
AGENT_MEAL = "meal"
AGENT_EXERCISE = "exercise"
AGENT_SNAP = "snap"
AGENT_QNA = "post_plan_qna"
AGENT_GUT_COACH = "gut_coach"

# --- Flow States / Node Names ---
# Common
STATE_VERIFIED = "verified"
NODE_VERIFY_USER = "verify_user"
NODE_POST_PLAN_QNA = "post_plan_qna"
NODE_TRANSITION_TO_SNAP = "transition_to_snap"
NODE_SNAP_IMAGE_ANALYSIS = "snap_image_analysis"
NODE_TRANSITION_TO_GUT_COACH = "transition_to_gut_coach"

# AMS Specific
NODE_ASK_MEAL_PREFERENCE = "ask_meal_plan_preference"
NODE_ASK_EXERCISE_PREFERENCE = "ask_exercise_plan_preference"
NODE_COLLECT_HEALTH_CONDITIONS = "collect_health_conditions"
NODE_COLLECT_AGE = "collect_age"
NODE_ASK_EXISTING_MEAL_PLAN_CHOICE = "ask_existing_meal_plan_choice"
NODE_TRANSITION_TO_EXERCISE = "transition_to_exercise"
NODE_COLLECT_DIET_PREFERENCE_AMS = "collect_diet_preference"

# Gut Cleanse Specific
NODE_COLLECT_DIETARY_PREFERENCE = "collect_dietary_preference"
# ... add other GC specific nodes as needed

# --- Common Messages / Responses ---
MSG_GREETING_FALLBACK = "Hey there! 👋 I'm Bugsy."

# --- Button IDs (Common) ---
BTN_YES = "yes"
BTN_NO = "no"

# --- AMS Flow Maps ---
# Maps last_question to next_node for linear flows

AMS_MEAL_FLOW_MAP = {
    "medications": NODE_COLLECT_DIET_PREFERENCE_AMS,
    "diet_preference": "collect_cuisine_preference", 
    "cuisine_preference": "collect_current_dishes",
    "current_dishes": "collect_allergies",
    "allergies": "collect_water_intake",
    "water_intake": "collect_beverages",
    "beverages": "collect_supplements",
    "supplements": "collect_gut_health",
    "gut_health": "collect_meal_goals",
    "meal_goals": "generate_meal_plan",
    "meal_day1_plan_review": "handle_meal_day1_review_choice",
    "awaiting_meal_day1_changes": "collect_meal_day1_changes",
    "regenerating_meal_day1": "regenerate_meal_day1_plan",
    "meal_day1_revised_review": "handle_meal_day1_revised_review",
    "meal_day2_complete": "generate_meal_day3_plan",
    "meal_day3_complete": "generate_meal_day4_plan",
    "meal_day4_complete": "generate_meal_day5_plan",
    "meal_day5_complete": "generate_meal_day6_plan",
    "meal_day6_complete": "generate_meal_day7_plan",
}

AMS_EXERCISE_FLOW_MAP = {
    NODE_TRANSITION_TO_EXERCISE: "collect_fitness_level",
    "fitness_level": "collect_activity_types",
    "activity_types": "collect_exercise_frequency",
    "exercise_frequency": "collect_exercise_intensity",
    "exercise_intensity": "collect_session_duration",
    "session_duration": "collect_sedentary_time",
    "sedentary_time": "collect_exercise_goals",
    "exercise_goals": "generate_day1_plan",
    "day1_plan_review": "handle_day1_review_choice",
    "awaiting_day1_changes": "collect_day1_changes",
    "regenerating_day1": "regenerate_day1_plan",
    "day1_revised_review": "handle_day1_revised_review",
    "day2_complete": "generate_day3_plan",
    "day3_complete": "generate_day4_plan",
    "day4_complete": "generate_day5_plan",
    "day5_complete": "generate_day6_plan",
    "day6_complete": "generate_day7_plan",
}

# --- Gut Cleanse Flow Maps ---
GUT_MEAL_FLOW_MAP = {
    "dietary_preference": "collect_cuisine_preference", 
    "cuisine_preference": "collect_food_allergies_intolerances",
    "food_allergies_intolerances": "collect_daily_eating_pattern",
    "daily_eating_pattern": "collect_foods_avoid",
    "foods_avoid": "collect_supplements",
    "supplements": "collect_digestive_issues",
    "digestive_issues": "collect_hydration",
    "hydration": "collect_other_beverages",
    "other_beverages": "collect_gut_sensitivity",
    "gut_sensitivity": "generate_meal_plan",
    "meal_day1_plan_review": "handle_meal_day1_review_choice",
    "awaiting_meal_day1_changes": "collect_meal_day1_changes",
    "regenerating_meal_day1": "regenerate_meal_day1_plan",
    "meal_day1_revised_review": "handle_meal_day1_revised_review",
    "meal_day2_complete": "generate_meal_day3_plan",
    "meal_day3_complete": "generate_meal_day4_plan",
    "meal_day4_complete": "generate_meal_day5_plan",
    "meal_day5_complete": "generate_meal_day6_plan",
    "meal_day6_complete": "generate_meal_day7_plan",
}
