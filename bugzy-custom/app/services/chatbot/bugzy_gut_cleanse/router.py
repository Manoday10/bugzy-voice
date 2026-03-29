"""
Router functions for the chatbot agent.

This module contains the main routing logic that determines which node
to execute next based on the current state of the conversation.
"""

import random
import logging
import re
from typing import Optional
from app.services.chatbot.bugzy_gut_cleanse.state import State
from app.services.chatbot.bugzy_gut_cleanse.constants import (
    QUESTION_TO_NODE,
    EDIT_EXISTING_MEAL_PLAN,
    CREATE_NEW_MEAL_PLAN,
    HEALTH_SAFETY_CONDITION_MAP,
    resolve_health_safety_status,
)
from app.services.chatbot.router_constants import (
    KEY_USER_ID, KEY_USER_MSG, KEY_LAST_QUESTION, KEY_PENDING_NODE,
    KEY_CURRENT_AGENT, KEY_CONVERSATION_HISTORY, KEY_USER_NAME,
    NODE_VERIFY_USER, NODE_POST_PLAN_QNA, NODE_TRANSITION_TO_SNAP,
    NODE_SNAP_IMAGE_ANALYSIS, NODE_TRANSITION_TO_GUT_COACH,
    NODE_ASK_MEAL_PREFERENCE, NODE_COLLECT_DIETARY_PREFERENCE,
    STATE_VERIFIED, AGENT_MEAL, AGENT_SNAP, AGENT_GUT_COACH, AGENT_QNA,
    GUT_MEAL_FLOW_MAP, KEY_AGE, KEY_HEIGHT, KEY_WEIGHT, KEY_BMI
)
from app.services.whatsapp.client import send_whatsapp_message, _send_whatsapp_list
from app.services.whatsapp.utils import _store_system_message, _update_last_answer_in_history, _store_question_in_history
from app.services.crm.sessions import load_meal_plan
from app.services.prompts.gut_cleanse.health_product_detection import is_health_question, is_product_question
from app.services.chatbot.bugzy_shared.context import is_meal_edit_request
from app.services.chatbot.bugzy_shared.qna import is_any_product_query
from app.services.chatbot.bugzy_gut_cleanse.intent_helpers import (
    _contains_word,
    _is_affirmative,
    _is_negative_or_defer,
)
logger = logging.getLogger(__name__)


def _is_greeting_message(text: str) -> bool:
    """Return True if the message is a short greeting/salutation without other intent."""
    if not text:
        return False
    msg = text.strip().lower()
    greetings = {
        "hi", "hello", "hey", "heyy", "heyyy", "hiya", "yo", "sup", "namaste",
        "good morning", "gm", "good afternoon", "good evening", "ge",
        "morning", "afternoon", "evening", "hola", "hii", "helloo"
    }
    # Normalize whitespace and basic punctuation variants
    msg = " ".join(msg.split())
    if msg in greetings:
        return True
    tokens = msg.split()
    if tokens and tokens[0] in greetings and len(tokens) <= 3:
        return True
    stripped = msg.replace("!", "").replace(".", "").replace(",", "")
    if stripped in greetings:
        return True
    return False

def _has_completed_weight(state: dict) -> bool:
    """Legacy function: Check if user has provided age, height, and weight (old profiling).
    Now checks for new profiling fields: age_eligible and gender."""
    # Check new profiling fields first
    has_new_profiling = (
        state.get("age_eligible") is not None and
        state.get("gender") is not None
    )
    if has_new_profiling:
        return True
    # Fallback to legacy fields for backward compatibility
    return (
        bool((state.get(KEY_AGE) or "").strip()) and
        bool((state.get(KEY_HEIGHT) or "").strip()) and
        bool((state.get(KEY_WEIGHT) or "").strip())
    )

def _has_any_profiling_data(state: dict) -> bool:
    """Check if user has ANY profiling data (new or legacy).
    Used to detect legacy sessions with partial profiling."""
    # Check new profiling fields first
    has_new_profiling = (
        state.get("age_eligible") is not None or
        state.get("gender") is not None
    )
    if has_new_profiling:
        return True
    # Fallback to legacy fields for backward compatibility
    return (
        bool((state.get(KEY_AGE) or "").strip()) or
        bool((state.get(KEY_HEIGHT) or "").strip()) or
        bool((state.get(KEY_WEIGHT) or "").strip())
    )

def _is_at_or_after_health_conditions(state: dict) -> bool:
    """Check if last_question is at or after meal planning flow (dietary_preference or later)."""
    order = [
        "verified", "age", "height", "weight", "bmi_calculated",
        # gut_cleanse meal flow: first question is dietary_preference (11-question meal plan)
        "dietary_preference", "cuisine_preference", "food_allergies_intolerances", "daily_eating_pattern", "foods_avoid", "supplements", "digestive_issues", "hydration", "other_beverages", "gut_sensitivity",
        "meal_day1_plan_review", "awaiting_meal_day1_changes",
        "regenerating_meal_day1", "meal_day1_revised_review",
        "meal_day1_complete", "meal_day2_complete", "meal_day3_complete",
        "meal_day4_complete", "meal_day5_complete", "meal_day6_complete",
        "generate_meal_plan", "meal_plan_complete", "transition_to_snap", "snap_complete",
        "transitioning_to_gut_coach", "post_plan_qna"
    ]
    lq = (state.get("last_question") or "").strip()
    if lq not in order:
        return False
    # Check if we're at or after dietary_preference (first meal planning question)
    # since health_conditions doesn't exist in gut_cleanse flow
    if "dietary_preference" not in order:
        return False
    return order.index(lq) >= order.index("dietary_preference")

def _get_resume_node_gut_cleanse(state: State) -> str:
    """Find the next missing question in the Gut Cleanse journey."""
    # 1. Basic Profiling
    if state.get("age_eligible") is None:
        return "collect_age_eligibility"
    
    # Handle underage confirmation
    if state.get("age_eligible") is False and state.get("age_warning_confirmed") is None:
        return "collect_age_warning_confirmation"

    if state.get("gender") is None:
        return "collect_gender"
    
    if (state.get("gender") or "").lower() == "female":
        if state.get("is_pregnant") is None and state.get("is_breastfeeding") is None:
            return "collect_pregnancy_check"
        if (state.get("is_pregnant") or state.get("is_breastfeeding")) and state.get("pregnancy_warning_confirmed") is None:
            return "collect_pregnancy_warning_confirmation"

    if state.get("health_safety_status") is None:
        return "collect_health_safety_screening"

    if state.get("detox_experience") is None:
        return "collect_detox_experience"
    
    # Detox reason follow-up if experience is recent
    if state.get("detox_experience") == "recent" and state.get("detox_recent_reason") is None:
        return "collect_detox_experience"  # This node handles the follow-up

    # 2. Meal Planning Profiling (11-Question Flow)
    meal_flow = [
        ("dietary_preference", "dietary_preference"),
        ("cuisine_preference", "cuisine_preference"),
        ("food_allergies_intolerances", "food_allergies_intolerances"),
        ("daily_eating_pattern", "daily_eating_pattern"),
        ("foods_avoid", "foods_avoid"),
        ("supplements", "supplements"),
        ("digestive_issues", "digestive_issues"),
        ("hydration", "hydration"),
        ("other_beverages", "other_beverages"),
        ("gut_sensitivity", "gut_sensitivity")
    ]
    
    for field, lq_name in meal_flow:
        val = state.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return QUESTION_TO_NODE.get(lq_name, "collect_dietary_preference")

    # If all profiling is done, check if meal plan is sent
    if not state.get("meal_plan_sent"):
        return "generate_meal_plan"
        
    return "transition_to_snap"

