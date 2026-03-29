"""
Router functions for the chatbot agent.

This module contains the main routing logic that determines which node
to execute next based on the current state of the conversation.
"""

import random
import logging
from typing import Optional
from app.services.chatbot.bugzy_general.state import State
from app.services.chatbot.bugzy_general.constants import QUESTION_TO_NODE
from app.services.whatsapp.client import send_whatsapp_message
from app.services.prompts.general.health_product_detection import is_health_question, is_product_question
logger = logging.getLogger(__name__)


# --- Helper Functions for Router ---

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
    """User has provided age, height, and weight (non-empty strings)."""
    return (
        bool((state.get("age") or "").strip()) and
        bool((state.get("height") or "").strip()) and
        bool((state.get("weight") or "").strip())
    )

def _is_at_or_after_health_conditions(state: dict) -> bool:
    """Check if last_question is health_conditions or any subsequent step in the flow."""
    order = [
        "verified", "age", "height", "weight", "bmi_calculated",
        "health_conditions", "collect_health_conditions", "medications",
        "meal_timing_breakfast", "meal_timing_lunch", "meal_timing_dinner",
        "current_breakfast", "current_lunch", "current_dinner",
        "diet_preference", "cuisine_preference", "allergies",
        "water_intake", "beverages", "lifestyle", "activity_level",
        "sleep_stress", "meal_goals", "meal_day1_plan_review", "awaiting_meal_day1_changes",
        "regenerating_meal_day1", "meal_day1_revised_review",
        "meal_day1_complete", "meal_day2_complete", "meal_day3_complete",
        "meal_day4_complete", "meal_day5_complete", "meal_day6_complete",
        "generate_meal_plan", "meal_plan_complete", "transition_to_exercise",
        "fitness_level", "activity_types", "exercise_frequency",
        "exercise_intensity", "session_duration", "sedentary_time",
        "exercise_goals", "day1_plan_review", "awaiting_day1_changes", 
        "regenerating_day1", "day1_revised_review",
        "day1_complete", "day2_complete", "day3_complete",
        "day4_complete", "day5_complete", "day6_complete",
        "exercise_plan_complete", "transition_to_snap", "snap_complete",
        "transitioning_to_gut_coach", "post_plan_qna"
    ]
    lq = (state.get("last_question") or "").strip()
    if lq not in order:
        return False
    return order.index(lq) >= order.index("health_conditions")

