"""
Router functions for the chatbot agent.

This module contains the main routing logic that determines which node
to execute next based on the current state of the conversation.
"""

import random
import logging
from typing import Optional
import re
from app.services.chatbot.bugzy_ams.state import State
from app.services.chatbot.bugzy_ams.constants import (
    QUESTION_TO_NODE,
    EDIT_EXISTING_MEAL_PLAN,
    CREATE_NEW_MEAL_PLAN,
    EDIT_EXISTING_EXERCISE_PLAN,
    CREATE_NEW_EXERCISE_PLAN,
)
from app.services.chatbot.router_constants import (
    KEY_USER_ID,
    KEY_USER_MSG,
    KEY_LAST_QUESTION,
    KEY_PENDING_NODE,
    KEY_CURRENT_AGENT,
    KEY_CONVERSATION_HISTORY,
    KEY_USER_NAME,
    KEY_JOURNEY_HISTORY,
    NODE_VERIFY_USER,
    NODE_POST_PLAN_QNA,
    NODE_TRANSITION_TO_SNAP,
    NODE_SNAP_IMAGE_ANALYSIS,
    NODE_TRANSITION_TO_GUT_COACH,
    NODE_ASK_MEAL_PREFERENCE,
    NODE_COLLECT_DIET_PREFERENCE_AMS,
    NODE_TRANSITION_TO_EXERCISE,
    NODE_COLLECT_HEALTH_CONDITIONS,
    NODE_COLLECT_AGE,
    NODE_ASK_EXISTING_MEAL_PLAN_CHOICE,
    STATE_VERIFIED,
    AGENT_MEAL,
    AGENT_EXERCISE,
    AGENT_SNAP,
    AGENT_GUT_COACH,
    AGENT_QNA,
    KEY_AGE,
    KEY_HEIGHT,
    KEY_WEIGHT,
    AMS_MEAL_FLOW_MAP,
    AMS_EXERCISE_FLOW_MAP,
    NODE_ASK_EXERCISE_PREFERENCE,
)
from app.services.whatsapp.client import send_whatsapp_message
from app.services.whatsapp.utils import _store_system_message
from app.services.crm.sessions import load_meal_plan, load_exercise_plan
from app.services.prompts.ams.health_product_detection import (
    is_health_question,
    is_product_question,
)
from app.services.chatbot.bugzy_shared.qna import (
    is_any_product_query,
    is_product_question as is_prod_heuristic,
)
from app.services.chatbot.bugzy_shared.context import (
    is_meal_edit_request,
    is_exercise_edit_request,
)
from app.services.chatbot.bugzy_shared.extraction import extract_day_number

logger = logging.getLogger(__name__)


# --- Helper Functions for Router ---


def _resolve_pending_node_from_last_question(last_question: Optional[str]) -> str:
    """
    Convert a last_question value into a concrete node name to resume.

    In this codebase, `last_question` sometimes stores a *question key* (e.g. "age")
    and sometimes stores a *node name* (e.g. "collect_age"). QnA interruptions need
    a *node name* to resume correctly.
    """
    lq = (last_question or "").strip()
    if not lq:
        return NODE_ASK_MEAL_PREFERENCE

    mapped = QUESTION_TO_NODE.get(lq)
    if mapped:
        return mapped

    # Already a node name we can resume directly
    if lq in set(QUESTION_TO_NODE.values()):
        return lq
    if lq.startswith(("collect_", "ask_", "handle_", "generate_", "transition_")):
        return lq

    return NODE_ASK_MEAL_PREFERENCE


def _contains_word(text: str, word: str) -> bool:
    """True if `word` appears as a standalone token (case-insensitive)."""
    if not text or not word:
        return False
    return bool(
        re.search(rf"(?<!\\w){re.escape(word)}(?!\\w)", text, flags=re.IGNORECASE)
    )


def _is_affirmative(text: str) -> bool:
    """Conservative yes-intent detection for preference prompts."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if _contains_word(t, "yes") or _contains_word(t, "yeah") or _contains_word(t, "yep"):
        return True
    if _contains_word(t, "sure") or _contains_word(t, "ok") or _contains_word(t, "okay"):
        return True
    if "let's go" in t or "lets go" in t:
        return True
    # Only treat create/make/build as yes if it's clearly about a plan
    if ("create" in t or "make" in t or "build" in t) and "plan" in t:
        return True
    return False


def _is_negative_or_defer(text: str) -> bool:
    """Conservative no/defer detection for preference prompts."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if _contains_word(t, "no") or _contains_word(t, "nah") or _contains_word(t, "nope"):
        return True
    if "later" in t or "not now" in t or "maybe later" in t or "not today" in t:
        return True
    if _contains_word(t, "skip") or _contains_word(t, "pass") or _contains_word(t, "busy"):
        return True
    if "don't" in t or "dont" in t:
        return True
    return False


def _is_greeting_message(text: str) -> bool:
    """Return True if the message is a short greeting/salutation without other intent."""
    if not text:
        return False
    msg = text.strip().lower()
    greetings = {
        "hi",
        "hello",
        "hey",
        "heyy",
        "heyyy",
        "hiya",
        "yo",
        "sup",
        "namaste",
        "good morning",
        "gm",
        "good afternoon",
        "good evening",
        "ge",
        "morning",
        "afternoon",
        "evening",
        "hola",
        "hii",
        "helloo",
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
        bool((state.get(KEY_AGE) or "").strip())
        and bool((state.get(KEY_HEIGHT) or "").strip())
        and bool((state.get(KEY_WEIGHT) or "").strip())
    )


def _has_any_profiling_data(state: dict) -> bool:
    """Check if user has ANY profiling data (age OR height OR weight).
    Used to detect legacy sessions with partial profiling."""
    return (
        bool((state.get(KEY_AGE) or "").strip())
        or bool((state.get(KEY_HEIGHT) or "").strip())
        or bool((state.get(KEY_WEIGHT) or "").strip())
    )


def _is_at_or_after_health_conditions(state: dict) -> bool:
    """Check if last_question is health_conditions or any subsequent step in the flow."""
    order = [
        "verified",
        "age",
        "height",
        "weight",
        "bmi_calculated",
        "ask_meal_plan_preference",
        "health_conditions",
        "collect_health_conditions",
        "medications",  # Now part of meal planner
        "existing_meal_plan_choice",
        "diet_preference",
        "cuisine_preference",
        "current_dishes",
        "allergies",
        "water_intake",
        "beverages",
        "supplements",
        "gut_health",
        "meal_goals",
        "meal_day1_plan_review",
        "awaiting_meal_day1_changes",
        "regenerating_meal_day1",
        "meal_day1_revised_review",
        "meal_day1_complete",
        "meal_day2_complete",
        "meal_day3_complete",
        "meal_day4_complete",
        "meal_day5_complete",
        "meal_day6_complete",
        "generate_meal_plan",
        "meal_plan_complete",
        "ask_exercise_plan_preference",
        "existing_exercise_plan_choice",
        "transition_to_exercise",
        "fitness_level",
        "activity_types",
        "exercise_frequency",
        "exercise_intensity",
        "session_duration",
        "sedentary_time",
        "exercise_goals",
        "day1_plan_review",
        "awaiting_day1_changes",
        "regenerating_day1",
        "day1_revised_review",
        "day1_complete",
        "day2_complete",
        "day3_complete",
        "day4_complete",
        "day5_complete",
        "day6_complete",
        "generate_day1_plan",
        "exercise_plan_complete",
        "transition_to_snap",
        "snap_complete",
        "transition_to_gut_coach",
        "post_plan_qna",
    ]
    lq = (state.get(KEY_LAST_QUESTION) or "").strip()
    if lq not in order:
        return False
    # Check if we're at or after health_conditions (first meal planning question)
    if "health_conditions" not in order:
        return False
    return order.index(lq) >= order.index("health_conditions")


