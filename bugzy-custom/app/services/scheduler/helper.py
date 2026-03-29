"""
Scheduler Helper Module

This module contains helper functions and constants for the scheduler service.
It includes logic for engagement windows and journey tracking helpers.
"""

import re
import logging
from datetime import datetime

import pytz

logger = logging.getLogger(__name__)

# ------------------ ENGAGEMENT WINDOW ------------------ #
def is_within_engagement_window(session_data):
    """Check if the current time (IST) is within the user's preferred engagement window."""
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist).time()

    # Handle single window case
    window = session_data.get("preferred_engagement_window")
    if window:
        start = datetime.strptime(window["start"], "%H:%M").time()
        end = datetime.strptime(window["end"], "%H:%M").time()
        return start <= now_ist <= end

    # Handle multiple windows
    windows = session_data.get("preferred_engagement_windows")
    if windows:
        for w in windows:
            start = datetime.strptime(w["start"], "%H:%M").time()
            end = datetime.strptime(w["end"], "%H:%M").time()
            if start <= now_ist <= end:
                return True
        return False

    # Default: restrict to 8-23:59 IST if no preference set
    default_start = datetime.strptime("08:00", "%H:%M").time()
    default_end = datetime.strptime("23:59", "%H:%M").time()
    return default_start <= now_ist <= default_end


# ------------------ RESUME JOURNEY TEMPLATE FUNCTIONALITY ------------------ #
# Supports both bugzy_ams and bugzy_gut_cleanse flows. All known last_question
# values from required questions, meal plan, and exercise (AMS only) nodes are
# included so resume logic works for either flow.

# All known last_question values from bugzy_ams and bugzy_gut_cleanse.
# Used only for membership: "in journey" = in this set and not post_plan_qna.
JOURNEY_ORDER = [
    # ---- bugzy_ams: user verification ----
    "verified", "age", "height", "weight", "bmi_calculated",
    # ---- bugzy_gut_cleanse: user verification / profiling ----
    "age_eligibility", "gender", "pregnancy_check",
    "health_safety_screening", "detox_experience",
    # ---- shared: meal plan preference / edit ----
    "ask_meal_plan_preference", "existing_meal_plan_choice", "select_meal_day_to_edit",
    # ---- bugzy_ams: meal plan required questions ----
    "health_conditions", "medications",
    "diet_preference", "cuisine_preference", "current_dishes", "allergies",
    "water_intake", "beverages", "supplements", "gut_health", "meal_goals",
    # ---- bugzy_gut_cleanse: meal plan required questions (11-question flow) ----
    "dietary_preference", "cuisine_preference", "food_allergies_intolerances",
    "daily_eating_pattern", "foods_avoid", "supplements", "digestive_issues",
    "hydration", "other_beverages", "gut_sensitivity",
    # ---- shared: meal plan review / generation ----
    "meal_day1_plan_review", "awaiting_meal_day1_changes", "meal_day1_complete",
    "meal_day1_revised_review", "generating_remaining_meal_days",
    "meal_day2_complete", "meal_day3_complete", "meal_day4_complete",
    "meal_day5_complete", "meal_day6_complete", "meal_plan_complete",
    # ---- bugzy_ams only: exercise transition and required questions ----
    "transitioning_to_exercise",
    "ask_exercise_plan_preference", "existing_exercise_plan_choice",
    "select_exercise_day_to_edit",
    "fitness_level", "activity_types", "exercise_frequency", "exercise_intensity",
    "session_duration", "sedentary_time", "exercise_goals",
    "generating_remaining_exercise_days",
    # ---- bugzy_ams: exercise plan review / generation ----
    "day1_plan_review", "awaiting_day1_changes", "day1_complete", "day1_revised_review",
    "day2_complete", "day3_complete", "day4_complete", "day5_complete", "day6_complete",
    "exercise_plan_complete",
    # ---- bugzy_gut_cleanse: exercise (if used) ----
    "workout_posture_gut", "workout_hydration_gut", "workout_gut_mobility_gut",
    "workout_relaxation_gut", "workout_gut_awareness_gut",
    # ---- QnA resume / completion ----
    "health_qna_answered", "product_qna_answered",
    "resuming_from_health_qna", "resuming_from_product_qna",
    "transitioning_to_gut_coach",
    "post_plan_qna",
]