def _should_apply_greeting_resume(state: dict) -> bool:
    """Apply greeting-resume only if not in post_plan_qna, weight done, and at/after health_conditions."""
    if state.get("current_agent") == "post_plan_qna" or state.get("last_question") == "post_plan_qna":
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
    if state.get("current_agent") == "post_plan_qna" or state.get("last_question") == "post_plan_qna":
        return False
    if not _has_completed_weight(state):
        return False
    return _is_at_or_after_health_conditions(state)

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
    from app.services.chatbot.bugzy_general.nodes.user_verification_nodes import handle_validated_input
    from app.services.chatbot.bugzy_general.nodes.qna_nodes import is_contextual_product_question
    
    logger.info("ROUTING with state keys: %s", state.keys())
    
    user_msg = state.get("user_msg", "").lower().strip()
    
    # Check for restart command
    if user_msg == "restart":
        return "verify_user"
    
    # Greeting-only messages: only resume if not in post_plan_qna,
    # weight completed, and at/after health_conditions
    if _is_greeting_message(state.get("user_msg", "")) and _should_apply_greeting_resume(state):
        pending = state.get("pending_node")

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
                "day1_plan_review": "handle_day1_review_choice",
                "day1_revised_review": "handle_day1_revised_review",
                "generate_meal_day1_plan": "generate_meal_plan",
                "generate_day1_plan": "generate_day1_plan",
            }
            # If pending is a last_question value, map it to the actual node
            mapped_pending = question_to_node_map.get(pending, pending)
            logger.info("GREET ROUTE - Greeting detected, resuming pending node: %s (original pending: %s)", mapped_pending, pending)
            return mapped_pending
            current_question = state.get("last_question")
            question_to_node = QUESTION_TO_NODE
        if current_question in question_to_node:
            node = question_to_node[current_question]
            logger.info("GREET ROUTE - Greeting detected, resuming current step: %s", node)
            return node
        logger.info("GREET ROUTE - Greeting detected but insufficient context; verifying user")
        return "verify_user"
    
    # Resume journey button clicks: resume as long as not in post_plan_qna
    # Removed restrictive checks for weight/health_conditions to allow resume at any point
    if _is_resume_journey_button(state.get("user_msg", "")) and not (state.get("current_agent") == "post_plan_qna" or state.get("last_question") == "post_plan_qna"):
        pending = state.get("pending_node")

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
                "day1_plan_review": "handle_day1_review_choice",
                "day1_revised_review": "handle_day1_revised_review",
                "generate_meal_day1_plan": "generate_meal_plan",
                "generate_day1_plan": "generate_day1_plan",
            }
            # If pending is a last_question value, map it to the actual node
            mapped_pending = question_to_node_map.get(pending, pending)
            logger.info("RESUME BUTTON ROUTE - Resume button detected, resuming pending node: %s (original pending: %s)", mapped_pending, pending)
            return mapped_pending
        current_question = state.get("last_question")
        question_to_node = QUESTION_TO_NODE
        if current_question in question_to_node:
            node = question_to_node[current_question]
            logger.info("RESUME BUTTON ROUTE - Resume button detected, resuming current step: %s", node)
            return node
        logger.info("RESUME BUTTON ROUTE - Resume button detected but insufficient context; verifying user")
        return "verify_user"
    
    # PRIORITY: Check for PLAN EDIT FLOW states FIRST (before post-plan routing)
    # This ensures edit requests are handled even when both plans are completed
    if state.get("last_question") == "select_meal_day_to_edit":
        return "handle_meal_day_selection_for_edit"
    elif state.get("last_question") and str(state.get("last_question")).startswith("awaiting_meal_day") and str(state.get("last_question")).endswith("_edit_changes"):
        return "collect_meal_day_edit_changes"
    elif state.get("last_question") == "select_exercise_day_to_edit":
        return "handle_exercise_day_selection_for_edit"
    elif state.get("last_question") and str(state.get("last_question")).startswith("awaiting_exercise_day") and str(state.get("last_question")).endswith("_edit_changes"):
        return "collect_exercise_day_edit_changes"
    
    # PRIORITY: Check if we're in post-plan state (both plans completed)
    # BUT NOT if we're still in the SNAP image analysis flow
    if (state.get("meal_plan_sent") and state.get("exercise_plan_sent")) or state.get("last_question") == "post_plan_qna":
        # Exception: If we're waiting for image analysis or transitioning from it, don't skip to post_plan_qna yet
        if state.get("last_question") in ["exercise_plan_complete", "snap_complete", "transitioning_to_snap", "transitioning_to_gut_coach"]:
            # Continue with normal flow to handle SNAP
            pass
        else:
            # Route all questions to post-plan Q&A handler
            return "post_plan_qna"
    
    # PRIORITY: Check for health and product questions BEFORE validation
    # This ensures these questions are handled properly even during data collection


    # Check if user is asking a product/company question
    # IMPORTANT: Check BOTH direct product questions AND contextual follow-ups
    # (e.g., "can i take it" after asking about a product)
    user_msg = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])
    is_product = is_product_question(user_msg)
    is_contextual_product = is_contextual_product_question(user_msg, conversation_history) if conversation_history else False
    
    # Debug to trace routing decisions
    if is_product or is_contextual_product:
        logger.info("ROUTER PRODUCT DETECTION | is_product=%s | is_contextual_product=%s | msg='%s'", is_product, is_contextual_product, user_msg)
    
    if is_product or is_contextual_product:
        # Check if both plans are completed - if so, route to post_plan_qna
        plans_completed = bool(state.get("meal_plan_sent")) and bool(state.get("exercise_plan_sent"))
        
        if plans_completed:
            # Both plans completed - route to post_plan_qna (unified Q&A handler)
            return "post_plan_qna"
        
        # Handle product questions during data collection
        current_question = state.get("last_question")
        if current_question and current_question not in [None, "verified", "post_plan_qna", "health_qna_answered", "product_qna_answered"]:
            # Set the pending node to the current question so we can resume later
            state["pending_node"] = QUESTION_TO_NODE.get(current_question, "collect_age")
        return "product_qna"

    
    # Check if user is asking a health question
    if is_health_question(state.get("user_msg", "")):
        # Check if both plans are completed - if so, route to post_plan_qna
        plans_completed = bool(state.get("meal_plan_sent")) and bool(state.get("exercise_plan_sent"))
        
        if plans_completed:
            # Both plans completed - route to post_plan_qna (unified Q&A handler)
            return "post_plan_qna"
        
        # IMPORTANT: Do NOT interrupt if user is in a review/choice state
        # These states need to handle user input themselves (including unclear responses)
        # This allows the else blocks in review/choice handlers to trigger
        review_choice_states = [
            "day1_plan_review",              # Exercise Day 1 initial review
            "day1_revised_review",           # Exercise Day 1 after revision
            "awaiting_day1_changes",         # Waiting for exercise Day 1 change request
            "meal_day1_plan_review",         # Meal Day 1 initial review
            "meal_day1_revised_review",      # Meal Day 1 after revision
            "awaiting_meal_day1_changes",    # Waiting for meal Day 1 change request
        ]
        
        # Only interrupt if we're in the middle of collecting info (not at start/end or in review states)
        if state.get("last_question") not in [None, "verified", "post_plan_qna", "health_qna_answered", "product_qna_answered"] + review_choice_states:
            # Set the pending node to the current question so we can resume later
            current_question = state.get("last_question")
            if current_question:
                # Map the current question to the corresponding node
                state["pending_node"] = QUESTION_TO_NODE.get(current_question, "collect_age")
            return "health_qna"

    # Now handle validation for current pending input
    current_question = state.get("last_question")
    if current_question and state.get("user_msg"):
        # Skip validation for review/choice nodes - they handle button responses internally
        review_choice_nodes = [
            "handle_meal_day1_review_choice",
            "handle_meal_day1_revised_review",
            "handle_day1_review_choice",
            "handle_day1_revised_review",
            "meal_day1_plan_review",
            "meal_day1_revised_review",
            "day1_plan_review",
            "day1_revised_review",
        ]
        
        # Map questions to expected field types for validation
        field_mapping = {
            "age": "age",
            "height": "height", 
            "weight": "weight",
            "health_conditions": "health conditions",
            "medications": "medications",
            "meal_timing_breakfast": "breakfast time",
            "meal_timing_lunch": "lunch time",  
            "meal_timing_dinner": "dinner time",
            "current_breakfast": "breakfast meal details",
            "current_lunch": "lunch meal details",
            "current_dinner": "dinner meal details",
            "diet_preference": "diet preference",
            "cuisine_preference": "cuisine preference",
            "allergies": "allergies",
            "water_intake": "water intake",
            "beverages": "beverages",
            "lifestyle": "lifestyle",
            "activity_level": "activity level",
            "sleep_stress": "sleep and stress",
            "supplements": "supplements",
            "gut_health": "gut health",
            "meal_goals": "goals",
            "fitness_level": "fitness level",
            "activity_types": "activity types",
            "exercise_frequency": "exercise frequency",
            "exercise_intensity": "exercise intensity",
            "session_duration": "session duration",
            "sedentary_time": "sedentary time",
            "exercise_goals": "exercise goals",
        }
        
        expected_field = field_mapping.get(current_question)
        # Only validate if it's NOT a review/choice node AND has a field mapping
        if expected_field and current_question not in review_choice_nodes:
            # Check if this is the first validation attempt for this message
            validation_key = f"{expected_field}_validated_in_router"
            if validation_key not in state:
                # Mark that we've validated this message in the router
                state[validation_key] = True
                
                # Validate the input
                validation_result = handle_validated_input(state, expected_field)
                if validation_result == "retry":
                    # Stay on the same question for retry
                    # Map the current_question to the correct node name
                    question_to_node_retry = {
                        "meal_day1_plan_review": "handle_meal_day1_review_choice",
                        "meal_day1_revised_review": "handle_meal_day1_revised_review",
                        "day1_plan_review": "handle_day1_review_choice",
                        "day1_revised_review": "handle_day1_revised_review",
                        "awaiting_meal_day1_changes": "collect_meal_day1_changes",
                        "awaiting_day1_changes": "collect_day1_changes",
                    }
                    # Check if it's a special node, otherwise prepend "collect_"
                    if current_question in question_to_node_retry:
                        return question_to_node_retry[current_question]
                    else:
                        return f"collect_{current_question}" if current_question != "age" else "collect_age"
    
    # If returning from health Q&A, product Q&A, snap/image analysis, or other interruptions, resume where we left off
    if state.get("last_question") in ["health_qna_answered", "product_qna_answered", "resuming_from_health_qna", "resuming_from_product_qna", "image_analysis_complete", "resuming_from_snap"]:
        pending = state.get("pending_node")
        if pending:
            # Map last_question values to actual node names if needed
            question_to_node_map = {
                "meal_day1_plan_review": "handle_meal_day1_review_choice",
                "meal_day1_revised_review": "handle_meal_day1_revised_review",
                "day1_plan_review": "handle_day1_review_choice",
                "day1_revised_review": "handle_day1_revised_review",
                "generate_meal_day1_plan": "generate_meal_plan",
                "generate_day1_plan": "generate_day1_plan",
            }
            # If pending is a last_question value, map it to the actual node
            mapped_pending = question_to_node_map.get(pending, pending)
            logger.info("RESUMING to node: %s (original pending: %s)", mapped_pending, pending)
            # Just return to the same node where we left off
            return mapped_pending
    
    # SNAP IMAGE ANALYSIS FLOW - Check this EARLY to catch transitions
    # This must come before basic info collection to avoid falling through
    if state.get("exercise_plan_sent") and state.get("last_question") == "exercise_plan_complete" and not state.get("snap_analysis_sent"):
        return "snap_image_analysis"
    elif state.get("last_question") == "transitioning_to_snap":
        # User is in SNAP transition, route to snap_image_analysis
        return "snap_image_analysis"
    elif state.get("snap_analysis_sent") and state.get("last_question") in ["snap_complete", "transitioning_to_gut_coach"]:
        return "transition_to_gut_coach"
    
    # Initial verification flow
    if state.get("last_question") is None:
        return "verify_user"
    elif state.get("last_question") == "verified":
        return "collect_age"
    
    # Basic info collection (shared) - Route based on last_question
    elif state.get("last_question") == "age":
        return "collect_height"
    elif state.get("last_question") == "height":
        return "collect_weight"
    elif state.get("last_question") == "weight":
        return "calculate_bmi"
    
    # MEAL PLANNER AGENT FLOW - Route based on last_question
    elif state.get("current_agent") == "meal":
        if state.get("last_question") == "bmi_calculated":
            return "collect_health_conditions"
        elif state.get("last_question") == "health_conditions":
            # Conditional routing: check if health condition exists
            health_conditions = state.get("health_conditions", "").strip().lower()
            # Skip medications if no health condition or if health condition is "none"
            if not health_conditions or health_conditions in ["none", "no", "nil", "nothing", "health_none"]:
                return "collect_meal_timing_breakfast"
            else:
                return "collect_medications"
        elif state.get("last_question") == "medications":
            return "collect_meal_timing_breakfast"
        elif state.get("last_question") == "meal_timing_breakfast":
            return "collect_meal_timing_lunch"
        elif state.get("last_question") == "meal_timing_lunch":
            return "collect_meal_timing_dinner"
        elif state.get("last_question") == "meal_timing_dinner":
            return "collect_current_breakfast"
        elif state.get("last_question") == "current_breakfast":
            return "collect_current_lunch"
        elif state.get("last_question") == "current_lunch":
            return "collect_current_dinner"
        elif state.get("last_question") == "current_dinner":
            return "collect_diet_preference"
        elif state.get("last_question") == "diet_preference":
            return "collect_cuisine_preference"
        elif state.get("last_question") == "cuisine_preference":
            return "collect_allergies"
        elif state.get("last_question") == "allergies":
            return "collect_water_intake"
        elif state.get("last_question") == "water_intake":
            return "collect_beverages"
        elif state.get("last_question") == "beverages":
            return "collect_lifestyle"
        elif state.get("last_question") == "lifestyle":
            return "collect_activity_level"
        elif state.get("last_question") == "activity_level":
            return "collect_sleep_stress"
        elif state.get("last_question") == "sleep_stress":
            return "collect_supplements"
        elif state.get("last_question") == "supplements":
            return "collect_gut_health"
        elif state.get("last_question") == "gut_health":
            return "collect_meal_goals"
        elif state.get("last_question") == "meal_goals":
            return "generate_meal_plan"
        elif state.get("last_question") == "meal_day1_plan_review":
            return "handle_meal_day1_review_choice"
        elif state.get("last_question") == "awaiting_meal_day1_changes":
            return "collect_meal_day1_changes"
        elif state.get("last_question") == "regenerating_meal_day1":
            return "regenerate_meal_day1_plan"
        elif state.get("last_question") == "meal_day1_revised_review":
            return "handle_meal_day1_revised_review"
        elif state.get("last_question") == "meal_day1_complete":
            # Check if pending_node is set (for single-call generation)
            pending = state.get("pending_node")
            if pending == "generate_all_remaining_meal_days":
                return "generate_all_remaining_meal_days"
            # Fallback to old day-by-day approach
            return "generate_meal_day2_plan"
        elif state.get("last_question") == "meal_day2_complete":
            return "generate_meal_day3_plan"
        elif state.get("last_question") == "meal_day3_complete":
            return "generate_meal_day4_plan"
        elif state.get("last_question") == "meal_day4_complete":
            return "generate_meal_day5_plan"
        elif state.get("last_question") == "meal_day5_complete":
            return "generate_meal_day6_plan"
        elif state.get("last_question") == "meal_day6_complete":
            return "generate_meal_day7_plan"
        elif state.get("meal_plan_sent") and state.get("last_question") == "meal_plan_complete":
            # Automatically transition to exercise planner
            return "transition_to_exercise"
    
    # EXERCISE PLANNER AGENT FLOW - Route based on last_question
    elif state.get("current_agent") == "exercise":
        if state.get("last_question") == "transitioning_to_exercise":
            return "collect_fitness_level"
        elif state.get("last_question") == "fitness_level":
            return "collect_activity_types"
        elif state.get("last_question") == "activity_types":
            return "collect_exercise_frequency"
        elif state.get("last_question") == "exercise_frequency":
            return "collect_exercise_intensity"
        elif state.get("last_question") == "exercise_intensity":
            return "collect_session_duration"
        elif state.get("last_question") == "session_duration":
            return "collect_sedentary_time"
        elif state.get("last_question") == "sedentary_time":
            return "collect_exercise_goals"
        elif state.get("last_question") == "exercise_goals":
            return "generate_day1_plan"
        elif state.get("last_question") == "day1_plan_review":
            return "handle_day1_review_choice"
        elif state.get("last_question") == "awaiting_day1_changes":
            return "collect_day1_changes"
        elif state.get("last_question") == "regenerating_day1":
            return "regenerate_day1_plan"
        elif state.get("last_question") == "day1_revised_review":
            return "handle_day1_revised_review"
        elif state.get("last_question") == "day1_complete":
            # Check if pending_node is set (for single-call generation)
            pending = state.get("pending_node")
            if pending == "generate_all_remaining_exercise_days":
                return "generate_all_remaining_exercise_days"
            # Fallback to old day-by-day approach
            return "generate_day2_plan"
        elif state.get("last_question") == "day2_complete":
            return "generate_day3_plan"
        elif state.get("last_question") == "day3_complete":
            return "generate_day4_plan"
        elif state.get("last_question") == "day4_complete":
            return "generate_day5_plan"
        elif state.get("last_question") == "day5_complete":
            return "generate_day6_plan"
        elif state.get("last_question") == "day6_complete":
            return "generate_day7_plan"
            
    # Post-plan handling - only if both plans are sent or we're in post-plan state
    elif (state.get("meal_plan_sent") and state.get("exercise_plan_sent")) or state.get("last_question") == "post_plan":
        return "post_plan_qna"
    
    # Fallback
    return "verify_user"