def _get_resume_node_ams(state: State) -> str:
    """Find the next missing question in the AMS journey."""
    # 1. Basic Profiling
    if not (state.get(KEY_AGE) or "").strip():
        return NODE_COLLECT_AGE
    if not (state.get(KEY_HEIGHT) or "").strip():
        return "collect_height"
    if not (state.get(KEY_WEIGHT) or "").strip():
        return "collect_weight"
    if not state.get("bmi_calculated"):
        return "calculate_bmi"

    # 2. Determine sub-flow based on last attempt
    attempt = state.get("voice_agent_last_attempt")

    if attempt == "exercise_planning" or state.get(KEY_CURRENT_AGENT) == AGENT_EXERCISE:
        # Exercise flow profiling
        exercise_flow = [
            ("fitness_level", "fitness_level"),
            ("activity_types", "activity_types"),
            ("exercise_frequency", "exercise_frequency"),
            ("exercise_intensity", "exercise_intensity"),
            ("session_duration", "session_duration"),
            ("sedentary_time", "sedentary_time"),
            ("exercise_goals", "exercise_goals"),
        ]
        for field, lq_name in exercise_flow:
            val = state.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                if field == "fitness_level":
                    return NODE_TRANSITION_TO_EXERCISE
                return lq_name
        return "generate_day1_plan"

    else:
        # Meal flow profiling (default or explicit meal_planning)
        if not (state.get("health_conditions") or "").strip():
            return NODE_COLLECT_HEALTH_CONDITIONS

        # medications is conditional
        hc = (state.get("health_conditions") or "").lower()
        has_hc = hc and hc not in ["none", "no", "nil", "nothing", "health_none"]
        if has_hc and not (state.get("medications") or "").strip():
            return "collect_medications"

        meal_flow = [
            ("diet_preference", "diet_preference"),
            ("cuisine_preference", "cuisine_preference"),
            ("current_dishes", "current_dishes"),
            ("allergies", "allergies"),
            ("water_intake", "water_intake"),
            ("beverages", "beverages"),
            ("supplements", "supplements"),
            ("gut_health", "gut_health"),
            ("meal_goals", "meal_goals"),
        ]
        for field, lq_name in meal_flow:
            val = state.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                if field == "diet_preference":
                    return NODE_COLLECT_DIET_PREFERENCE_AMS
                return f"collect_{field}"
        return "generate_meal_plan"


def _should_apply_greeting_resume(state: dict) -> bool:
    """Apply greeting-resume only if not in post_plan_qna, weight done, and at/after health_conditions."""
    if (
        state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA
        or state.get(KEY_LAST_QUESTION) == NODE_POST_PLAN_QNA
    ):
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
    if (
        state.get("current_agent") == "post_plan_qna"
        or state.get("last_question") == "post_plan_qna"
    ):
        return False
    if not _has_completed_weight(state):
        return False
    return _is_at_or_after_health_conditions(state)


def is_journey_restart_request(user_msg: str) -> Optional[str]:
    """
    Detect if user wants to start/restart a meal or exercise plan journey.
    Returns 'meal', 'exercise', 'both', or None.
    """
    if not user_msg:
        return None

    text = user_msg.lower()

    import re

    # Check for specific "both" patterns with regex
    both_pattern_regex = r"(both|all)\s+(plans?|journeys?)"
    if re.search(both_pattern_regex, text) or ("meal" in text and "exercise" in text):
        return "both"

    # Check meal patterns with regex for typo tolerance
    meal_pattern_regex = (
        r"(meal|diet|nutrition|food|eating)\s+(plan|journey|plam|pla|program|schedule)"
    )
    wants_meal = bool(re.search(meal_pattern_regex, text))

    # Check exercise patterns with regex for typo tolerance
    exercise_pattern_regex = r"(exercise|workout|fitness|training|gym)\s+(plan|journey|plam|pla|program|schedule)"
    wants_exercise = bool(re.search(exercise_pattern_regex, text))

    # Refine intent verbs (want, create, start, give, make)
    intent_verbs = [
        "want",
        "need",
        "give",
        "make",
        "create",
        "start",
        "begin",
        "can i have",
        "get",
        "send",
        "show",
        "build",
        "generate",
        "would like",
        "interested in",
    ]
    has_intent = any(v in text for v in intent_verbs)

    # Negative filtering
    negative_patterns = [
        "don't want",
        "no ",
        "stop",
        "cancel",
        "hate",
        "dislike",
        "already have",
    ]
    is_negative = any(p in text for p in negative_patterns)

    if is_negative:
        return None

    if wants_meal and wants_exercise:
        return "both"

    # If explicit intent verb is present OR simple short phrase like "meal plan please"
    if has_intent or len(text.split()) <= 5:
        if wants_meal:
            return "meal"
        if wants_exercise:
            return "exercise"

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
    if "?" in text:
        return True

    # Check for question words at the start
    question_starters = [
        "what",
        "how",
        "why",
        "when",
        "where",
        "who",
        "which",
        "whom",
        "whose",
        "can",
        "could",
        "would",
        "should",
        "will",
        "shall",
        "may",
        "might",
        "do",
        "does",
        "did",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "am i",
        "is it",
        "are there",
        "is there",
        "can i",
        "should i",
        "do i",
        "tell me",
        "show me",
        "explain",
        "help me",
        "any",
        "recommend",
    ]

    # Check if text starts with any question starter
    words = text_lower.split()
    if words and any(text_lower.startswith(starter) for starter in question_starters):
        return True

    # Check for question phrases anywhere in the text
    question_phrases = [
        "can you tell",
        "could you tell",
        "do you know",
        "would you recommend",
        "what about",
        "how about",
        "is it okay",
        "is it safe",
        "is it good",
        "should i take",
        "can i take",
        "may i",
        "could i",
    ]

    if any(phrase in text_lower for phrase in question_phrases):
        return True

    return False


# Local helpers removed in favor of shared modules


# --- Main Router Functions ---


