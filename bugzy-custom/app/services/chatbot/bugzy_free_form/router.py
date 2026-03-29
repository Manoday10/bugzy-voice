"""
Router for the bugzy_free_form agent.

Ultra-simple: verify_user → post_plan_qna; SNAP flow → snap_image_analysis → post_plan_qna.
"""

import logging
from app.services.chatbot.bugzy_free_form.state import State
from app.services.chatbot.router_constants import (
    NODE_VERIFY_USER,
    NODE_POST_PLAN_QNA,
    NODE_SNAP_IMAGE_ANALYSIS,
    KEY_LAST_QUESTION,
    KEY_USER_MSG,
    KEY_USER_NAME,
    STATE_VERIFIED,
    KEY_AGE,
    KEY_HEIGHT,
    KEY_BMI,
)

logger = logging.getLogger(__name__)


def _is_greeting_or_new(text: str, state: State) -> bool:
    """True if first-time user or greeting (no user_name yet or short hi/hello)."""
    if not text:
        return False
    msg = (text or "").strip().lower()
    greetings = {
        "hi", "hello", "hey", "heyy", "heyyy", "hiya", "yo", "sup", "namaste",
        "good morning", "gm", "good afternoon", "good evening", "ge",
        "morning", "afternoon", "evening", "hola", "hii", "helloo",
    }
    if msg in greetings:
        return True
    tokens = msg.split()
    if tokens and tokens[0] in greetings and len(tokens) <= 3:
        return True
    # No user_name yet => treat as first message (verify_user will run)
    if not (state.get(KEY_USER_NAME) or "").strip():
        return True
    return False


def router(state: State) -> str:
    """
    Route to one of: verify_user, post_plan_qna, transition_to_snap, snap_image_analysis.

    1. last_question == "transitioning_to_snap" → snap_image_analysis
    2. Already verified (user_name set) OR migrated user (has profile data) → post_plan_qna
    3. First-time / no user_name and no profile → verify_user
    4. Else → post_plan_qna
    """
    last_question = (state.get(KEY_LAST_QUESTION) or "").strip()
    user_msg = (state.get(KEY_USER_MSG) or "").strip()
    user_name = (state.get(KEY_USER_NAME) or "").strip()

    # SNAP: user sent image after transition_to_snap
    if last_question == "transitioning_to_snap":
        logger.info("ROUTER free_form: transitioning_to_snap → snap_image_analysis")
        return NODE_SNAP_IMAGE_ANALYSIS

    # Already verified: user has name and we've run verify_user → stay in QnA
    if user_name and last_question == STATE_VERIFIED:
        logger.info("ROUTER free_form: already verified → post_plan_qna")
        return NODE_POST_PLAN_QNA
    
    # MIGRATED USER: Has profile data from AMS/Gut Cleanse → skip verification
    # Check for any profile fields that indicate the user has completed profiling
    profile_indicators = [
        state.get(KEY_AGE), state.get(KEY_HEIGHT), state.get(KEY_BMI),
        state.get("diet_preference"), state.get("fitness_level"),
        state.get("dietary_preference")  # Gut Cleanse field
    ]
    has_profile_data = any(profile_indicators)
    
    if user_name and has_profile_data:
        logger.info("ROUTER free_form: migrated user (has profile) → post_plan_qna")
        return NODE_POST_PLAN_QNA

    # First-time: no user_name yet (or greeting with no session) → verify_user
    if not user_name or _is_greeting_or_new(user_msg, state):
        logger.info("ROUTER free_form: greeting/new → verify_user")
        return NODE_VERIFY_USER

    # Default: post_plan_qna
    logger.info("ROUTER free_form: default → post_plan_qna")
    return NODE_POST_PLAN_QNA
