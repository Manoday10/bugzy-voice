"""
Context manager for bugzy_free_form agent.

Slim context: no meal/exercise plans, only user name, order, and conversation.
"""

import logging
from typing import List, Dict, Optional

from app.services.crm.sessions import load_meal_plan, load_exercise_plan
from app.services.chatbot.bugzy_free_form.state import State
from app.services.chatbot.bugzy_shared.context import (
    build_profile_memory_from_mapping,
    detect_user_intent,
    detect_followup_question,
    INTENT_MEAL,
    INTENT_PRODUCT,
    INTENT_HEALTH,
    INTENT_GENERAL,
    INTENT_EXERCISE,
)

logger = logging.getLogger(__name__)


def build_profile_memory(state: State) -> str:
    """
    Build user profile from available data across all modules.
    All fields are optional - only includes what exists in state.
    """
    
    mapping = [
        # Core identity
        {"key": "user_name", "label": "Name"},
        {"key": "user_order", "label": "Order"},
        {"key": "user_order_date", "label": "Order date"},
        
        # === AMS Module Variables (Optional) ===
        # Basic profiling
        {"key": "age", "label": "Age"},
        {"key": "height", "label": "Height", "suffix": " cm"},
        {"key": "weight", "label": "Weight", "suffix": " kg"},
        {"key": "bmi", "label": "BMI"},
        {"key": "bmi_category", "label": "BMI Category"},
        
        # Health info
        {"key": "health_conditions", "label": "Health Conditions"},
        {"key": "medications", "label": "Medications"},
        
        # AMS Meal preferences (9 questions)
        {"key": "diet_preference", "label": "Diet"},
        {"key": "cuisine_preference", "label": "Cuisine"},
        {"key": "allergies", "label": "Allergies"},
        {"key": "water_intake", "label": "Water"},
        {"key": "beverages", "label": "Beverages"},
        {"key": "supplements", "label": "Supplements"},
        {"key": "gut_health", "label": "Gut Health"},
        {"key": "meal_goals", "label": "Meal Goals"},
        
        # AMS Exercise preferences (FITT - 7 questions)
        {"key": "fitness_level", "label": "Fitness"},
        {"key": "activity_types", "label": "Activities"},
        {"key": "exercise_goals", "label": "Exercise Goals"},
        
        # === Gut Cleanse Module Variables (Optional) ===
        # Safety screening
        {"key": "age_eligible", "label": "Age Eligible (18+)"},
        {"key": "gender", "label": "Gender"},
        {"key": "is_pregnant", "label": "Pregnant"},
        {"key": "is_breastfeeding", "label": "Breastfeeding"},
        {"key": "health_safety_status", "label": "Health Safety"},
        {"key": "detox_experience", "label": "Detox Experience"},
        
        # Gut Cleanse meal preferences (11 questions)
        {"key": "dietary_preference", "label": "Dietary Pref"},
        {"key": "food_allergies_intolerances", "label": "Food Allergies"},
        {"key": "daily_eating_pattern", "label": "Eating Pattern"},
        {"key": "foods_avoid", "label": "Foods to Avoid"},
        {"key": "digestive_issues", "label": "Digestive Issues"},
        {"key": "hydration", "label": "Hydration"},
        {"key": "other_beverages", "label": "Other Beverages"},
        {"key": "gut_sensitivity", "label": "Gut Sensitivity"},
        
        # Plan status
        {"transform": lambda _, s: "Meal Plan: Active" if s.get("meal_plan_sent") else None},
        {"transform": lambda _, s: "Exercise Plan: Active" if s.get("exercise_plan_sent") else None},
    ]

    profile = build_profile_memory_from_mapping(state, mapping)
    if not profile:
        profile = "No profile data"
    
    # DEBUG: Log what we found (use root logger to ensure it shows)
    import logging as root_logging
    # Count parts by split to estimate fields
    parts_count = len([p for p in profile.split("; ") if p and p != "No profile data"])
    root_logging.info("🔍 [FREE_FORM] Profile built with %d fields: %s", 
                      parts_count, profile[:200] + "..." if len(profile) > 200 else profile)
    
    return profile


def _get_meal_plan_content(state: State, max_chars: int) -> str:
    """Helper to extract relevant meal plan days."""
    user_id = state.get("user_id", "")
    
    # Try to load from state first
    if state.get("meal_day1_plan") or state.get("meal_plan"):
        meal_plan_db = {}
    else:
        # DB Load Strategy for Free Form (Migrated Users)
        import logging as root_logging
        
        # 1. Try generic load
        meal_plan_db = load_meal_plan(user_id) or {}
        root_logging.info("🔍 [FREE_FORM] Generic load_meal_plan result keys: %s", list(meal_plan_db.keys()))
        
        # 2. If empty, explicit try "ams"
        if not meal_plan_db:
            meal_plan_db = load_meal_plan(user_id, product="ams") or {}
            root_logging.info("🔍 [FREE_FORM] Fallback 'ams' load_meal_plan result keys: %s", list(meal_plan_db.keys()))
            
        # 3. If empty, explicit try "gut_cleanse"
        if not meal_plan_db:
             meal_plan_db = load_meal_plan(user_id, product="gut_cleanse") or {}
             root_logging.info("🔍 [FREE_FORM] Fallback 'gut_cleanse' load_meal_plan result keys: %s", list(meal_plan_db.keys()))
             
        if meal_plan_db:
            root_logging.info("🔍 [FREE_FORM] FINAL Found meal plan in DB (product: %s)", meal_plan_db.get("product"))
        else:
            root_logging.warning("⚠️ [FREE_FORM] No meal plan found for %s after all attempts", user_id)

    days_content = []
    for d in range(1, 8):
        key = f"meal_day{d}_plan"
        content = state.get(key) or meal_plan_db.get(key)
        if content:
            days_content.append(content)
            
    if not days_content:
        full_plan = state.get("meal_plan") or meal_plan_db.get("meal_plan") or ""
        return full_plan[:max_chars] if full_plan else ""
        
    full_text = "\n\n".join(days_content)
    if len(full_text) > max_chars:
        return full_text[:max_chars] + "...[truncated]"
    return full_text