def router(state: State) -> str:
    """Central brain that decides the next step based on saved state."""
    # Import handle_validated_input here to avoid circular imports
    from app.services.chatbot.bugzy_ams.nodes.user_verification_nodes import (
        handle_validated_input,
    )
    from app.services.chatbot.bugzy_ams.nodes.qna_nodes import (
        is_contextual_product_question,
    )

    logger.info("ROUTING with state keys: %s", state.keys())

    user_msg = state.get(KEY_USER_MSG, "").lower().strip()

    # Check for restart command
    if user_msg == "restart":
        return NODE_VERIFY_USER

    # BULLETPROOF: "Make Changes" on Day 1 meal plan → always go to collect changes (ask "what changes?")
    # Matches: button ids. Ignores last_question (e.g. stale voice_agent_promotion_meal from voice flow).
    _make_changes_meal = (
        "make_changes_meal_day1" in user_msg or "more_changes_meal_day1" in user_msg
    )
    if _make_changes_meal:
        logger.info(
            "ROUTER: Make Changes (meal Day 1) → handle_meal_day1_review_choice (last_q=%s)",
            state.get(KEY_LAST_QUESTION),
        )
        return "handle_meal_day1_review_choice"

    # BULLETPROOF: "Make Changes" on Day 1 exercise plan → always go to collect changes (ask "what changes?")
    # Matches: button ids (make_changes_exercise_day1 now in AMS_BUTTON_MAP) + title fallback "make changes".
    # Ignores last_question (e.g. stale voice_agent_promotion_exercise from voice flow).
    _make_changes_exercise = (
        "make_changes_exercise_day1" in user_msg
        or "make_changes_day1" in user_msg
        or "more_changes_day1" in user_msg
        or (
            "make changes" in user_msg
            and (state.get(KEY_CURRENT_AGENT) == AGENT_EXERCISE or state.get(KEY_LAST_QUESTION) == "day1_plan_review")
        )  # title fallback when button id not in map
    )
    if _make_changes_exercise:
        logger.info(
            "ROUTER: Make Changes (exercise Day 1) → handle_day1_review_choice (last_q=%s)",
            state.get(KEY_LAST_QUESTION),
        )
        return "handle_day1_review_choice"

    # Greeting-only messages: only resume if not in post_plan_qna,
    # weight completed, and at/after health_conditions
    if _is_greeting_message(
        state.get(KEY_USER_MSG, "")
    ) and _should_apply_greeting_resume(state):
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
                "🌟 Great! Let's pick up where we were...",
            ]
            send_whatsapp_message(state[KEY_USER_ID], random.choice(resume_msgs))
        except Exception:
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
            logger.info(
                "GREET ROUTE - Greeting detected, resuming pending node: %s (original pending: %s)",
                mapped_pending,
                pending,
            )
            return mapped_pending
        current_question = state.get(KEY_LAST_QUESTION)
        question_to_node = QUESTION_TO_NODE
        if current_question in question_to_node:
            node = question_to_node[current_question]
            logger.info(
                "GREET ROUTE - Greeting detected, resuming current step: %s", node
            )
            return node
        logger.info(
            "GREET ROUTE - Greeting detected but insufficient context; verifying user"
        )
        return NODE_VERIFY_USER

    # Resume journey button clicks: resume as long as not in post_plan_qna
    # Removed restrictive checks for weight/health_conditions to allow resume at any point
    if _is_resume_journey_button(state.get(KEY_USER_MSG, "")) and not (
        state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA
        or state.get(KEY_LAST_QUESTION) == NODE_POST_PLAN_QNA
    ):
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
                "🌟 Great! Let's pick up where we were...",
            ]
            send_whatsapp_message(state[KEY_USER_ID], random.choice(resume_msgs))
        except Exception:
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
            logger.info(
                "RESUME BUTTON ROUTE - Resume button detected, resuming pending node: %s (original pending: %s)",
                mapped_pending,
                pending,
            )
            return mapped_pending
        current_question = state.get(KEY_LAST_QUESTION)
        question_to_node = QUESTION_TO_NODE
        if current_question in question_to_node:
            node = question_to_node[current_question]
            logger.info(
                "RESUME BUTTON ROUTE - Resume button detected, resuming current step: %s",
                node,
            )
            return node
        logger.info(
            "RESUME BUTTON ROUTE - Resume button detected but insufficient context; verifying user"
        )
        return NODE_VERIFY_USER

    # PRIORITY: Check for PLAN EDIT FLOW states FIRST (before post-plan routing)
    # This ensures edit requests are handled even when both plans are completed
    # PRIORITY: Check for PLAN EDIT FLOW states FIRST (before post-plan routing)
    # This ensures edit requests are handled even when both plans are completed
    if state.get(KEY_LAST_QUESTION) == "select_meal_day_to_edit":
        return "handle_meal_day_selection_for_edit"
    elif (
        state.get(KEY_LAST_QUESTION)
        and str(state.get(KEY_LAST_QUESTION)).startswith("awaiting_meal_day")
        and str(state.get(KEY_LAST_QUESTION)).endswith("_edit_changes")
    ):
        return "collect_meal_day_edit_changes"
    elif state.get(KEY_LAST_QUESTION) == "select_exercise_day_to_edit":
        return "handle_exercise_day_selection_for_edit"
    elif (
        state.get(KEY_LAST_QUESTION)
        and str(state.get(KEY_LAST_QUESTION)).startswith("awaiting_exercise_day")
        and str(state.get(KEY_LAST_QUESTION)).endswith("_edit_changes")
    ):
        return "collect_exercise_day_edit_changes"
    elif state.get(KEY_LAST_QUESTION) == "existing_meal_plan_choice":
        # IMPORTANT: This must be handled before post-plan routing,
        # otherwise we'll always get forced into post_plan_qna.
        msg = (state.get(KEY_USER_MSG) or "").lower().strip()
        logger.info(
            "🔍 ROUTER (AMS): Handling existing_meal_plan_choice, user_msg='%s'", msg
        )

        if msg == EDIT_EXISTING_MEAL_PLAN or "edit" in msg:
            state["wants_meal_plan"] = True
            return "load_existing_meal_plan_for_edit"
        if (
            msg == CREATE_NEW_MEAL_PLAN
            or "create" in msg
            or "new" in msg
            or "fresh" in msg
            or "restart" in msg
        ):
            logger.info("🔍 ROUTER (AMS): User chose CREATE NEW MEAL PLAN")
            logger.info("🔍 ROUTER (AMS): State before changes:")
            logger.info("  - current_agent: %s", state.get(KEY_CURRENT_AGENT))
            logger.info(
                "  - existing_meal_plan_choice_origin: %s",
                state.get("existing_meal_plan_choice_origin"),
            )
            logger.info("  - meal_plan_sent: %s", state.get("meal_plan_sent"))

            state["wants_meal_plan"] = True

            # CRITICAL FIX: Check if user was in post_plan_qna BEFORE changing current_agent
            # This is the key to detecting recreation vs first-time creation
            was_in_post_plan = (
                state.get("existing_meal_plan_choice_origin") == NODE_POST_PLAN_QNA
                or state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA
            )

            logger.info("🔍 ROUTER (AMS): was_in_post_plan = %s", was_in_post_plan)

            # Now change the agent
            state[KEY_CURRENT_AGENT] = AGENT_MEAL

            # If we're in post-plan context, ensure we don't get stuck in post_plan_qna routing.
            if state.get("meal_plan_sent"):
                state["meal_plan_sent"] = False

            # Set journey_restart_mode if this was a recreation from post_plan_qna
            if was_in_post_plan:
                state["journey_restart_mode"] = True
                state["existing_meal_plan_choice_origin"] = (
                    NODE_POST_PLAN_QNA  # Set it here for consistency
                )
                logger.info(
                    "🔄 JOURNEY RESTART MODE (AMS): Set to True (user recreating meal plan from post_plan_qna)"
                )
            else:
                logger.info(
                    "⚠️  ROUTER (AMS): NOT setting journey_restart_mode (was_in_post_plan=False)"
                )

            logger.info("🔍 ROUTER (AMS): State after changes:")
            logger.info(
                "  - journey_restart_mode: %s", state.get("journey_restart_mode")
            )
            logger.info(
                "  - existing_meal_plan_choice_origin: %s",
                state.get("existing_meal_plan_choice_origin"),
            )
            logger.info("  - current_agent: %s", state.get(KEY_CURRENT_AGENT))

            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return "collect_health_conditions"
            return "collect_age"
        return "ask_existing_meal_plan_choice"
    elif state.get(KEY_LAST_QUESTION) == "existing_exercise_plan_choice":
        # IMPORTANT: Must be handled before post-plan routing.
        msg = (state.get(KEY_USER_MSG) or "").lower().strip()
        logger.info(
            "🔍 ROUTER: Handling existing_exercise_plan_choice, user_msg='%s'", msg
        )

        if msg == EDIT_EXISTING_EXERCISE_PLAN or "edit" in msg:
            state["wants_exercise_plan"] = True
            return "load_existing_exercise_plan_for_edit"
        if (
            msg == CREATE_NEW_EXERCISE_PLAN
            or "create" in msg
            or "new" in msg
            or "fresh" in msg
            or "restart" in msg
        ):
            logger.info("🔍 ROUTER: User chose CREATE NEW EXERCISE PLAN")
            logger.info("🔍 ROUTER: State before changes:")
            logger.info("  - current_agent: %s", state.get(KEY_CURRENT_AGENT))
            logger.info(
                "  - existing_exercise_plan_choice_origin: %s",
                state.get("existing_exercise_plan_choice_origin"),
            )
            logger.info("  - exercise_plan_sent: %s", state.get("exercise_plan_sent"))

            state["wants_exercise_plan"] = True

            # CRITICAL FIX: Check if user was in post_plan_qna BEFORE changing current_agent
            # This is the key to detecting recreation vs first-time creation
            was_in_post_plan = (
                state.get("existing_exercise_plan_choice_origin") == NODE_POST_PLAN_QNA
                or state.get(KEY_CURRENT_AGENT) == NODE_POST_PLAN_QNA
            )

            logger.info("🔍 ROUTER: was_in_post_plan = %s", was_in_post_plan)

            # Now change the agent
            state[KEY_CURRENT_AGENT] = AGENT_EXERCISE

            # Prevent forced post_plan_qna during the new journey
            if state.get("exercise_plan_sent"):
                state["exercise_plan_sent"] = False

            # Set journey_restart_mode if this was a recreation from post_plan_qna
            if was_in_post_plan:
                state["journey_restart_mode"] = True
                state["existing_exercise_plan_choice_origin"] = (
                    NODE_POST_PLAN_QNA  # Set it here for consistency
                )
                logger.info(
                    "🔄 JOURNEY RESTART MODE: Set to True (user recreating exercise plan from post_plan_qna)"
                )
            else:
                logger.info(
                    "⚠️  ROUTER: NOT setting journey_restart_mode (was_in_post_plan=False)"
                )

            logger.info("🔍 ROUTER: State after changes:")
            logger.info(
                "  - journey_restart_mode: %s", state.get("journey_restart_mode")
            )
            logger.info(
                "  - existing_exercise_plan_choice_origin: %s",
                state.get("existing_exercise_plan_choice_origin"),
            )
            logger.info("  - current_agent: %s", state.get(KEY_CURRENT_AGENT))

            if (
                state.get("profiling_collected")
                or state.get("journey_restart_mode")
                or _has_completed_weight(state)
            ):
                return NODE_TRANSITION_TO_EXERCISE
            return "collect_age"
        return "ask_existing_exercise_plan_choice"

    # PRIORITY: Check if we're in post-plan state (both plans completed)
    # BUT NOT if we're still in the SNAP image analysis flow
    # AND NOT if we're in the middle of creating a NEW meal plan (Create New Plan questionnaire)
    # AND NOT if we're in journey_restart_mode (recreating plan)
    if (
        state.get("meal_plan_sent")
        and state.get("exercise_plan_sent")
        and not state.get("journey_restart_mode")
    ) or state.get(KEY_LAST_QUESTION) == NODE_POST_PLAN_QNA:
        # Exception: If we're waiting for image analysis or transitioning from it, don't skip to post_plan_qna yet
        if state.get(KEY_LAST_QUESTION) in [
            "exercise_plan_complete",
            "snap_complete",
            "transitioning_to_snap",
            "transitioning_to_gut_coach",
        ]:
            # Continue with normal flow to handle SNAP
            pass
        # Exception: If we're in the meal plan questionnaire or day-1 review/7-day flow, continue flow (do NOT go to post_plan_qna)
        elif state.get(KEY_LAST_QUESTION) in [
            "health_conditions",
            "medications",
            "diet_preference",
            "cuisine_preference",
            "current_dishes",
            "allergies",
            "water_intake",
            "beverages",
            "supplements",
            "gut_health",
            "meal_goals",
            "generate_meal_plan",
            "meal_day1_plan_review",
            "awaiting_meal_day1_changes",
            "regenerating_meal_day1",
            "meal_day1_revised_review",
            "meal_day1_complete",
            "meal_day2_complete",
            "meal_day3_complete",
            "meal_day4_complete",
            "meal_day5_complete",
            "meal_day6_complete",
            "meal_day7_complete",
            # EXERCISE NODES (FITT Assessment)
            "fitness_level",
            "activity_types",
            "exercise_frequency",
            "exercise_intensity",
            "session_duration",
            "sedentary_time",
            "exercise_goals",
            # Exercise Plan Review
            "day1_plan_review",
            "awaiting_day1_changes",
            "regenerating_day1",
            "day1_revised_review",
            "day1_complete",
            "day2_complete",
            "day3_complete",
            "day4_complete",
            "day5_complete",
            "day6_complete",
            "day7_complete",
            # QNA RESUME STATES
            "health_qna_answered",
            "product_qna_answered",
            "resuming_from_health_qna",
            "resuming_from_product_qna",
        ]:
            pass  # Fall through to meal/exercise agent routing
        else:
            # Route all questions to post-plan Q&A handler
            return NODE_POST_PLAN_QNA

    # PRIORITY: Check for health and product questions BEFORE validation
    # This ensures these questions are handled properly even during data collection

    # Check if user is asking a product/company question
    # Strictly use shared is_any_product_query for consistent detection
    conversation_history = state.get(KEY_CONVERSATION_HISTORY, [])
    if is_any_product_query(user_msg, conversation_history):
        logger.info(
            "ROUTER PRODUCT DETECTION | Product query detected | msg='%s'", user_msg
        )

        # Check if both plans are completed - if so, route to post_plan_qna
        plans_completed = (
            bool(state.get("meal_plan_sent"))
            and bool(state.get("exercise_plan_sent"))
            and not state.get("journey_restart_mode")
        )

        if plans_completed:
            return NODE_POST_PLAN_QNA

        # Handle product questions during data collection
        current_question = state.get(KEY_LAST_QUESTION)
        if current_question and current_question not in [
            None,
            STATE_VERIFIED,
            NODE_POST_PLAN_QNA,
            "health_qna_answered",
            "product_qna_answered",
        ]:
            state[KEY_PENDING_NODE] = _resolve_pending_node_from_last_question(
                current_question
            )
        return "product_qna"

    # Check if user is asking a health question
    # If not a product question, check if it's health-related
    if is_health_question(user_msg):
        # Check if both plans are completed - if so, route to post_plan_qna
        plans_completed = (
            bool(state.get("meal_plan_sent"))
            and bool(state.get("exercise_plan_sent"))
            and not state.get("journey_restart_mode")
        )

        if plans_completed:
            return NODE_POST_PLAN_QNA

        # Review states should handle their own input
        review_choice_states = [
            "day1_plan_review",
            "day1_revised_review",
            "awaiting_day1_changes",
            "meal_day1_plan_review",
            "meal_day1_revised_review",
            "awaiting_meal_day1_changes",
        ]

        if (
            state.get(KEY_LAST_QUESTION)
            not in [
                None,
                STATE_VERIFIED,
                NODE_POST_PLAN_QNA,
                "health_qna_answered",
                "product_qna_answered",
            ]
            + review_choice_states
        ):
            current_question = state.get(KEY_LAST_QUESTION)
            if current_question:
                state[KEY_PENDING_NODE] = _resolve_pending_node_from_last_question(
                    current_question
                )
            return "health_qna"

    # Basic profiling chain: last_question="age" means we asked for HEIGHT, so user_msg IS height.
    # Do NOT validate user_msg as "age" — route directly to collect_height/collect_weight.
    # (Validation block would fail "172 cm" as age and cause "I didn't catch that" + wrong routing)
    if state.get(KEY_LAST_QUESTION) == "age" and state.get(KEY_USER_MSG):
        logger.info("ROUTER: age→collect_height (user_msg is height answer)")
        return "collect_height"
    if state.get(KEY_LAST_QUESTION) == "height" and state.get(KEY_USER_MSG):
        logger.info("ROUTER: height→collect_weight (user_msg is weight answer)")
        return "collect_weight"

    # Now handle validation for current pending input
    current_question = state.get(KEY_LAST_QUESTION)
    if current_question and state.get(KEY_USER_MSG):
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
            "health_conditions": "health_conditions",
            "medications": "medications",
            "diet_preference": "diet_preference",
            "cuisine_preference": "cuisine_preference",
            "current_dishes": "current_dishes",
            "allergies": "allergies",
            "water_intake": "water_intake",
            "beverages": "beverages",
            "supplements": "supplements",
            "gut_health": "gut_health",
            "meal_goals": "meal_goals",
            "fitness_level": "fitness_level",
            "activity_types": "activity_types",
            "exercise_frequency": "exercise_frequency",
            "exercise_intensity": "exercise_intensity",
            "session_duration": "session_duration",
            "sedentary_time": "sedentary_time",
            "exercise_goals": "exercise_goals",
        }

        expected_field = field_mapping.get(current_question)
        VOICE_BYPASS_FIELDS = (
            "age", "height", "weight",
            "diet_preference", "cuisine_preference", "current_dishes",
            "allergies", "water_intake", "beverages", "supplements",
            "gut_health", "meal_goals",
            "fitness_level", "activity_types", "exercise_frequency",
            "exercise_intensity", "session_duration", "sedentary_time", "exercise_goals",
        )
        if state.get("interaction_mode") == "voice" and expected_field in VOICE_BYPASS_FIELDS:
            if current_question == "age":
                return "collect_age"
            return f"collect_{expected_field}"
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
                    question_to_node_retry = {
                        "meal_day1_plan_review": "handle_meal_day1_review_choice",
                        "meal_day1_revised_review": "handle_meal_day1_revised_review",
                        "day1_plan_review": "handle_day1_review_choice",
                        "day1_revised_review": "handle_day1_revised_review",
                        "awaiting_meal_day1_changes": "collect_meal_day1_changes",
                        "awaiting_day1_changes": "collect_day1_changes",
                    }
                    if current_question in question_to_node_retry:
                        return question_to_node_retry[current_question]
                    return "collect_age" if current_question == "age" else f"collect_{current_question}"
                if validation_result == "valid":
                    # Route to collect node so it persists the value
                    if current_question == "age":
                        return "collect_age"
                    return f"collect_{current_question}"

    # If returning from health Q&A, product Q&A, snap/image analysis, or other interruptions, resume where we left off
    if state.get(KEY_LAST_QUESTION) in [
        "health_qna_answered",
        "product_qna_answered",
        "resuming_from_health_qna",
        "resuming_from_product_qna",
        "image_analysis_complete",
        "resuming_from_snap",
    ]:
        pending = state.get(KEY_PENDING_NODE)
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
            logger.info(
                "RESUMING to node: %s (original pending: %s)", mapped_pending, pending
            )
            # Just return to the same node where we left off
            return mapped_pending

    # SNAP IMAGE ANALYSIS FLOW - Check this EARLY to catch transitions
    # This must come before basic info collection to avoid falling through
    if (
        state.get("exercise_plan_sent")
        and state.get(KEY_LAST_QUESTION) == "exercise_plan_complete"
        and not state.get("snap_analysis_sent")
    ):
        if not _has_completed_weight(state):
            return "collect_age"
        return NODE_SNAP_IMAGE_ANALYSIS
    elif state.get(KEY_LAST_QUESTION) == "transitioning_to_snap":
        # User is in SNAP transition, route to snap_image_analysis
        return NODE_SNAP_IMAGE_ANALYSIS
    elif state.get("snap_analysis_sent") and state.get(KEY_LAST_QUESTION) in [
        "snap_complete",
        "transitioning_to_gut_coach",
    ]:
        return NODE_TRANSITION_TO_GUT_COACH

    # Initial verification flow
    if state.get(KEY_LAST_QUESTION) is None:
        return NODE_VERIFY_USER
    elif state.get(KEY_LAST_QUESTION) == STATE_VERIFIED:
        return NODE_ASK_MEAL_PREFERENCE

    # Basic info collection (shared) - Route based on last_question
    elif state.get(KEY_LAST_QUESTION) == "age":
        return "collect_height"
    elif state.get(KEY_LAST_QUESTION) == "height":
        return "collect_weight"
    elif state.get(KEY_LAST_QUESTION) == "weight":
        # NEW: Set profiling flag and detect context
        state["profiling_collected"] = True

        # DEBUG: Log state to understand what's available
        logger.info(
            "[EARLY PROFILING DEBUG] After weight - current_agent=%s, wants_meal_plan=%s, wants_exercise_plan=%s, meal_plan_sent=%s, exercise_plan_sent=%s",
            state.get(KEY_CURRENT_AGENT),
            state.get("wants_meal_plan"),
            state.get("wants_exercise_plan"),
            state.get("meal_plan_sent"),
            state.get("exercise_plan_sent"),
        )

        # Determine context - where did we come from?
        # Use current_agent as primary indicator since it's more reliably persisted
        if state.get(KEY_CURRENT_AGENT) == AGENT_MEAL and not state.get(
            "meal_plan_sent"
        ):
            # We're collecting profiling EARLY in meal flow
            state["profiling_collected_in_meal"] = True
            logger.info(
                "[EARLY PROFILING] Weight collected in MEAL flow (agent=meal) - routing to calculate_bmi"
            )

        # Check if we're in exercise planning flow (early profiling)
        elif state.get(KEY_CURRENT_AGENT) == AGENT_EXERCISE and not state.get(
            "exercise_plan_sent"
        ):
            # We're collecting profiling EARLY in exercise flow
            state["profiling_collected_in_exercise"] = True
            logger.info(
                "[EARLY PROFILING] Weight collected in EXERCISE flow (agent=exercise) - routing to calculate_bmi"
            )

        # Otherwise, normal end-of-journey profiling (fallback scenario)
        else:
            logger.info(
                "[EARLY PROFILING] Weight collected in FALLBACK flow (end-of-journey, agent=%s) - routing to calculate_bmi",
                state.get(KEY_CURRENT_AGENT),
            )

        return "calculate_bmi"
    elif state.get(KEY_LAST_QUESTION) == "bmi_calculated":
        # CHANGED: Use context-aware routing after BMI
        return route_after_bmi_calculation(state)

    # DAY 1 PLAN REVIEW ROUTING - Must come BEFORE ask_meal_plan_preference
    # When user taps "Make Changes" after Day 1 plan, go directly to collect changes
    # instead of voice_agent_promotion (ask_meal_plan_preference "create" branch)
    elif state.get(KEY_LAST_QUESTION) == "meal_day1_plan_review":
        logger.info(
            "➡️  ROUTER: meal_day1_plan_review → handle_meal_day1_review_choice (Make Changes flow)"
        )
        return "handle_meal_day1_review_choice"
    elif state.get(KEY_LAST_QUESTION) == "meal_day1_revised_review":
        logger.info(
            "➡️  ROUTER: meal_day1_revised_review → handle_meal_day1_revised_review"
        )
        return "handle_meal_day1_revised_review"

    # MEAL PLAN PREFERENCE ROUTING (before agent-specific routing)
    # This needs to be checked early because current_agent might not be set yet
    elif state.get(KEY_LAST_QUESTION) == NODE_ASK_MEAL_PREFERENCE:
        # VOICE CALL: User called while at meal preference — assume they want meal plan, start journey
        if state.get("interaction_mode") == "voice":
            state["wants_meal_plan"] = True
            state["wants_exercise_plan"] = False
            state[KEY_CURRENT_AGENT] = AGENT_MEAL
            state["voice_agent_accepted"] = True
            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return "collect_health_conditions"
            return "collect_age"

        # Check user choice
        msg_raw = state.get(KEY_USER_MSG, "") or ""
        msg = msg_raw.lower()
        msg_id = msg_raw

        # Option 1: User wants to create meal plan
        # Match: "Create a meal plan" / "Sounds great! 🔥" / "Yes, create it! 🔥" / button ID "create_meal_plan"
        if (
            msg_id == "create_meal_plan"
            or "create" in msg_raw
            or "🔥" in msg_raw
            or _is_affirmative(msg_raw)
        ):
            state["wants_meal_plan"] = True
            state["wants_exercise_plan"] = False
            state[KEY_CURRENT_AGENT] = AGENT_MEAL

            existing_meal_plan = load_meal_plan(state.get(KEY_USER_ID, "")) or {}
            if existing_meal_plan and existing_meal_plan.get("meal_day1_plan"):
                state["existing_meal_plan_data"] = existing_meal_plan
                logger.info(
                    "✅ ROUTER: Existing meal plan found - asking edit vs new choice"
                )
                return "ask_existing_meal_plan_choice"

            logger.info("➡️  ROUTER: Routing to voice_agent_promotion_meal")
            return "voice_agent_promotion_meal"



        # Option 2: User already has a meal plan
        # Match: "I already have one 📋" / "Already sorted 📋" / "I've got one already 📋" / button ID "has_meal_plan"
        elif (
            msg_id == "has_meal_plan"
            or "already have" in msg
            or "already sorted" in msg
            or "already got" in msg
            or "i've got one" in msg
            or "got one already" in msg
            or "📋" in state.get(KEY_USER_MSG, "")
        ):
            state["wants_meal_plan"] = False
            send_whatsapp_message(
                state["user_id"],
                "Perfect! You're already ahead of the game 💚 Let’s move forward.\n\nJust so you know — once your journey is complete, you can always type *\"create a meal plan\"* anytime and I’ll build one for you instantly 📋✨",
            )
            _store_system_message(
                state,
                "Perfect! You're already ahead of the game 💚 Let’s move forward.\n\nJust so you know — once your journey is complete, you can always type *\"create a meal plan\"* anytime and I’ll build one for you instantly 📋✨",
            )
            logger.info(
                "➡️  ROUTER: User already has meal plan - routing to ask_exercise_plan_preference"
            )
            return "ask_exercise_plan_preference"

        # Option 3: User doesn't want meal plan now (Explicit NO)
        # Match: "Not right now" / "Not interested" / "Maybe later" / button ID "no_meal_plan" / "no" / "later"
        elif (
            msg_id == "no_meal_plan"
            or _is_negative_or_defer(msg_raw)
        ):
            state["wants_meal_plan"] = False
            send_whatsapp_message(
                state["user_id"],
                "No worries at all 💚 Let’s continue.\n\nAnd just a heads up — after your journey is complete, you can simply type *\"create a meal plan\"* anytime and I’ll prepare one for you 📋✨",
            )
            _store_system_message(
                state,
                "No worries at all 💚 Let’s continue.\n\nAnd just a heads up — after your journey is complete, you can simply type *\"create a meal plan\"* anytime and I’ll prepare one for you 📋✨",
            )
            logger.info(
                "➡️  ROUTER: Meal plan declined - routing to ask_exercise_plan_preference"
            )
            return "ask_exercise_plan_preference"

        # Option 4: Invalid Input (Catch-all)
        else:
            send_whatsapp_message(
                state["user_id"],
                "I didn't quite catch that. Please let me know nicely using the buttons below! 👇",
            )
            return NODE_ASK_MEAL_PREFERENCE

    # NEW: Handle voice agent promotion response
    elif state.get(KEY_LAST_QUESTION) == "voice_agent_promotion_meal":
        # VOICE CALL: User is already on the call — start the meal journey
        if state.get("interaction_mode") == "voice":
            state["voice_agent_accepted"] = True
            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return "collect_health_conditions"
            return "collect_age"

        msg_raw = state.get(KEY_USER_MSG, "") or ""
        msg = msg_raw.lower()
        msg_id = msg_raw

        # User chose chat
        if msg_id == "create_here_chat" or "chat" in msg:
            state["voice_agent_choice"] = "chat"
            state["voice_agent_declined"] = True
            
            # Route to appropriate data collection node
            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return "collect_health_conditions"
            else:
                return "collect_age"
        
        # User chose voice agent
        elif msg_id == "try_voice_agent" or "voice" in msg:
            # The button directly links to the wa.me Call URL now. We just end the graph here.
            return "__end__"
        
        # Unclear response -> Clarify
        else:
            return "voice_agent_promotion_meal"  # Re-ask

    # EXISTING MEAL PLAN CHOICE ROUTING
    elif state.get("last_question") == "existing_meal_plan_choice":
        msg = state.get("user_msg", "").lower()
        if msg == "edit_existing_meal_plan" or "edit" in msg:
            # User wants to edit existing plan - route to day selection
            logger.info("✅ ROUTER: User chose to edit existing plan")
            # Load the existing meal plan days into state
            existing_plan = (
                state.get("existing_meal_plan_data")
                or load_meal_plan(state.get("user_id", ""))
                or {}
            )
            for day in range(1, 8):
                day_key = f"meal_day{day}_plan"
                if day_key in existing_plan:
                    state[day_key] = existing_plan[day_key]
            return "handle_meal_day_selection_for_edit"
        elif msg == "create_new_meal_plan" or "new" in msg or "create" in msg:
            # User wants to create new plan - start fresh from health conditions
            logger.info("✅ ROUTER: User chose to create new plan")
            # Check if profiling already collected
            if state.get("profiling_collected") or state.get("journey_restart_mode"):
                return NODE_COLLECT_HEALTH_CONDITIONS
            else:
                return NODE_COLLECT_AGE
        else:
            # Invalid response - stay at the same node
            return NODE_ASK_EXISTING_MEAL_PLAN_CHOICE

    # MEAL PLANNER AGENT FLOW - Route based on last_question
    elif state.get(KEY_CURRENT_AGENT) == AGENT_MEAL:
        last_q = state.get(KEY_LAST_QUESTION)

        # 1. Complex Conditionals
        if last_q == "health_conditions" or last_q == NODE_COLLECT_HEALTH_CONDITIONS:
            # Conditional routing: check if health condition exists
            health_conditions = state.get("health_conditions", "").strip().lower()
            # Skip medications if no health condition or if health condition is "none"
            if not health_conditions or health_conditions in [
                "none",
                "no",
                "nil",
                "nothing",
                "health_none",
            ]:
                return NODE_COLLECT_DIET_PREFERENCE_AMS
            else:
                return "collect_medications"

        elif last_q == "meal_day1_complete":
            # Check if pending_node is set (for single-call generation)
            pending = state.get(KEY_PENDING_NODE)
            if pending == "generate_all_remaining_meal_days":
                return "generate_all_remaining_meal_days"
            # Fallback to old day-by-day approach
            return "generate_meal_day2_plan"

        elif state.get("meal_plan_sent") and last_q == "meal_plan_complete":
            return NODE_ASK_EXERCISE_PREFERENCE

        elif last_q == "existing_meal_plan_choice":
            msg = state.get(KEY_USER_MSG, "").lower()
            if msg == EDIT_EXISTING_MEAL_PLAN or "edit" in msg:
                state["wants_meal_plan"] = True
                return "load_existing_meal_plan_for_edit"
            if msg == CREATE_NEW_MEAL_PLAN or "create" in msg or "new" in msg:
                state["wants_meal_plan"] = True
                state["wants_exercise_plan"] = False
                if state.get("profiling_collected") or state.get(
                    "journey_restart_mode"
                ):
                    return NODE_COLLECT_HEALTH_CONDITIONS
                return NODE_COLLECT_AGE
            return NODE_ASK_EXISTING_MEAL_PLAN_CHOICE

        elif last_q == NODE_ASK_EXERCISE_PREFERENCE:
            msg_raw = state.get(KEY_USER_MSG, "") or ""
            msg = msg_raw.lower()
            msg_id = msg_raw

            # Option 1: User wants to create exercise plan
            # Match: "Create an exercise plan" / "Sounds great! 🔥" / "Yes, create it! 🔥" / button ID "create_exercise_plan"
            if (
                msg_id == "create_exercise_plan"
                or "create" in msg_raw
                or "🔥" in msg_raw
                or _is_affirmative(msg_raw)
            ):
                state["wants_exercise_plan"] = True
                state[KEY_CURRENT_AGENT] = AGENT_EXERCISE

                existing_exercise_plan = (
                    load_exercise_plan(state.get(KEY_USER_ID, "")) or {}
                )
                if existing_exercise_plan and existing_exercise_plan.get("day1_plan"):
                    state["existing_exercise_plan_data"] = existing_exercise_plan
                    logger.info(
                        "✅ ROUTER: Existing exercise plan found - asking edit vs new choice"
                    )
                    return "ask_existing_exercise_plan_choice"

                logger.info("➡️  ROUTER: Routing to voice_agent_promotion_exercise")
                return "voice_agent_promotion_exercise"



            # Option 2: User already has an exercise plan
            # Match: "I already have one 🏋️" / "Already sorted 🏋️" / "I've got one already 🏋️" / button ID "has_exercise_plan"
            elif (
                msg_id == "has_exercise_plan"
                or "already have" in msg
                or "already sorted" in msg
                or "already got" in msg
                or "i've got one" in msg
                or "got one already" in msg
                or "have one" in msg
                or "already" in msg
            ):
                state["wants_exercise_plan"] = False
                send_whatsapp_message(
                    state["user_id"],
                    "Amazing! You’re already putting in the work 💪 Let’s keep going.\n\nAnd remember — once your journey is complete, you can type *\"create an exercise plan\"* anytime and I’ll design one for you 🏋️✨",
                )
                _store_system_message(
                    state,
                    "Amazing! You’re already putting in the work 💪 Let’s keep going.\n\nAnd remember — once your journey is complete, you can type *\"create an exercise plan\"* anytime and I’ll design one for you 🏋️✨",
                )
                logger.info(
                    "➡️  ROUTER: User already has exercise plan - routing to required profiling"
                )
                if (
                    state.get("profiling_collected")
                    or _has_completed_weight(state)
                    or _has_any_profiling_data(state)
                ):
                    logger.info(
                        "[EARLY PROFILING] Already has exercise plan - profiling exists → transition_to_snap"
                    )
                    return NODE_TRANSITION_TO_SNAP
                else:
                    logger.info(
                        "[EARLY PROFILING] Already has exercise plan - no profiling data → collect_age"
                    )
                    return NODE_COLLECT_AGE

            # Option 3: User doesn't want exercise plan now (Explicit NO)
            # Match: "Not right now" / "Not interested" / "Maybe later" / button ID "no_exercise_plan" / "no" / "later"
            elif (
                msg_id == "no_exercise_plan"
                or _is_negative_or_defer(msg_raw)
            ):
                state["wants_exercise_plan"] = False
                send_whatsapp_message(
                    state["user_id"],
                    "All good 💚 Let’s continue.\n\nAnd anytime after your journey is complete, just say *\"create an exercise plan\"* and I’ll build one for you 🏋️✨",
                )
                _store_system_message(
                    state,
                    "All good 💚 Let’s continue.\n\nAnd anytime after your journey is complete, just say *\"create an exercise plan\"* and I’ll build one for you 🏋️✨",
                )
                logger.info(
                    "➡️  ROUTER: Exercise plan declined - routing to required profiling"
                )
                if (
                    state.get("profiling_collected")
                    or _has_completed_weight(state)
                    or _has_any_profiling_data(state)
                ):
                    logger.info(
                        "[EARLY PROFILING] Exercise plan NO - profiling exists → transition_to_snap"
                    )
                    return NODE_TRANSITION_TO_SNAP
                else:
                    logger.info(
                        "[EARLY PROFILING] Exercise plan NO - no profiling data → collect_age"
                    )
                    return NODE_COLLECT_AGE

            # Option 4: Invalid Input (Catch-all)
            else:
                send_whatsapp_message(
                    state["user_id"],
                    "I didn't quite catch that. Please let me know nicely using the buttons below! 👇",
                )
                return NODE_ASK_EXERCISE_PREFERENCE

        # NEW: Handle voice agent promotion response for exercise
        elif last_q == "voice_agent_promotion_exercise":
            # VOICE CALL: User is already on the call — start the exercise journey
            if state.get("interaction_mode") == "voice":
                state["voice_agent_accepted"] = True
                if (
                    state.get("profiling_collected")
                    or state.get("journey_restart_mode")
                    or _has_completed_weight(state)
                ):
                    return NODE_TRANSITION_TO_EXERCISE
                if not (state.get("age") or "").strip():
                    return NODE_COLLECT_AGE
                if not (state.get("height") or "").strip():
                    return "collect_height"
                if not (state.get("weight") or "").strip():
                    return "collect_weight"
                return "calculate_bmi"

            msg_raw = state.get(KEY_USER_MSG, "") or ""
            msg = msg_raw.lower()
            msg_id = msg_raw

            # User chose chat
            if msg_id == "create_here_chat" or "chat" in msg:
                state["voice_agent_choice"] = "chat"
                state["voice_agent_declined"] = True
                
                # Check profiling logic directly to transition to exercise chat flow
                if (
                    state.get("profiling_collected")
                    or state.get("journey_restart_mode")
                    or _has_completed_weight(state)
                ):
                    return NODE_TRANSITION_TO_EXERCISE
                else:
                    if not (state.get("age") or "").strip():
                        return NODE_COLLECT_AGE
                    elif not (state.get("height") or "").strip():
                        return "collect_height"
                    elif not (state.get("weight") or "").strip():
                        return "collect_weight"
                    else:
                        return "calculate_bmi"
            
            # User chose voice agent
            elif msg_id == "try_voice_agent" or "voice" in msg:
                # The button directly links to the wa.me Call URL now. We just end the graph here.
                return "__end__"
            
            # Unclear response -> Clarify
            else:
                return "voice_agent_promotion_exercise"  # Re-ask

        # 2. Linear Map Lookup
        elif last_q in AMS_MEAL_FLOW_MAP:
            return AMS_MEAL_FLOW_MAP[last_q]

    # EXERCISE PLANNER AGENT FLOW - Route based on last_question
    elif state.get(KEY_CURRENT_AGENT) == AGENT_EXERCISE:
        last_q = state.get(KEY_LAST_QUESTION)

        # 1. Complex Conditionals
        if last_q == "day1_complete":
            # Check if pending_node is set (for single-call generation)
            pending = state.get(KEY_PENDING_NODE)
            if pending == "generate_all_remaining_exercise_days":
                return "generate_all_remaining_exercise_days"
            # Fallback to old day-by-day approach
            return "generate_day2_plan"

        # 2. Linear Map Lookup
        elif last_q in AMS_EXERCISE_FLOW_MAP:
            return AMS_EXERCISE_FLOW_MAP[last_q]

    # Post-plan handling - only if both plans are sent or we're in post-plan state
    elif (state.get("meal_plan_sent") and state.get("exercise_plan_sent")) or state.get(
        KEY_LAST_QUESTION
    ) == "post_plan":
        return NODE_POST_PLAN_QNA

    # Resumption handler for voice agent instructions
    elif state.get(KEY_LAST_QUESTION) == "voice_agent_instructions_provided":
        logger.info("📦 ROUTER: Resuming from voice agent instructions - finding next node")
        return _get_resume_node_ams(state)

    # Fallback
    return NODE_VERIFY_USER