# Readable step names for the resume message. Covers both flows.
STEP_DISPLAY_NAMES = {
    # bugzy_ams verification
    "verified": "Basic info",
    "age": "Age",
    "height": "Height",
    "weight": "Weight",
    "bmi_calculated": "BMI",
    # bugzy_gut_cleanse verification / profiling
    "age_eligibility": "Age eligibility",
    "gender": "Gender",
    "pregnancy_check": "Pregnancy check",
    "health_safety_screening": "Health safety",
    "detox_experience": "Detox experience",
    # meal plan preference / edit
    "ask_meal_plan_preference": "Meal plan preference",
    "existing_meal_plan_choice": "Existing meal plan choice",
    "select_meal_day_to_edit": "Select meal day to edit",
    # bugzy_ams meal questions
    "health_conditions": "Health conditions",
    "medications": "Medications",
    "diet_preference": "Diet preference",
    "cuisine_preference": "Cuisine preference",
    "current_dishes": "Current dishes",
    "allergies": "Allergies",
    "water_intake": "Water intake",
    "beverages": "Beverages",
    "supplements": "Supplements",
    "gut_health": "Gut health",
    "meal_goals": "Meal goals",
    # bugzy_gut_cleanse meal questions
    "dietary_preference": "Dietary preference",
    "food_allergies_intolerances": "Food allergies / intolerances",
    "daily_eating_pattern": "Daily eating pattern",
    "foods_avoid": "Foods to avoid",
    "digestive_issues": "Digestive issues",
    "hydration": "Hydration",
    "other_beverages": "Other beverages",
    "gut_sensitivity": "Gut sensitivity",
    # meal plan review / generation (shared)
    "meal_day1_plan_review": "Meal plan Day 1 review",
    "awaiting_meal_day1_changes": "Meal plan Day 1 changes",
    "meal_day1_complete": "Meal plan Day 1",
    "meal_day1_revised_review": "Meal plan Day 1 revised review",
    "generating_remaining_meal_days": "Meal plan generation",
    "meal_day2_complete": "Meal plan Day 2",
    "meal_day3_complete": "Meal plan Day 3",
    "meal_day4_complete": "Meal plan Day 4",
    "meal_day5_complete": "Meal plan Day 5",
    "meal_day6_complete": "Meal plan Day 6",
    "meal_plan_complete": "Meal plan",
    # bugzy_ams exercise
    "transitioning_to_exercise": "Exercise transition",
    "ask_exercise_plan_preference": "Exercise plan preference",
    "existing_exercise_plan_choice": "Existing exercise plan choice",
    "select_exercise_day_to_edit": "Select exercise day to edit",
    "fitness_level": "Fitness level",
    "activity_types": "Activity types",
    "exercise_frequency": "Exercise frequency",
    "exercise_intensity": "Exercise intensity",
    "session_duration": "Session duration",
    "sedentary_time": "Sedentary time",
    "exercise_goals": "Exercise goals",
    "generating_remaining_exercise_days": "Exercise plan generation",
    "day1_plan_review": "Exercise plan Day 1 review",
    "awaiting_day1_changes": "Exercise plan Day 1 changes",
    "day1_complete": "Exercise plan Day 1",
    "day1_revised_review": "Exercise plan Day 1 revised review",
    "day2_complete": "Exercise plan Day 2",
    "day3_complete": "Exercise plan Day 3",
    "day4_complete": "Exercise plan Day 4",
    "day5_complete": "Exercise plan Day 5",
    "day6_complete": "Exercise plan Day 6",
    "exercise_plan_complete": "Exercise plan",
    # bugzy_gut_cleanse exercise
    "workout_posture_gut": "Workout posture",
    "workout_hydration_gut": "Workout hydration",
    "workout_gut_mobility_gut": "Workout mobility",
    "workout_relaxation_gut": "Workout relaxation",
    "workout_gut_awareness_gut": "Workout gut awareness",
    # QnA / completion
    "health_qna_answered": "Health Q&A",
    "product_qna_answered": "Product Q&A",
    "resuming_from_health_qna": "Health Q&A",
    "resuming_from_product_qna": "Product Q&A",
    "transitioning_to_gut_coach": "Gut coach transition",
    "post_plan_qna": "Post-plan Q&A",
}

# Dynamic last_question patterns -> display format (regex match, format string with group 1)
_STEP_DISPLAY_PATTERNS = [
    (re.compile(r"^awaiting_meal_day(\d+)_edit_changes$"), "Meal plan Day {} edit"),
    (re.compile(r"^awaiting_exercise_day(\d+)_edit_changes$"), "Exercise plan Day {} edit"),
]


def get_step_display_name(last_question: str) -> str:
    """Get a readable display name for the step. Handles dynamic patterns for edit flows."""
    if not last_question:
        return "your progress"
    key = last_question.strip()
    if key in STEP_DISPLAY_NAMES:
        return STEP_DISPLAY_NAMES[key]
    for pattern, fmt in _STEP_DISPLAY_PATTERNS:
        m = pattern.match(key)
        if m:
            return fmt.format(m.group(1))
    return key.replace("_", " ").title()


def is_user_in_journey(last_question: str) -> bool:
    """
    Check if user is still in journey (has not reached post_plan_qna).
    Supports both bugzy_ams and bugzy_gut_cleanse: any known step except
    post_plan_qna counts as in-journey. Dynamic steps (e.g. awaiting_meal_day3_edit_changes)
    are treated as in-journey if they match known patterns.
    """
    if not last_question:
        return False
    lq = last_question.strip()
    if lq == "post_plan_qna":
        return False
    if lq in JOURNEY_ORDER:
        return True
    for pattern, _ in _STEP_DISPLAY_PATTERNS:
        if pattern.match(lq):
            return True
    return False