def resume_router(state: State) -> str:
    """Route back to the interrupted node after health Q&A or product Q&A."""
    pending = state.get("pending_node")
    logger.info("RESUME ROUTER - Pending node: %s", pending)
    
    # If both plans are completed, clear pending_node and go to post-plan Q&A
    if state.get("meal_plan_sent") and state.get("exercise_plan_sent"):
        logger.info("RESUME ROUTER - Both plans completed, routing to post_plan_qna")
        return "post_plan_qna"
    
    # If we have a pending node and we're still in plan generation, resume from there
    if pending and not state.get("exercise_plan_sent"):
        # Map last_question values to actual node names if needed
        question_to_node_map = {
            "meal_day1_plan_review": "handle_meal_day1_review_choice",
            "meal_day1_revised_review": "handle_meal_day1_revised_review",
            "day1_plan_review": "handle_day1_review_choice",
            "day1_revised_review": "handle_day1_revised_review",
            "generate_meal_day1_plan": "generate_meal_plan",
            "generate_day1_plan": "generate_day1_plan",
        }
        # If pending is a last_question value, map it to the actual node
        mapped_pending = question_to_node_map.get(pending, pending)
        # Return to the SAME node that was interrupted, not the next one
        # This ensures the user gets asked the question they didn't answer yet
        logger.info("RESUME ROUTER - Returning to: %s (original pending: %s)", mapped_pending, pending)
        return mapped_pending
    
    # If we don't have a pending node, go to collect_age as a fallback
    if not pending:
        logger.info("RESUME ROUTER - No pending node, defaulting to collect_age")
        return "collect_age"
        
    return "post_plan_qna"