def route_after_collect_weight(state: State) -> str:
    """When weight is valid, chain to calculate_bmi so BMI runs immediately (no extra user message)."""
    import re
    w = str(state.get("weight", "") or "").lower()
    has_digits = bool(re.search(r"\d", w))
    has_units = any(kw in w for kw in ("kg", "k g", "kgs", "kilogram", "lb", "lbs", "pound"))
    if state.get(KEY_LAST_QUESTION) == "weight" and (has_digits or has_units):
        return "calculate_bmi"
    return "__end__"


def route_after_bmi_calculation(state: State) -> str:
    """
    Route after BMI calculation based on context.
    Context is determined by where profiling was collected.
    """
    # Mark BMI as calculated
    state["bmi_calculated"] = True

    # DEBUG: Log state to understand what's available
    logger.info(
        "[EARLY PROFILING DEBUG] After BMI - current_agent=%s, profiling_collected_in_meal=%s, profiling_collected_in_exercise=%s, meal_plan_sent=%s, exercise_plan_sent=%s",
        state.get(KEY_CURRENT_AGENT),
        state.get("profiling_collected_in_meal"),
        state.get("profiling_collected_in_exercise"),
        state.get("meal_plan_sent"),
        state.get("exercise_plan_sent"),
    )

    # NEW: Determine context from tracking flags OR current_agent (more reliable)

    # If profiling was collected during meal flow (EARLY)
    # Check both the flag AND current_agent as fallback
    # CRITICAL: Also check wants_meal_plan to avoid routing to health_conditions when user said NO to meal plan
    # Voice: voice_agent_context=meal_planning implies meal journey (set in _build_initial_state)
    is_meal_flow = (
        state.get("profiling_collected_in_meal")
        or (
            state.get(KEY_CURRENT_AGENT) == AGENT_MEAL
            and state.get("wants_meal_plan")
            and not state.get("meal_plan_sent")
        )
        or (
            state.get("interaction_mode") == "voice"
            and state.get("voice_agent_context") == "meal_planning"
            and not state.get("meal_plan_sent")
        )
    )
    if is_meal_flow:
        # Route to health conditions (next step in meal flow)
        logger.info(
            "[EARLY PROFILING] BMI calculated - profiling was in MEAL flow (flag=%s, agent=%s, wants_meal=%s) → collect_health_conditions",
            state.get("profiling_collected_in_meal"),
            state.get(KEY_CURRENT_AGENT),
            state.get("wants_meal_plan"),
        )
        return "collect_health_conditions"

    # If profiling was collected during exercise flow (EARLY)
    # Check both the flag AND current_agent as fallback
    elif state.get("profiling_collected_in_exercise") or (
        state.get(KEY_CURRENT_AGENT) == AGENT_EXERCISE
        and not state.get("exercise_plan_sent")
    ):
        # Route to transition_to_exercise (AMS-specific transition node)
        # AMS: Go to transition node first, then to first exercise question
        logger.info(
            "[EARLY PROFILING] BMI calculated - profiling was in EXERCISE flow (flag=%s, agent=%s) → transition_to_exercise",
            state.get("profiling_collected_in_exercise"),
            state.get(KEY_CURRENT_AGENT),
        )
        return NODE_TRANSITION_TO_EXERCISE

    # Otherwise, end-of-journey profiling (fallback scenario - CASE C: NO to both plans)
    else:
        logger.info(
            "[EARLY PROFILING] BMI calculated - FALLBACK flow (agent=%s, wants_meal=%s, wants_exercise=%s) → transition_to_snap",
            state.get(KEY_CURRENT_AGENT),
            state.get("wants_meal_plan"),
            state.get("wants_exercise_plan"),
        )
        return NODE_TRANSITION_TO_SNAP