def _should_apply_greeting_resume(state: dict) -> bool:
    """Apply greeting-resume only if not in post_plan_qna, weight done, and at/after health_conditions."""
    if state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA or state.get(KEY_LAST_QUESTION) == NODE_POST_PLAN_QNA:
        return False
    if not _has_completed_weight(state):
        return False
    return _is_at_or_after_health_conditions(state)

def _is_resume_journey_button(text: str) -> bool:
    """Return True if the message is a resume journey button click."""
    if not text:
        return False
    msg = text.strip().lower()
    # Check for resume journey button markers
    return msg == "resume_journey" or msg == "resume" or "resume journey" in msg

def _should_apply_resume_button_resume(state: dict) -> bool:
    """Apply resume-button-resume only if not in post_plan_qna, weight done, and at/after health_conditions."""
    if state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA or state.get(KEY_LAST_QUESTION) == NODE_POST_PLAN_QNA:
        return False
    if not _has_completed_weight(state):
        return False
    return _is_at_or_after_health_conditions(state)


def is_journey_restart_request(user_msg: str) -> Optional[str]:
    """
    Detect if user wants to start/restart a meal plan journey.
    Returns 'meal' or None.
    """
    if not user_msg:
        return None
    
    text = user_msg.lower()
    
    import re
    
    # Check meal patterns with regex for typo tolerance (e.g., "plam", "pla")
    # Matches: meal plan, meal plam, meal pla, diet plan, food plan, etc.
    meal_pattern_regex = r'(meal|diet|nutrition|food|eating)\s+(plan|journey|plam|pla|program|schedule)'
    wants_meal = bool(re.search(meal_pattern_regex, text))
    
    # Refine intent verbs (want, create, start, give, make)
    intent_verbs = [
        "want", "need", "give", "make", "create", "start", "begin", "can i have",
        "get", "send", "show", "build", "generate", "would like", "interested in"
    ]
    has_intent = any(v in text for v in intent_verbs)
    
    # Negative filtering
    negative_patterns = ["don't want", "no ", "stop", "cancel", "hate", "dislike", "already have"]
    is_negative = any(p in text for p in negative_patterns)
    
    if is_negative:
        return None
        
    # If explicit intent verb is present OR simple short phrase like "meal plan please"
    if has_intent or len(text.split()) <= 5:
        if wants_meal:
            return "meal"
            
    return None

def is_question_statement(text: str) -> bool:
    """
    Check if the text is a question (asking for information) rather than a statement (providing information).
    Returns True if the text appears to be a question.
    """
    if not text:
        return False
    
    text_lower = text.strip().lower()
    
    # Check for question mark
    if '?' in text:
        return True
    
    # Check for question words at the start
    question_starters = [
        'what', 'how', 'why', 'when', 'where', 'who', 'which', 'whom', 'whose',
        'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might',
        'do', 'does', 'did', 'is', 'are', 'was', 'were', 'has', 'have', 'had',
        'am i', 'is it', 'are there', 'is there', 'can i', 'should i', 'do i',
        'tell me', 'show me', 'explain', 'help me', 'any', 'recommend'
    ]
    
    # Check if text starts with any question starter
    words = text_lower.split()
    if words and any(text_lower.startswith(starter) for starter in question_starters):
        return True
    
    # Check for question phrases anywhere in the text
    question_phrases = [
        'can you tell', 'could you tell', 'do you know', 'would you recommend',
        'what about', 'how about', 'is it okay', 'is it safe', 'is it good',
        'should i take', 'can i take', 'may i', 'could i'
    ]
    
    if any(phrase in text_lower for phrase in question_phrases):
        return True
    
    return False


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


def extract_day_number(user_msg: str) -> Optional[int]:
    """
    Extract day number from user message.
    Supports formats like "Day 3", "day 2", "third day", etc.
    Returns day number (1-7) or None if not found.
    """
    if not user_msg:
        return None
    
    user_msg_lower = user_msg.lower()
    
    # Check for numeric day formats (Day 1, day 2, etc.)
    import re
    numeric_pattern = r'\bday\s*(\d)\b'
    match = re.search(numeric_pattern, user_msg_lower)
    if match:
        day_num = int(match.group(1))
        if 1 <= day_num <= 7:
            return day_num
    
    # Check for ordinal day formats (first day, second day, etc.)
    ordinal_map = {
        'first': 1, '1st': 1,
        'second': 2, '2nd': 2,
        'third': 3, '3rd': 3,
        'fourth': 4, '4th': 4,
        'fifth': 5, '5th': 5,
        'sixth': 6, '6th': 6,
        'seventh': 7, '7th': 7
    }
    
    for ordinal, num in ordinal_map.items():
        if ordinal in user_msg_lower:
            return num
    
    return None


# --- Main Router Functions ---