def _get_exercise_plan_content(state: State, max_chars: int) -> str:
    """Helper to extract relevant exercise plan days."""
    user_id = state.get("user_id", "")
    
    if state.get("day1_plan") or state.get("exercise_plan"):
        ex_plan_db = {}
    else:
        import logging as root_logging
        
        # DB Load Strategy: generic -> ams -> gut_cleanse
        ex_plan_db = load_exercise_plan(user_id) or {}
        root_logging.info("🔍 [FREE_FORM] Generic load_exercise_plan result keys: %s", list(ex_plan_db.keys()))
        
        if not ex_plan_db:
            ex_plan_db = load_exercise_plan(user_id, product="ams") or {}
            root_logging.info("🔍 [FREE_FORM] Fallback 'ams' load_exercise_plan result keys: %s", list(ex_plan_db.keys()))
            
        if not ex_plan_db:
             ex_plan_db = load_exercise_plan(user_id, product="gut_cleanse") or {}
             root_logging.info("🔍 [FREE_FORM] Fallback 'gut_cleanse' load_exercise_plan result keys: %s", list(ex_plan_db.keys()))

        if ex_plan_db:
            root_logging.info("🔍 [FREE_FORM] FINAL Found exercise plan in DB (product: %s)", ex_plan_db.get("product"))
        else:
            root_logging.warning("⚠️ [FREE_FORM] No exercise plan found for %s after all attempts", user_id)

    days_content = []
    for d in range(1, 8):
        key = f"day{d}_plan"
        content = state.get(key) or ex_plan_db.get(key)
        if content:
            days_content.append(content)
            
    if not days_content:
        full_plan = state.get("exercise_plan") or ex_plan_db.get("exercise_plan") or ""
        return full_plan[:max_chars] if full_plan else ""
        
    full_text = "\n\n".join(days_content)
    if len(full_text) > max_chars:
        return full_text[:max_chars] + "...[truncated]"
    return full_text


def build_plan_memory(state: State, intent: str, max_chars: int = 3000) -> str:
    """Load meal OR exercise plan ONLY if relevant to intent."""
    if intent == INTENT_MEAL:
        return _get_meal_plan_content(state, max_chars)
    elif intent == INTENT_EXERCISE:
        return _get_exercise_plan_content(state, max_chars)
    return ""


def build_session_memory(state: State, max_messages: int = 6) -> List[Dict]:
    """Last N messages from conversation_history."""
    history = state.get("conversation_history", []) or []
    return history[-max_messages:] if history else []




def build_optimized_context(
    state: State,
    user_question: str,
    llm_client,
    intent: Optional[str] = None,
    include_plans: bool = True,
    max_recent_messages: int = 6,
) -> str:
    """Build context string for post_plan_qna with optional plans."""
    if intent is None:
        intent = detect_user_intent(user_question, state)
    
    history = state.get("conversation_history", []) or []
    is_followup = detect_followup_question(user_question, history)
    profile = build_profile_memory(state)
    
    # Increase context window for follow-ups
    if is_followup:
        max_recent_messages = max(8, max_recent_messages)
        
    recent = build_session_memory(state, max_recent_messages)
    recent_str = "\n".join([f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}" for m in recent])

    # Load Plans if relevant
    plan_mem = ""
    if include_plans:
        plan_mem = build_plan_memory(state, intent)
        if plan_mem:
            import logging as root_logging
            root_logging.info("🔍 [FREE_FORM] Loaded %s plan content (%d chars)", intent, len(plan_mem))

    # PRIORITY ORDER: Profile → Recent Messages → Plans → Order
    parts = [f"**User Profile**\n{profile}"]
    
    # Recent conversation history (prioritized)
    if recent_str:
        header = "**Recent Conversation (Follow-up)**" if is_followup else "**Recent Conversation**"
        parts.append(f"{header}\n{recent_str}")
        logger.info("🔍 [FREE_FORM] Including %d recent messages in context", len(recent))
    
    # Plan Content (Contextual)
    if plan_mem:
        plan_title = "Meal Plan" if intent == INTENT_MEAL else "Exercise Plan"
        parts.append(f"**User's {plan_title}**\n{plan_mem}")
    
    # Order info (secondary context, skip if follow-up on specific topic to avoid distraction)
    if state.get("user_order") and not is_followup:
        parts.append(f"**User Order**\n{state.get('user_order')}" + (f" (Date: {state.get('user_order_date')})" if state.get("user_order_date") else ""))
    
    return "\n\n".join(parts)