def resume_router(state: State) -> str:
    """Route back to the interrupted node after health Q&A or product Q&A."""
    pending = state.get(KEY_PENDING_NODE)
    logger.info("RESUME ROUTER - Pending node: %s", pending)

    # If both plans are completed, clear pending_node and go to post-plan Q&A
    # BUT NOT if we're in journey_restart_mode (recreating plan)
    if (
        state.get("meal_plan_sent")
        and state.get("exercise_plan_sent")
        and not state.get("journey_restart_mode")
    ):
        logger.info("RESUME ROUTER - Both plans completed, routing to post_plan_qna")
        return NODE_POST_PLAN_QNA

    # If we have a pending node and we're still in plan generation, resume from there
    # Allow resumption if exercise plan NOT sent OR if we are restarting (recreating)
    if pending and (
        not state.get("exercise_plan_sent") or state.get("journey_restart_mode")
    ):
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
        logger.info(
            "RESUME ROUTER - Returning to: %s (original pending: %s)",
            mapped_pending,
            pending,
        )
        return mapped_pending

    # If we don't have a pending node, go to ask_meal_plan_preference as a fallback
    if not pending:
        logger.info(
            "RESUME ROUTER - No pending node, defaulting to ask_meal_plan_preference"
        )
        return NODE_ASK_MEAL_PREFERENCE

    return NODE_POST_PLAN_QNA