def router(state: State) -> str:
    """Central brain that decides the next step based on saved state."""
    # Import handle_validated_input here to avoid circular imports
    from app.services.chatbot.bugzy_gut_cleanse.nodes.user_verification_nodes import handle_validated_input
    from app.services.chatbot.bugzy_gut_cleanse.nodes.qna_nodes import is_contextual_product_question
    
    logger.info("ROUTING with state keys: %s", state.keys())
    
    user_msg = state.get(KEY_USER_MSG, "").lower().strip()
    
    # Check for restart command
    if user_msg == "restart":
        return NODE_VERIFY_USER

    # BULLETPROOF: "Make Changes" on Day 1 meal plan → always go to collect changes (ask "what changes?")
    # Matches: button ids (in SHARED_BUTTON_MAP). Ignores last_question (e.g. stale voice_agent_promotion_meal).
    _make_changes_meal = (
        "make_changes_meal_day1" in user_msg or "more_changes_meal_day1" in user_msg
    )
    if _make_changes_meal:
        logger.info(
            "ROUTER: Make Changes (meal Day 1) → handle_meal_day1_review_choice (last_q=%s)",
            state.get(KEY_LAST_QUESTION),
        )
        return "handle_meal_day1_review_choice"

    # Greeting-only messages: only resume if not in post_plan_qna,
    # weight completed, and at/after health_conditions
    if _is_greeting_message(state.get(KEY_USER_MSG, "")) and _should_apply_greeting_resume(state):
        pending = state.get(KEY_PENDING_NODE)

        # Send a friendly resume/transition message before asking the question again
        try:
            resume_msgs = [
                "💚 Let's pick up where we left off...",
                "🌟 Now, back to your personalized plan...",
                "✨ Great! Let's continue with your wellness journey...",
                "💫 Perfect! Now let's get back to creating your plan...",
                "🌸 Awesome! Let's continue where we paused...",
                "💝 Thanks for that! Now, back to your plan...",
                "🌿 Got it! Let's resume building your wellness plan...",
                "💖 Hope that helped! Now, let's continue...",
                "🌺 Wonderful! Let's get back to your personalized journey...",
                "✨ That's sorted! Now, back to crafting your plan...",
                "💚 Perfect! Let's continue with the next step...",
                "🌟 Great! Let's pick up where we were..."
            ]
            send_whatsapp_message(state["user_id"], random.choice(resume_msgs))
        except Exception as _e:
            pass
        if pending:
            # Map last_question values to actual node names if needed
            question_to_node_map = {
                "meal_day1_plan_review": "handle_meal_day1_review_choice",
                "meal_day1_revised_review": "handle_meal_day1_revised_review",
                "generate_meal_day1_plan": "generate_meal_plan",
            }
            # If pending is a last_question value, map it to the actual node
            mapped_pending = question_to_node_map.get(pending, pending)
            logger.info("GREET ROUTE - Greeting detected, resuming pending node: %s (original pending: %s)", mapped_pending, pending)
            return mapped_pending
        current_question = state.get(KEY_LAST_QUESTION)
        question_to_node = QUESTION_TO_NODE
        if current_question in question_to_node:
            node = question_to_node[current_question]
            logger.info("GREET ROUTE - Greeting detected, resuming current step: %s", node)
            return node
        logger.info("GREET ROUTE - Greeting detected but insufficient context; verifying user")
        return NODE_VERIFY_USER
    
    # Resume journey button clicks: resume as long as not in post_plan_qna
    # Removed restrictive checks for weight/health_conditions to allow resume at any point
    if _is_resume_journey_button(state.get(KEY_USER_MSG, "")) and not (state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA or state.get(KEY_LAST_QUESTION) == NODE_POST_PLAN_QNA):
        pending = state.get(KEY_PENDING_NODE)

        # Send a friendly resume/transition message before asking the question again
        try:
            resume_msgs = [
                "💚 Let's pick up where we left off...",
                "🌟 Now, back to your personalized plan...",
                "✨ Great! Let's continue with your wellness journey...",
                "💫 Perfect! Now let's get back to creating your plan...",
                "🌸 Awesome! Let's continue where we paused...",
                "💝 Thanks for that! Now, back to your plan...",
                "🌿 Got it! Let's resume building your wellness plan...",
                "💖 Hope that helped! Now, let's continue...",
                "🌺 Wonderful! Let's get back to your personalized journey...",
                "✨ That's sorted! Now, back to crafting your plan...",
                "💚 Perfect! Let's continue with the next step...",
                "🌟 Great! Let's pick up where we were..."
            ]
            send_whatsapp_message(state[KEY_USER_ID], random.choice(resume_msgs))
        except Exception as _e:
            pass
        if pending:
            # Map last_question values to actual node names if needed
            question_to_node_map = {
                "meal_day1_plan_review": "handle_meal_day1_review_choice",
                "meal_day1_revised_review": "handle_meal_day1_revised_review",
                "generate_meal_day1_plan": "generate_meal_plan",
            }
            # If pending is a last_question value, map it to the actual node
            mapped_pending = question_to_node_map.get(pending, pending)
            logger.info("RESUME BUTTON ROUTE - Resume button detected, resuming pending node: %s (original pending: %s)", mapped_pending, pending)
            return mapped_pending
        current_question = state.get(KEY_LAST_QUESTION)
        question_to_node = QUESTION_TO_NODE
        if current_question in question_to_node:
            node = question_to_node[current_question]
            logger.info("RESUME BUTTON ROUTE - Resume button detected, resuming current step: %s", node)
            return node
        logger.info("RESUME BUTTON ROUTE - Resume button detected but insufficient context; verifying user")
        return NODE_VERIFY_USER
    
    # PRIORITY: Check for PLAN EDIT FLOW states FIRST (before post-plan routing)
    # This ensures edit requests are handled even when both plans are completed
    if state.get(KEY_LAST_QUESTION) == "select_meal_day_to_edit":
        return "handle_meal_day_selection_for_edit"
    elif state.get(KEY_LAST_QUESTION) and str(state.get(KEY_LAST_QUESTION)).startswith("awaiting_meal_day") and str(state.get(KEY_LAST_QUESTION)).endswith("_edit_changes"):
        return "collect_meal_day_edit_changes"
    elif state.get(KEY_LAST_QUESTION) == "existing_meal_plan_choice":
        # IMPORTANT: This must be handled before post-plan routing,
        # otherwise we'll always get forced into post_plan_qna.
        msg = (state.get(KEY_USER_MSG) or "").lower().strip()
        logger.info("🔍 ROUTER (GUT_CLEANSE): Handling existing_meal_plan_choice, user_msg='%s'", msg)
        
        if msg == EDIT_EXISTING_MEAL_PLAN or "edit" in msg:
            state["wants_meal_plan"] = True
            return "load_existing_meal_plan_for_edit"
        if msg == CREATE_NEW_MEAL_PLAN or "create" in msg or "new" in msg or "fresh" in msg or "restart" in msg:
            logger.info("🔍 ROUTER (GUT_CLEANSE): User chose CREATE NEW MEAL PLAN")
            logger.info("🔍 ROUTER (GUT_CLEANSE): State before changes:")
            logger.info("  - current_agent: %s", state.get(KEY_CURRENT_AGENT))
            logger.info("  - existing_meal_plan_choice_origin: %s", state.get("existing_meal_plan_choice_origin"))
            logger.info("  - meal_plan_sent: %s", state.get("meal_plan_sent"))
            
            state["wants_meal_plan"] = True
            
            # CRITICAL FIX: Check if user was in post_plan_qna BEFORE changing current_agent
            # This is the key to detecting recreation vs first-time creation
            was_in_post_plan = (
                state.get("existing_meal_plan_choice_origin") == NODE_POST_PLAN_QNA or
                state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA
            )
            
            logger.info("🔍 ROUTER (GUT_CLEANSE): was_in_post_plan = %s", was_in_post_plan)
            
            # Now change the agent
            state[KEY_CURRENT_AGENT] = AGENT_MEAL
            
            # If we're in post-plan context, ensure we don't get stuck in post_plan_qna routing.
            if state.get("meal_plan_sent"):
                state["meal_plan_sent"] = False
            
            # Set journey_restart_mode if this was a recreation from post_plan_qna
            if was_in_post_plan:
                state["journey_restart_mode"] = True
                state["existing_meal_plan_choice_origin"] = NODE_POST_PLAN_QNA  # Set it here for consistency
                logger.info("🔄 JOURNEY RESTART MODE (GUT_CLEANSE): Set to True (user recreating meal plan from post_plan_qna)")
            else:
                logger.info("⚠️  ROUTER (GUT_CLEANSE): NOT setting journey_restart_mode (was_in_post_plan=False)")
            
            logger.info("🔍 ROUTER (GUT_CLEANSE): State after changes:")
            logger.info("  - journey_restart_mode: %s", state.get("journey_restart_mode"))
            logger.info("  - existing_meal_plan_choice_origin: %s", state.get("existing_meal_plan_choice_origin"))
            logger.info("  - current_agent: %s", state.get(KEY_CURRENT_AGENT))
            logger.info("  - meal_plan_sent: %s", state.get("meal_plan_sent"))
            
            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return NODE_COLLECT_DIETARY_PREFERENCE
            return "collect_age_eligibility"
        return "ask_existing_meal_plan_choice"
    
    # PRIORITY: Check if we're in post-plan state (meal plan completed)
    # BUT NOT if we're still in the SNAP image analysis flow or meal plan completion
    # AND NOT if we're in the middle of creating a NEW meal plan (Create New Plan questionnaire)
    # AND NOT if we're in journey_restart_mode (recreating meal plan from post_plan_qna)
    if (state.get("meal_plan_sent") and not state.get("journey_restart_mode")) or state.get(KEY_LAST_QUESTION) == NODE_POST_PLAN_QNA:
        # Exception: If we're waiting for image analysis, transitioning, or completing meal plan, don't skip to post_plan_qna yet
        if state.get(KEY_LAST_QUESTION) in ["snap_complete", "transitioning_to_snap", "transitioning_to_gut_coach", "meal_plan_complete"]:
            # Continue with normal flow to handle SNAP or meal plan completion
            pass
        # Exception: If we're in the meal plan questionnaire (Create New Plan flow), continue questionnaire, do NOT go to post_plan_qna
        elif state.get(KEY_LAST_QUESTION) in [
            "dietary_preference", "cuisine_preference", "food_allergies_intolerances",
            "daily_eating_pattern", "foods_avoid", "supplements", "digestive_issues",
            "hydration", "other_beverages", "gut_sensitivity",
        ]:
            pass  # Fall through to meal agent routing (e.g. dietary_preference -> collect_cuisine_preference)
        else:
            # Route all questions to post-plan Q&A handler
            return NODE_POST_PLAN_QNA
    
    # PRIORITY: Check for health and product questions BEFORE validation
    # Same as bugzy_ams: during meal journey (including Create New Plan flow), if user asks
    # a health/product question we interrupt, answer it, then resume back to the same step via pending_node.
    # Check if user is asking a product/company question
    # Strictly use shared is_any_product_query for consistent detection
    conversation_history = state.get(KEY_CONVERSATION_HISTORY, [])
    if is_any_product_query(user_msg, conversation_history):
        logger.info("ROUTER PRODUCT DETECTION (GUT) | Product query detected | msg='%s'", user_msg)
        
        # Check if meal plan is completed - if so, route to post_plan_qna
        plan_completed = bool(state.get("meal_plan_sent")) and not bool(state.get("journey_restart_mode"))

        if plan_completed:
            return NODE_POST_PLAN_QNA
        
        # Handle product questions during data collection
        current_question = state.get(KEY_LAST_QUESTION)
        if current_question and current_question not in [None, STATE_VERIFIED, NODE_POST_PLAN_QNA, "health_qna_answered", "product_qna_answered"]:
            state[KEY_PENDING_NODE] = QUESTION_TO_NODE.get(current_question, NODE_ASK_MEAL_PREFERENCE)
        return "product_qna"

    
    # Check if user is asking a health question
    # IMPORTANT: Do NOT treat as health question when user is answering a list/button (e.g. health_safety_screening)
    # — their reply (e.g. "Constipation", "IBS/IBD") would be mis-detected as a health question and hijack the flow
    # Note: age_eligibility and gender have simple Yes/No or Male/Female answers that won't be confused
    # with health questions, so they can be interrupted for QnA
    profiling_list_steps = [
        "pregnancy_check", "health_safety_screening", "detox_experience", "detox_recent_reason",
    ]
    if is_health_question(state.get(KEY_USER_MSG, "")) and state.get(KEY_LAST_QUESTION) not in profiling_list_steps:
        # Check if meal plan is completed - if so, route to post_plan_qna
        # BUT NOT if we're in journey_restart_mode (recreating meal plan)
        plan_completed = bool(state.get("meal_plan_sent")) and not bool(state.get("journey_restart_mode"))

        if plan_completed:
            # Meal plan completed (not recreation) - route to post_plan_qna (unified Q&A handler)
            return NODE_POST_PLAN_QNA
        
        # IMPORTANT: Do NOT interrupt if user is in a review/choice state
        # These states need to handle user input themselves (including unclear responses)
        # This allows the else blocks in review/choice handlers to trigger
        review_choice_states = [
            "meal_day1_plan_review",         # Meal Day 1 initial review
            "meal_day1_revised_review",      # Meal Day 1 after revision
            "awaiting_meal_day1_changes",    # Waiting for meal Day 1 change request
        ]
        
        # Only interrupt if we're in the middle of collecting info (not at start/end or in review states)
        # Same as product_qna: set pending_node so we resume back to the same step after answering (first-time or Create New Plan flow)
        if state.get(KEY_LAST_QUESTION) not in [None, STATE_VERIFIED, NODE_POST_PLAN_QNA, "health_qna_answered", "product_qna_answered"] + review_choice_states:
            current_question = state.get(KEY_LAST_QUESTION)
            if current_question:
                state[KEY_PENDING_NODE] = QUESTION_TO_NODE.get(current_question, NODE_ASK_MEAL_PREFERENCE)
            return "health_qna"

    # Now handle validation for current pending input
    current_question = state.get(KEY_LAST_QUESTION)
    
    # Auto-recovery for corrupted state (bug where last_question was incorrectly reverted to detox_experience)
    if current_question == "detox_experience":
        user_msg = (state.get(KEY_USER_MSG) or "").lower()
        msg_id = state.get(KEY_USER_MSG, "")
        if any(kw in user_msg for kw in ["incomplete", "finish", "results", "symptoms", "back", "maintenance"]) or "detox_reason_" in msg_id:
            logger.info("Auto-recovering broken state: changing last_question from detox_experience to detox_recent_reason")
            state[KEY_LAST_QUESTION] = "detox_recent_reason"
            current_question = "detox_recent_reason"
            
    if current_question and state.get(KEY_USER_MSG):
        # Skip validation for review/choice nodes - they handle button responses internally
        review_choice_nodes = [
            "handle_meal_day1_review_choice",
            "handle_meal_day1_revised_review",
            "meal_day1_plan_review",
            "meal_day1_revised_review",
        ]

        # Map questions to expected field types for validation (gut_cleanse meal flow only)
        field_mapping = {
            "dietary_preference": "dietary_preference",
            "cuisine_preference": "cuisine_preference",
            # New Profiling Fields
            "health_safety_screening": "health_safety_screening",
            "detox_experience": "detox_experience",
            "detox_recent_reason": "detox_recent_reason",
            # End New Profiling Fields
            "food_allergies_intolerances": "food_allergies_intolerances",
            "daily_eating_pattern": "daily_eating_pattern",
            "foods_avoid": "foods_avoid",
            "supplements": "supplements",
            "digestive_issues": "digestive_issues",
            "hydration": "hydration",
            "other_beverages": "other_beverages",
            "gut_sensitivity": "gut_sensitivity",
        }

        expected_field = field_mapping.get(current_question)
        # Only validate if it's NOT a review/choice node AND has a field mapping
        if expected_field and current_question not in review_choice_nodes:
            # IMPORTANT: Always validate each message. Never skip validation due to prior state.
            # The validation_key_cached was causing validation to be skipped on subsequent messages.
            # We validate on EVERY message for the field, which allows proper retry logic.

            # Validate the input
            validation_result = handle_validated_input(state, expected_field)
            if validation_result == "retry":
                # Stay on the same question for retry
                # Map the current_question to the correct node name
                question_to_node_retry = {
                    "meal_day1_plan_review": "handle_meal_day1_review_choice",
                    "meal_day1_revised_review": "handle_meal_day1_revised_review",
                    "awaiting_meal_day1_changes": "collect_meal_day1_changes",
                }
                # Check if it's a special node, otherwise prepend "collect_"
                if current_question in question_to_node_retry:
                    return question_to_node_retry[current_question]
                else:
                    return f"collect_{current_question}" if current_question != "age_eligibility" else "collect_age_eligibility"
    
    # If returning from health Q&A, product Q&A, snap/image analysis, or other interruptions, resume where we left off
    # Same as bugzy_ams: answer the health/product question first, then route back to the same question (first-time or Create New Plan flow)
    if state.get(KEY_LAST_QUESTION) in ["health_qna_answered", "product_qna_answered", "resuming_from_health_qna", "resuming_from_product_qna", "image_analysis_complete", "resuming_from_snap"]:
        pending = state.get(KEY_PENDING_NODE)
        if pending:
            # Map last_question values to actual node names (QUESTION_TO_NODE covers all questionnaire steps; extra map for review nodes)
            question_to_node_map = {
                "meal_day1_plan_review": "handle_meal_day1_review_choice",
                "meal_day1_revised_review": "handle_meal_day1_revised_review",
                "generate_meal_day1_plan": "generate_meal_plan",
            }
            mapped_pending = question_to_node_map.get(pending, QUESTION_TO_NODE.get(pending, pending))
            logger.info("RESUMING to node: %s (original pending: %s)", mapped_pending, pending)
            return mapped_pending
    
    # SNAP IMAGE ANALYSIS FLOW - Check this EARLY to catch transitions
    # This must come before basic info collection to avoid falling through
    if state.get(KEY_LAST_QUESTION) == "transitioning_to_snap":
        # User is in SNAP transition, route to snap_image_analysis
        return NODE_SNAP_IMAGE_ANALYSIS
    elif state.get("snap_analysis_sent") and state.get(KEY_LAST_QUESTION) in ["snap_complete", "transitioning_to_gut_coach"]:
        return NODE_TRANSITION_TO_GUT_COACH
    
    # -----------------------------------------------------------
    # EXTENDED PROFILING ROUTING
    # -----------------------------------------------------------

    # Age Warning Confirmation (after age_eligibility for under-18 users)
    if state.get(KEY_LAST_QUESTION) == "age_warning_confirmation":
        msg = (state.get(KEY_USER_MSG) or "").lower()
        msg_id = state.get(KEY_USER_MSG, "")

        # User confirmed they want to proceed
        # Check for: button ID, "yes", "proceed", or "okay"
        if msg_id == "age_proceed_yes" or "yes" in msg or "proceed" in msg or "okay" in msg or "ok" in msg:
            state["age_warning_confirmed"] = True
            _update_last_answer_in_history(state, "Yes")
            return "collect_gender"

        # If user sends something else, re-ask the confirmation
        return "collect_age_warning_confirmation"

    # Pregnancy Warning Confirmation (after pregnancy_check for pregnant/breastfeeding users)
    if state.get(KEY_LAST_QUESTION) == "pregnancy_warning_confirmation":
        msg = (state.get(KEY_USER_MSG) or "").lower()
        msg_id = state.get(KEY_USER_MSG, "")

        # User confirmed they want to proceed
        if msg_id == "pregnancy_proceed_yes" or "yes" in msg:
            state["pregnancy_warning_confirmed"] = True
            _update_last_answer_in_history(state, "Yes")

            # Everyone (meal plan or not) goes to Health Safety Screening next
            # as part of the new 5-question required profiling flow
            if state.get("wants_meal_plan"):
                next_message = "Perfect! Let's move on to your meal plan 💚"
                send_whatsapp_message(state["user_id"], next_message)
                _store_system_message(state, next_message)
                if state.get("interaction_mode") != "voice":
                    import time
                    time.sleep(1.0)
            return "collect_health_safety_screening"

        # If user sends something else, re-ask the confirmation
        return "collect_pregnancy_warning_confirmation"

    # Health Safety Screening (after gender/pregnancy_check)
    if state.get(KEY_LAST_QUESTION) == "health_safety_screening":
        msg = (state.get(KEY_USER_MSG) or "").lower()
        msg_id = state.get(KEY_USER_MSG, "")

        # Resolve the specific condition from button ID first, then keyword fallback
        specific_status = resolve_health_safety_status(msg, msg_id)

        if specific_status:
            # Determine high-level group for backward-compat (used elsewhere to gate flow)
            block_conditions = {"under_18", "pregnant", "ulcers", "diarrhea", "ibs_ibd"}
            state["health_safety_status"] = specific_status
            state["health_safety_group"] = "gut_condition" if specific_status in block_conditions else "medical_condition"
            state["specific_health_condition"] = msg
            _update_last_answer_in_history(state, state["user_msg"])
            return "collect_detox_experience"

        # Healthy / None typed (or user says "No" to having conditions)
        if "healthy" in msg or "none" in msg or msg_id == "health_safe_healthy" or _is_negative_or_defer(msg):
            state["health_safety_status"] = "healthy"
            _update_last_answer_in_history(state, state["user_msg"])
            return "collect_detox_experience"

        # If user says "Yes" generically, ask them to specify
        if _is_affirmative(msg):
            send_whatsapp_message(state["user_id"], "Could you please tell me which specific condition you have?")
            return "collect_health_safety_screening"

        # Invalid input — re-ask
        send_whatsapp_message(
            state["user_id"],
            "I didn't quite catch that. Please select from the options above! 👆"
        )
        return "collect_health_safety_screening"

    # Q6: Detox Experience (Follow-up handling first)
    if state.get(KEY_LAST_QUESTION) == "detox_recent_reason":
        msg = (state.get(KEY_USER_MSG) or "").lower()
        msg_id = state.get(KEY_USER_MSG, "")
        
        response = "Got it 💚"
        if "incomplete" in msg or "finish" in msg or "detox_reason_incomplete" in msg_id:
            state["detox_recent_reason"] = "incomplete"
            response = "Got it 💚 Let's complete all 14 days this time!"
        elif "results" in msg or "detox_reason_no_results" in msg_id:
            state["detox_recent_reason"] = "no_results"
            response = "We'll make sure you follow the protocol closely this time 💚"
        elif "symptoms" in msg or "back" in msg or "detox_reason_symptoms_back" in msg_id:
            state["detox_recent_reason"] = "symptoms_back"
            response = "Perfect timing for a reset 💚"
        elif "maintenance" in msg or "detox_reason_maintenance" in msg_id:
            state["detox_recent_reason"] = "maintenance"
            response = "Great proactive approach! 💚\n\nNote: Gut cleanses work best every 2–3 months 🌟"
        else:
            send_whatsapp_message(
                state["user_id"],
                "I didn't quite catch that. Please select from the options above! 👆"
            )
            return "collect_detox_experience"
        
        send_whatsapp_message(state[KEY_USER_ID], response)
        _store_system_message(state, response)
        _update_last_answer_in_history(state, state[KEY_USER_MSG])
        if state.get("interaction_mode") != "voice":
            import time
            time.sleep(2)
        return route_after_profiling_complete(state)

    if state.get(KEY_LAST_QUESTION) == "detox_experience":
        msg = (state.get(KEY_USER_MSG) or "").lower()
        msg_id = state.get(KEY_USER_MSG, "")

        # Option 1: First time (No detox experience)
        if "no" in msg or "first" in msg or msg_id == "detox_exp_no" or _is_negative_or_defer(msg):
            state["detox_experience"] = "no"
            education = "Exciting! Your first gut reset 🎉\n\n*What to expect:*\n• Days 1–3: Mild bloating or more bathroom trips\n• Days 4–7: Symptoms settling, energy improving\n• Days 8–14: Feeling lighter and clearer\n\nI'll guide you through every step 💚"
            send_whatsapp_message(state["user_id"], education)
            _store_system_message(state, education)
            if state.get("interaction_mode") != "voice":
                import time
                time.sleep(2)
            _update_last_answer_in_history(state, state["user_msg"])
            state["profiling_collected"] = True
            logger.info("[PROFILING COMPLETE] Basic profiling marked as collected for user %s", state["user_id"])

            # Route based on meal plan preference
            return route_after_profiling_complete(state)

        # Option 2: Recent detox (within last 3 months) - ask follow-up (or generic yes)
        elif "recent" in msg or msg_id == "detox_exp_recent" or _is_affirmative(msg):
            state["detox_experience"] = "recent"
            followup = "Thanks for sharing 💚\n\nWhy are you doing another cleanse so soon?"
            _send_whatsapp_list(
                state["user_id"],
                followup,
                "Select Reason 👇",
                [
                    {
                        "title": "Reason",
                        "rows": [
                            {"id": "detox_reason_incomplete", "title": "Didn't finish", "description": "Stopped halfway"},
                            {"id": "detox_reason_no_results", "title": "No results", "description": "Didn't see changes"},
                            {"id": "detox_reason_symptoms_back", "title": "Symptoms back", "description": "Issues returned"},
                            {"id": "detox_reason_maintenance", "title": "Maintenance", "description": "Routine upkeep"}
                        ]
                    }
                ],
                header_text="Reason for Cleanse"
            )
            # We don't update last_answer here because we're asking a follow-up
            _store_question_in_history(state, followup, "detox_recent_reason")
            state["last_question"] = "detox_recent_reason"
            state["pending_node"] = "collect_detox_experience"
            _update_last_answer_in_history(state, state["user_msg"])
            return "collect_detox_experience"  # Route back to node to handle follow-up wait

        # Option 3: Long ago (more than 3 months)
        elif "long" in msg or "ago" in msg or msg_id == "detox_exp_long_ago":
            state["detox_experience"] = "long_ago"
            encouragement = "Perfect timing for another reset 💚\n\nYour gut will respond really well to this 🌿"
            send_whatsapp_message(state["user_id"], encouragement)
            _store_system_message(state, encouragement)
            if state.get("interaction_mode") != "voice":
                import time
                time.sleep(2)
            _update_last_answer_in_history(state, state["user_msg"])
            state["profiling_collected"] = True
            logger.info("[PROFILING COMPLETE] Basic profiling marked as collected for user %s", state["user_id"])

            # Route based on meal plan preference
            return route_after_profiling_complete(state)

        # Invalid input - send error and re-ask
        else:
            send_whatsapp_message(
                state["user_id"],
                "I didn't quite catch that. Please select from the options above! 👆"
            )
            return "collect_detox_experience"

    # Initial verification flow
    if state.get("last_question") is None:
        return "verify_user"
    elif state.get("last_question") == "verified":
        return "ask_meal_plan_preference"
    
    # Basic info collection (shared) - NEW PROFILING FLOW
    # Age eligibility → Gender → Pregnancy check (if female) → Route based on meal plan preference
    elif state.get("last_question") == "age_eligibility":
        msg = state.get("user_msg", "").lower()
        msg_id = state.get("user_msg", "")
        msg_raw = state.get("user_msg", "") or ""

        # Option 1: Yes (18+)
        if msg_id == "age_eligible_yes" or "✅" in msg_raw or _is_affirmative(msg_raw) or "18" in msg:
            state["age_eligible"] = True
            _update_last_answer_in_history(state, "Yes, I'm 18+")
            return "collect_gender"

        # Option 2: No (under 18)
        elif msg_id == "age_eligible_no" or "❌" in msg_raw or (_is_negative_or_defer(msg_raw) and "18" in msg):
            state["age_eligible"] = False
            _update_last_answer_in_history(state, "No, I'm under 18")
            # Send warning message (only if not already sent)
            if not state.get("age_eligibility_warning_sent"):
                warning_msg = (
                    "⚠️ Important\n\n"
                    "Appreciate you sharing that 💚\n\n"
                    "The Gut Cleanse isn't recommended for anyone under 18 years of age, "
                    "as your gut is still developing.\n\n"
                    "It may be too strong for you right now."
                )
                send_whatsapp_message(state["user_id"], warning_msg)
                _store_system_message(state, warning_msg)
                state["age_eligibility_warning_sent"] = True
                if state.get("interaction_mode") != "voice":
                    import time
                    time.sleep(1.5)
            # Route to confirmation node instead of directly to gender
            return "collect_age_warning_confirmation"

        # Option 3: Invalid input - send error and re-ask
        else:
            send_whatsapp_message(
                state["user_id"],
                "I didn't quite catch that. Please let me know using the buttons below! 👇"
            )
            return "collect_age_eligibility"
    elif state.get("last_question") == "gender":
        msg = (state.get("user_msg") or "").lower()
        msg_id = state.get("user_msg", "")
        
        import re
        is_male = msg_id == "gender_male" or msg == "male" or bool(re.search(r'\b(male|mail|man|boy|guy)\b', msg))
        is_female = msg_id == "gender_female" or msg == "female" or bool(re.search(r'\b(female|woman|girl|lady)\b', msg))
        is_prefer_not = msg_id == "gender_prefer_not_to_say" or any(w in msg for w in ["prefer not", "skip", "rather not", "don't"])
        
        # Resolve conflicts (e.g. "not a female")
        if is_male and is_female:
            if "female" in msg: is_male = False
            else: is_female = False

        # Store gender in state
        if is_male:
            state["gender"] = "male"
            _update_last_answer_in_history(state, "Male")
            # Confirmation handled in node
            
            # Male / Prefer not to say -> Go to Health Safety Screening
            return "collect_health_safety_screening"
            
        elif is_female:
            state["gender"] = "female"
            _update_last_answer_in_history(state, "Female")
            # Continue to pregnancy check
            return "collect_pregnancy_check"
            
        elif is_prefer_not:
            state["gender"] = "prefer_not_to_say"
            _update_last_answer_in_history(state, "Prefer not to say")
            # Confirmation handled in node

            # Male / Prefer not to say -> Go to Health Safety Screening
            return "collect_health_safety_screening"

        # Invalid input - send error and re-ask
        else:
            if state.get("interaction_mode") != "voice":
                send_whatsapp_message(
                    state["user_id"],
                    "I didn't quite catch that. Please let me know using the buttons below! 👇"
                )
            return "collect_gender"

    elif state.get("last_question") == "pregnancy_check":
        # Handle pregnancy/breastfeeding response
        # Similar to how medications response is handled - store the answer and route to next step
        msg = (state.get("user_msg") or "").lower()
        msg_id = state.get("user_msg", "")
        msg_raw = state.get("user_msg", "") or ""

        # Option 1: Not pregnant/breastfeeding
        if msg_id == "pregnancy_no" or (msg == "no" and "✅" in msg_raw) or _is_negative_or_defer(msg):
            state["is_pregnant"] = False
            state["is_breastfeeding"] = False
            _update_last_answer_in_history(state, "No")
            return "collect_health_safety_screening"

        # Option 2: Pregnant
        elif msg_id == "pregnancy_yes_pregnant" or "pregnant" in msg or "🤰" in msg_raw or _is_affirmative(msg):
            state["is_pregnant"] = True
            state["is_breastfeeding"] = False
            _update_last_answer_in_history(state, "Yes, pregnant")
            # Send warning message with hazardous/critical signs
            warning_msg = (
                "⚠️ Important\n\n"
                "Appreciate you sharing that 💚\n\n"
                "The Gut Cleanse isn't recommended during pregnancy or breastfeeding, "
                "as it may affect:\n"
                "•  Nutrient absorption for you and your baby\n"
                "•  Hormonal balance\n"
                "•  Milk production\n\n"
                "It may be too strong for your body during this phase."
            )
            send_whatsapp_message(state["user_id"], warning_msg)
            _store_system_message(state, warning_msg)
            if state.get("interaction_mode") != "voice":
                import time
                time.sleep(1.5)
            return "collect_pregnancy_warning_confirmation"

        # Option 3: Breastfeeding
        elif msg_id == "pregnancy_yes_breastfeeding" or "breastfeeding" in msg or "🤱" in msg_raw:
            state["is_pregnant"] = False
            state["is_breastfeeding"] = True
            _update_last_answer_in_history(state, "Yes, breastfeeding")
            # Send warning message with hazardous/critical signs
            warning_msg = (
                "⚠️ Important\n\n"
                "Appreciate you sharing that 💚\n\n"
                "The Gut Cleanse isn't recommended during pregnancy or breastfeeding, "
                "as it may affect:\n"
                "•  Nutrient absorption for you and your baby\n"
                "•  Hormonal balance\n"
                "•  Milk production\n\n"
                "It may be too strong for your body during this phase."
            )
            send_whatsapp_message(state["user_id"], warning_msg)
            _store_system_message(state, warning_msg)
            if state.get("interaction_mode") != "voice":
                import time
                time.sleep(1.5)
            return "collect_pregnancy_warning_confirmation"

        # Invalid input - send error and re-ask
        else:
            send_whatsapp_message(
                state["user_id"],
                "I didn't quite catch that. Please let me know using the buttons below! 👇"
            )
            return "collect_pregnancy_check"

    
    
    # MEAL PLAN PREFERENCE ROUTING (before agent-specific routing)
    # This needs to be checked early because current_agent might not be set yet
    elif state.get("last_question") == "ask_meal_plan_preference":
        # VOICE CALL: User called while at meal preference — assume they want meal plan, start journey
        if state.get("interaction_mode") == "voice":
            state["wants_meal_plan"] = True
            state["current_agent"] = "meal"
            state["voice_agent_accepted"] = True
            # Route to the first question that is still missing — never go backwards
            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return "collect_dietary_preference"
            has_full_profiling = (
                state.get("age_eligible") is not None
                and state.get("gender") is not None
                and state.get("health_safety_status") is not None
            )
            if has_full_profiling:
                return "collect_detox_experience"
            if state.get("age_eligible") is not None and state.get("gender") is None:
                return "collect_gender"
            if state.get("gender") is not None and state.get("health_safety_status") is None:
                if state.get("gender") == "female" and state.get("is_pregnant") is None and state.get("is_breastfeeding") is None:
                    return "collect_pregnancy_check"
                return "collect_health_safety_screening"
            return "collect_age_eligibility"

        # Check user choice
        msg = state.get("user_msg", "").lower()
        msg_id = state.get("user_msg", "")  # Get button ID if it's a button click
        
        msg_raw = state.get("user_msg", "") or ""

        # Option 1: User wants to create meal plan (button click or affirmative text)
        # Treat short greetings (hey, hi) as affirmative — user is engaging, assume yes
        if msg_id == "create_meal_plan" or "create" in msg_raw or "🔥" in msg_raw or _is_affirmative(msg_raw) or _is_greeting_message(msg_raw):
            state["wants_meal_plan"] = True
            state["current_agent"] = "meal"

            send_whatsapp_message(state["user_id"], "Awesome! Let's make this perfect for you 💚")
            _store_system_message(state, "Awesome! Let's make this perfect for you 💚")

            existing_meal_plan = load_meal_plan(state.get("user_id", "")) or {}
            if existing_meal_plan and existing_meal_plan.get("meal_day1_plan"):
                state["existing_meal_plan_data"] = existing_meal_plan
                logger.info("✅ ROUTER: Existing meal plan found - asking edit vs new choice")
                return "ask_existing_meal_plan_choice"

            return "voice_agent_promotion_meal"



        # Option 2: User already has a meal plan
        elif (msg_id == "has_meal_plan" or "📋" in msg_raw or
              "already have" in msg or "already sorted" in msg or "already got" in msg or
              "i've got one" in msg or "got one already" in msg):
            state["wants_meal_plan"] = False
            send_whatsapp_message(state["user_id"], "Perfect! You're already ahead of the game 💚 Let me ask a few quick questions so I can help you better!\n\nAnd anytime after your journey completes, simply type *\"create a meal plan\"* and I'll build one for you instantly 📋✨")
            _store_system_message(state, "Perfect! You're already ahead of the game 💚 Let me ask a few quick questions so I can help you better!\n\nAnd anytime after your journey completes, simply type *\"create a meal plan\"* and I'll build one for you instantly 📋✨")
            logger.info("➡️  ROUTER: User already has meal plan - routing to required profiling")

            if state.get("profiling_collected") or _has_completed_weight(state) or _has_any_profiling_data(state):
                logger.info("[EARLY PROFILING] Already has plan - profiling exists → transition_to_snap")
                return "transition_to_snap"
            else:
                logger.info("[EARLY PROFILING] Already has plan - no profiling data → collect_age_eligibility")
                return "collect_age_eligibility"

        # Option 3: User doesn't want meal plan now (explicit no/defer)
        elif msg_id == "no_meal_plan" or _is_negative_or_defer(msg_raw):
            state["wants_meal_plan"] = False
            send_whatsapp_message(state["user_id"], "No problem! 💚\n\nAnd whenever you're ready later, just say *\"create a meal plan\"* and I'll prepare one for you 📋✨")
            _store_system_message(state, "No problem! 💚\n\nAnd whenever you're ready later, just say *\"create a meal plan\"* and I'll prepare one for you 📋✨")
            logger.info("➡️  ROUTER: Meal plan declined - routing to required profiling")

            if state.get("profiling_collected") or _has_completed_weight(state) or _has_any_profiling_data(state):
                logger.info("[EARLY PROFILING] Meal plan NO - profiling exists → transition_to_snap")
                return "transition_to_snap"
            else:
                logger.info("[EARLY PROFILING] Meal plan NO - no profiling data → collect_age_eligibility")
                return "collect_age_eligibility"

        # Option 4: Invalid input - send error and re-ask
        else:
            send_whatsapp_message(
                state["user_id"],
                "I didn't quite catch that. Please let me know using the buttons below! 👇"
            )
            return "ask_meal_plan_preference"
            
    elif state.get("last_question") == "voice_agent_promotion_meal":
        # VOICE CALL: User is already on the call — start the meal journey
        if state.get("interaction_mode") == "voice":
            state["voice_agent_accepted"] = True
            state["wants_meal_plan"] = True
            state["current_agent"] = "meal"
            # Route to the first question that is still missing — never go backwards
            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return "collect_dietary_preference"
            # All basic profiling done → meal plan questions
            has_full_profiling = (
                state.get("age_eligible") is not None
                and state.get("gender") is not None
                and state.get("health_safety_status") is not None
            )
            if has_full_profiling:
                return "collect_detox_experience"
            # Partial profiling — route to next unanswered step
            if state.get("age_eligible") is not None and state.get("gender") is None:
                return "collect_gender"
            if state.get("gender") is not None and state.get("health_safety_status") is None:
                # Female path needs pregnancy check
                if state.get("gender") == "female" and state.get("is_pregnant") is None and state.get("is_breastfeeding") is None:
                    return "collect_pregnancy_check"
                return "collect_health_safety_screening"
            # Nothing answered yet — start from age
            return "collect_age_eligibility"

        msg_raw = state.get("user_msg", "") or ""
        msg = msg_raw.lower()
        msg_id = msg_raw

        # User chose chat
        if msg_id == "create_here_chat" or "chat" in msg:
            state["voice_agent_choice"] = "chat"
            state["voice_agent_declined"] = True
            
            # Check if profiling already collected
            has_new_profiling = (
                state.get("age_eligible") is not None and
                state.get("gender") is not None
            )

            if state.get("profiling_collected") or state.get("journey_restart_mode") or has_new_profiling:
                logger.info("✅ ROUTER: Profiling already collected - SKIPPING profiling questions")
                return "collect_health_safety_screening"
            else:
                return "collect_age_eligibility"
                
        # User chose voice agent
        elif msg_id == "try_voice_agent" or "voice" in msg:
            # The button directly links to the wa.me Call URL now. We just end the graph here.
            return "__end__"
        
        # Unclear response -> Clarify
        else:
            return "voice_agent_promotion_meal"  # Re-ask
    
    # MEAL PLANNER AGENT FLOW - Route based on last_question (gut_cleanse 11-Question Meal Flow only)
    elif state.get("current_agent") == "meal":
        last_q = state.get("last_question")
        
        # 1. Complex Conditionals
        if last_q == "meal_day1_complete":
            # Check if pending_node is set (for single-call generation)
            pending = state.get("pending_node")
            if pending == "generate_all_remaining_meal_days":
                return "generate_all_remaining_meal_days"
            # Fallback to old day-by-day approach
            return "generate_meal_day2_plan"
            
        elif state.get("meal_plan_sent") and last_q == "meal_plan_complete":
            # If recreation (Create New Plan from post_plan_qna), stay in post_plan_qna — do NOT go to SNAP
            if state.get("journey_restart_mode") or state.get("existing_meal_plan_choice_origin") == "post_plan_qna":
                return "post_plan_qna"
            logger.info("➡️  ROUTER: Meal plan complete - routing directly to transition_to_snap")
            return "transition_to_snap"
            
        # 2. Linear Map Lookup
        elif last_q in GUT_MEAL_FLOW_MAP:
            return GUT_MEAL_FLOW_MAP[last_q]
            
    # Post-plan handling - only if meal plan is sent or we're in post-plan state
    elif state.get("meal_plan_sent") or state.get("last_question") == "post_plan":
        return "post_plan_qna"
    
    # Resumption handler for voice agent instructions
    elif state.get("last_question") == "voice_agent_instructions_provided":
        logger.info("📦 ROUTER: Resuming from voice agent instructions - finding next node")
        return _get_resume_node_gut_cleanse(state)

    # Fallback
    return "verify_user"


def route_after_profiling_complete(state: State) -> str:
    """
    Route after profiling is complete (new flow: age eligibility, gender, pregnancy check,
    health safety screening, detox experience (+ detox_recent_reason follow-up)).
    Routes based on meal plan preference.
    """
    if state.get("interaction_mode") == "voice":
        state["wants_meal_plan"] = True
        
    wants_meal = state.get("wants_meal_plan", False)
    
    if wants_meal:
        # User wants meal plan - send success message before routing to meal questions
        # Only send if not already sent (to avoid duplicates)
        if not state.get("profiling_to_meal_success_sent"):
            success_msg = "Perfect! Let's move on to your meal plan 💚"
            send_whatsapp_message(state[KEY_USER_ID], success_msg)
            _store_system_message(state, success_msg)
            state["profiling_to_meal_success_sent"] = True
            if state.get("interaction_mode") != "voice":
                import time
                time.sleep(1.0)
        state["profiling_collected"] = True
        logger.info("[PROFILING COMPLETE] User wants meal plan → collect_dietary_preference")
        return "collect_dietary_preference"
    else:
        # User doesn't want meal plan - route to transition_to_snap
        logger.info("[PROFILING COMPLETE] User doesn't want meal plan → transition_to_snap")
        state["profiling_collected"] = True
        state["profiling_collected_in_meal"] = False
        return NODE_TRANSITION_TO_SNAP


def resume_router(state: State) -> str:
    """Route back to the interrupted node after health Q&A or product Q&A."""
    pending = state.get(KEY_PENDING_NODE)
    logger.info("RESUME ROUTER - Pending node: %s", pending)
    
    # If meal plan is completed, clear pending_node and go to post-plan Q&A
    if state.get("meal_plan_sent"):
        logger.info("RESUME ROUTER - Meal plan completed, routing to post_plan_qna")
        return NODE_POST_PLAN_QNA
    
    # If we have a pending node and we're still in plan generation, resume from there
    if pending:
        # Map last_question values to actual node names if needed
        question_to_node_map = {
            "meal_day1_plan_review": "handle_meal_day1_review_choice",
            "meal_day1_revised_review": "handle_meal_day1_revised_review",
            "generate_meal_day1_plan": "generate_meal_plan",
        }
        # If pending is a last_question value, map it to the actual node
        mapped_pending = question_to_node_map.get(pending, pending)
        # Return to the SAME node that was interrupted, not the next one
        # This ensures the user gets asked the question they didn't answer yet
        logger.info("RESUME ROUTER - Returning to: %s (original pending: %s)", mapped_pending, pending)
        return mapped_pending
    
    # If we don't have a pending node, go to ask_meal_plan_preference as a fallback
    if not pending:
        logger.info("RESUME ROUTER - No pending node, defaulting to ask_meal_plan_preference")
        return NODE_ASK_MEAL_PREFERENCE
        
    return NODE_POST_PLAN_QNA
