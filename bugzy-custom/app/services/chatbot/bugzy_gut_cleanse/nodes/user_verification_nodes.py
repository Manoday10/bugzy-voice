"""
User verification and basic info collection nodes.

This module contains nodes for user verification, collecting basic information
(age, height, weight), BMI calculation, and SNAP image analysis transitions.
"""

import time
import logging
from typing import Optional

from app.services.chatbot.bugzy_gut_cleanse.state import State
from app.services.chatbot.bugzy_gut_cleanse.intent_helpers import (
    _is_affirmative,
    _is_negative_or_defer,
)
from app.services.chatbot.bugzy_gut_cleanse.voice_message_utils import (
    gut_age_prompt_already_spoken,
    gut_last_assistant_content,
)
from app.services.whatsapp.utils import (
    _store_question_in_history,
    _update_last_answer_in_history,
    _store_system_message,
    llm,
)
from app.services.whatsapp.client import (
    send_whatsapp_message,
    _send_whatsapp_buttons,
    _send_whatsapp_list,
)
from app.services.whatsapp.messages import remove_markdown
from app.services.crm.sessions import (
    fetch_user_details,
    save_session_to_file,
    fetch_order_details,
    extract_order_details,
)
from app.services.prompts.gut_cleanse.validation_config import VALIDATION_RULES
from app.services.chatbot.bugzy_gut_cleanse.constants import (
    TRANSITION_TO_GUT_COACH_MESSAGES,
    GUT_CLEANSE_KEYS_TO_CLEAR,
    GUT_CRM_GREETING_1,
    GUT_CRM_GREETING_2,
    GUT_GENERIC_GREETING_1,
    GUT_GENERIC_GREETING_2,
    HEALTH_SAFETY_LIST_ITEMS,
    DETOX_EXPERIENCE_MAP,
    DETOX_REASON_MAP,
    HEALTH_BLOCK_IDS,
    HEALTH_STATUS_KEYWORDS,
    HEALTH_SAFETY_WARNINGS,
    HEALTH_SAFETY_CONDITION_MAP,
    resolve_health_safety_status,
)

logger = logging.getLogger(__name__)


def _gut_voice_owns_turn(state: State) -> bool:
    """True when voice call/modality should receive questions — skip duplicate WhatsApp UI."""
    return state.get("interaction_mode") == "voice" or bool(state.get("voice_call_active"))


def _voice_parse_age_eligibility(user_msg: str) -> Optional[bool]:
    """Parse 18+ intent from voice/STT. True=18+, False=under 18, None=unclear."""
    raw = (user_msg or "").strip()
    if not raw:
        return None
    msg = raw.lower()
    if raw == "age_eligible_yes" or "✅" in raw:
        return True
    if raw == "age_eligible_no" or "❌" in raw:
        return False
    under_phrases = ("under 18", "underage", "i'm a minor", "im a minor", "not eighteen", "below 18")
    if any(p in msg for p in under_phrases):
        return False
    if _is_affirmative(raw):
        return True
    if _is_negative_or_defer(raw) and ("18" in msg or any(p in msg for p in under_phrases)):
        return False
    if "18" in msg and any(w in msg for w in ("over", "above", "turned 18", "i am 18", "i'm 18")):
        return True
    return None


from app.services.chatbot.bugzy_shared.validation import (
    validate_input as shared_validate_input,
    handle_validated_input as shared_handle_validated_input,
)
from app.services.prompts.gut_cleanse.validation_config import VALIDATION_RULES


def validate_input(user_input: str, expected_field: str) -> tuple[bool, str]:
    """Validate input using shared logic and Gut Cleanse rules."""
    return shared_validate_input(user_input, expected_field, VALIDATION_RULES)


def handle_validated_input(
    state: State, expected_field: str, max_attempts: int = 3
) -> str:
    """Handle validated input using shared logic and Gut Cleanse rules."""
    return shared_handle_validated_input(
        state, expected_field, VALIDATION_RULES, max_attempts=max_attempts
    )


# --- SHARED NODES ---
def verify_user_node(state: State) -> State:
    """Node: Verify user by phone number against CRM."""
    phone = state["user_id"]
    # Reset all profiling and plan data to ensure a fresh start
    # This prevents "ghost data" from previous sessions persisting across restarts
    for key in GUT_CLEANSE_KEYS_TO_CLEAR:
        if key in state:
            state[key] = None

    # Always reset agent to meal initially
    state["current_agent"] = "meal"

    # Store the result in state
    result = fetch_user_details(phone)

    if "error" not in result and "message" not in result:
        state["phone_number"] = result.get("phone_number")
        state["user_name"] = result.get("name")
        state["crm_user_data"] = result.get("full_data")

        # --- NEW: Fetch Latest Order Details ---
        try:
            order_response = fetch_order_details(phone)
            order_info = extract_order_details(order_response)

            # Store order info in state for context building
            state["user_order"] = order_info.get("latest_order_name")
            state["user_order_date"] = order_info.get("latest_order_date")
            state["has_orders"] = order_info.get("has_orders", False)

            if state["has_orders"]:
                logger.info(
                    "📦 Fetched latest order for %s: %s (%s)",
                    state["user_name"],
                    state["user_order"],
                    state["user_order_date"],
                )
            else:
                logger.info("📦 No recent orders found for %s", state["user_name"])

        except Exception as e:
            logger.error("⚠️ Error fetching order details: %s", e)
            # Ensure we don't crash, just proceed without order info
            state["user_order"] = None
            state["user_order_date"] = None
            state["has_orders"] = False
        # Send greeting in 3 separate messages
        greeting_msg1 = GUT_CRM_GREETING_1.format(user_name=state["user_name"])
        send_whatsapp_message(state["user_id"], greeting_msg1)

        greeting_msg2 = GUT_CRM_GREETING_2
        send_whatsapp_message(state["user_id"], greeting_msg2)

        # Store all greeting messages as system messages
        _store_system_message(state, greeting_msg1)
        _store_system_message(state, greeting_msg2)
    else:
        # Send greeting in 3 separate messages for non-CRM users
        greeting_msg1 = GUT_GENERIC_GREETING_1
        send_whatsapp_message(state["user_id"], greeting_msg1)

        greeting_msg2 = GUT_GENERIC_GREETING_2
        send_whatsapp_message(state["user_id"], greeting_msg2)

        # Store all greeting messages as system messages
        _store_system_message(state, greeting_msg1)
        _store_system_message(state, greeting_msg2)

    state["last_question"] = "verified"
    state["current_agent"] = "meal"  # Start with meal planner

    # Save session to file after verification
    save_session_to_file(state["user_id"], state)

    return state


def collect_age_eligibility(state: State) -> State:
    """Node: Collect age eligibility (18+ check)."""
    # Check if we're resuming from QnA or Snap
    last_q = state.get("last_question")
    is_resuming = last_q in [
        "resuming_from_health_qna",
        "resuming_from_product_qna",
        "resuming_from_snap",
    ]

    # Ensure plan context is persisted when coming from preference questions (skip if resuming)
    if not is_resuming:
        msg = (state.get("user_msg") or "").lower()
        is_yes = any(
            keyword in msg for keyword in ["yes", "create", "plan", "ok", "sure"]
        )
        if state.get("last_question") == "ask_meal_plan_preference" and is_yes:
            state["wants_meal_plan"] = True
            state["current_agent"] = "meal"

    # Check if age eligibility already exists (session resume) - BUT NOT if resuming from QnA
    if state.get("age_eligible") is not None and not is_resuming:
        logger.info(
            f"Age eligibility already collected for user {state['user_id']}: {state['age_eligible']}"
        )
        # IMPORTANT: Do NOT override last_question here.
        # Overwriting last_question to "age_eligibility" causes the router to loop
        # back to question 1 on the next turn, even though the journey is mid-flow.
        # Just return state unchanged so the existing last_question is preserved.
        return state

    # Skip intro when re-asking after invalid input (router already sent "I didn't quite catch that...")
    reasking = state.get("age_eligibility_question_sent") is True

    # Voice + LiveKit pre-seed: parse reply if the 18+ prompt was already spoken,
    # even when last_question in DB is stale (age_eligibility / meal pref / etc.).
    is_voice = _gut_voice_owns_turn(state)
    user_msg_raw = (state.get("user_msg") or "").strip()
    from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS

    voiced_age_q = VOICE_QUESTIONS.get("age_eligibility", "Are you 18 years or older?")
    msgs_list = list(state.get("messages", []))
    already_heard_age = gut_age_prompt_already_spoken(msgs_list, voiced_age_q)
    from_promotion = last_q == "voice_agent_promotion_meal"
    last_asst_snip = (gut_last_assistant_content(msgs_list) or "")[:120]

    logger.info(
        "[voice/age_eligibility] user=%s last_q=%s already_heard=%s from_promo=%s msg_len=%d last_asst=%r",
        state.get("user_id"),
        last_q,
        already_heard_age,
        from_promotion,
        len(user_msg_raw),
        last_asst_snip,
    )

    if is_voice and user_msg_raw and (from_promotion or already_heard_age):
        parsed = _voice_parse_age_eligibility(user_msg_raw)
        logger.info("[voice/age_eligibility] parse_result=%s user_reply=%r", parsed, user_msg_raw[:80])
        if parsed is True:
            state["age_eligible"] = True
            _update_last_answer_in_history(state, "Yes, I'm 18+")
            gender_q = VOICE_QUESTIONS.get(
                "gender", "What's your gender? Male, female, or prefer not to say."
            )
            msgs = msgs_list + [{"role": "assistant", "content": gender_q}]
            _store_question_in_history(state, gender_q, "gender")
            return state | {
                "last_question": "gender",
                "pending_node": "collect_gender",
                "age_eligibility_question_sent": True,
                "messages": msgs,
            }
        if parsed is False:
            state["age_eligible"] = False
            _update_last_answer_in_history(state, "No, I'm under 18")
            warn = (
                "The Gut Cleanse is not recommended for anyone under 18. "
                "Your gut is still developing and the program may be too strong. "
            )
            vq = VOICE_QUESTIONS.get(
                "age_warning_confirmation",
                "Do you want to continue with general wellness tips instead?",
            )
            combined = f"{warn}{vq}"
            msgs = msgs_list + [{"role": "assistant", "content": combined}]
            _store_question_in_history(state, vq, "age_warning_confirmation")
            return state | {
                "last_question": "age_warning_confirmation",
                "pending_node": "collect_age_warning_confirmation",
                "age_eligibility_warning_sent": True,
                "age_eligibility_question_sent": True,
                "messages": msgs,
            }
        retry_msg = (
            "I didn't quite catch that. Are you 18 or older? Please say yes or no."
        )
        msgs = msgs_list + [{"role": "assistant", "content": retry_msg}]
        _store_question_in_history(state, voiced_age_q, "age_eligibility")
        return state | {
            "last_question": "age_eligibility",
            "pending_node": "collect_age_eligibility",
            "age_eligibility_question_sent": True,
            "messages": msgs,
        }

    # Context-aware intro message (skip if resuming from QnA or re-asking)
    intro_message = ""
    if not is_resuming and not reasking:
        if state.get("wants_meal_plan") and not state.get("meal_plan_sent"):
            intro_message = "Just a few quick questions so I can build a detox-friendly meal plan that actually works for your body 🌿"
        else:
            intro_message = "Let me ask a few basic questions so I can assist you better whenever you need! This will take only a moment!"

    if _gut_voice_owns_turn(state):
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS

        question = VOICE_QUESTIONS.get("age_eligibility", "Are you 18 years or older?")
        content = f"{intro_message} {question}".strip() if intro_message else question
        if reasking:
            content = "I didn't quite catch that. Are you 18 or older? Say yes or no."
        elif gut_age_prompt_already_spoken(list(state.get("messages", [])), question):
            logger.info(
                "collect_age_eligibility: 18+ prompt already in messages — skip duplicate append"
            )
        else:
            state.setdefault("messages", []).append({"role": "assistant", "content": content})
    else:
        if not is_resuming:
            send_whatsapp_message(state["user_id"], intro_message)
            _store_system_message(state, intro_message)
            if state.get("interaction_mode") != "voice":
                import time
                time.sleep(1)
        question = "🌸 Are you 18 years or older?"
        _send_whatsapp_buttons(
            state["user_id"],
            question,
            [
                {"type": "reply", "reply": {"id": "age_eligible_yes", "title": "Yes, I'm 18+ ✅"}},
                {"type": "reply", "reply": {"id": "age_eligible_no", "title": "No, I'm under 18 ❌"}},
            ],
        )

    _store_question_in_history(state, question, "age_eligibility")

    state["last_question"] = "age_eligibility"
    state["pending_node"] = "collect_age_eligibility"
    state["age_eligibility_question_sent"] = True
    return state


def collect_age_warning_confirmation(state: State) -> State:
    """Node: Ask user to confirm they want to proceed after under-18 age warning."""
    # Check if already confirmed (session resume)
    if state.get("age_warning_confirmed") is not None:
        logger.info(
            f"Age warning confirmation already collected for user {state['user_id']}"
        )
        state["last_question"] = "age_warning_confirmation"
        return state

    question = "Keeping this in mind, would you still like to proceed?"
    if _gut_voice_owns_turn(state):
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        vq = VOICE_QUESTIONS.get("age_warning_confirmation", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": vq})
        question = vq
    else:
        _send_whatsapp_buttons(
            state["user_id"],
            question,
            [
                {
                    "type": "reply",
                    "reply": {"id": "age_proceed_yes", "title": "Proceed anyway"},
                },
            ],
        )

    # Store the question in conversation history
    _store_question_in_history(state, question, "age_warning_confirmation")

    state["last_question"] = "age_warning_confirmation"
    state["pending_node"] = "collect_age_warning_confirmation"
    return state


def collect_gender(state: State) -> State:
    """Node: Collect gender."""
    # Check if we're resuming from QnA
    last_q = state.get("last_question")
    is_resuming = last_q in [
        "resuming_from_health_qna",
        "resuming_from_product_qna",
        "resuming_from_snap",
    ]

    # Check if we're coming from age_eligibility (skip if resuming)
    if last_q == "age_eligibility" and not is_resuming:
        # Capture the age_eligible response here, since router side-effects might be lost
        msg = (state.get("user_msg") or "").lower()
        msg_id = state.get("user_msg", "")

        # Logic matches what was in router, but now safely inside a node
        if (
            msg_id == "age_eligible_yes"
            or "yes" in msg
            or "18" in msg
            or "✅" in state.get("user_msg", "")
        ):
            state["age_eligible"] = True
            _update_last_answer_in_history(state, "Yes, I'm 18+")
        elif (
            msg_id == "age_eligible_no"
            or ("no" in msg and ("under" in msg or "18" in msg))
            or "❌" in state.get("user_msg", "")
        ):
            state["age_eligible"] = False
            _update_last_answer_in_history(state, "No, I'm under 18")

    # Check if gender already exists (session resume) - BUT NOT if resuming from QnA
    if state.get("gender") and not is_resuming:
        logger.info(
            f"Gender already collected for user {state['user_id']}: {state['gender']}"
        )
        # IMPORTANT: Do NOT override last_question here - it resets routing back to question 2.
        return state

    # Adapt question tone based on context
    is_under_18 = state.get("age_eligible") is False

    if is_under_18:
        question = "I'd still like to learn a bit about you. What's your gender?"
    else:
        question = "✨ Perfect! What's your gender?"

    if _gut_voice_owns_turn(state):
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("gender", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_buttons(
            state["user_id"],
            question,
            [
                {"type": "reply", "reply": {"id": "gender_male", "title": "Male"}},
                {"type": "reply", "reply": {"id": "gender_female", "title": "Female"}},
                {
                    "type": "reply",
                    "reply": {
                        "id": "gender_prefer_not_to_say",
                        "title": "Prefer not to say",
                    },
                },
            ],
        )

    # Store the question in conversation history
    _store_question_in_history(state, question, "gender")

    state["last_question"] = "gender"
    state["pending_node"] = "collect_gender"
    return state


def collect_pregnancy_check(state: State) -> State:
    """Node: Collect pregnancy/breastfeeding status (only for females).

    Similar to collect_medications - this node only asks the question.
    The router handles the conditional logic (only routes here if gender is female).
    """
    # Check if we're resuming from QnA
    last_q = state.get("last_question")
    is_resuming = last_q in [
        "resuming_from_health_qna",
        "resuming_from_product_qna",
        "resuming_from_snap",
    ]

    # Capture gender if coming from collect_gender (skip if resuming)
    if last_q == "gender" and not is_resuming:
        msg = (state.get("user_msg") or "").lower()
        msg_id = state.get("user_msg", "")

        # Logic to capture gender
        if msg_id == "gender_female" or msg == "female":
            state["gender"] = "female"
            _update_last_answer_in_history(state, "Female")
        # Note: We only expect females here, but valid to check

    # Check if already collected (session resume) - BUT NOT if resuming from QnA
    if (
        state.get("is_pregnant") is not None
        or state.get("is_breastfeeding") is not None
    ) and not is_resuming:
        logger.info(f"Pregnancy check already collected for user {state['user_id']}")
        # IMPORTANT: Do NOT override last_question here - it resets routing to pregnancy question.
        return state

    # Store the gender from user_msg and update last answer (skip if resuming from QnA)
    # The router already stored gender, but we update the answer in history here
    if state.get("user_msg") and not is_resuming:
        _update_last_answer_in_history(state, state["user_msg"])

    question = "🤰 Important safety check\nAre you currently pregnant or breastfeeding?"

    if _gut_voice_owns_turn(state):
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("pregnancy_check", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_buttons(
            state["user_id"],
            question,
            [
                {"type": "reply", "reply": {"id": "pregnancy_no", "title": "No ✅"}},
                {
                    "type": "reply",
                    "reply": {"id": "pregnancy_yes_pregnant", "title": "Yes, pregnant 🤰"},
                },
                {
                    "type": "reply",
                    "reply": {
                        "id": "pregnancy_yes_breastfeeding",
                        "title": "Yes, breastfeeding 🤱",
                    },
                },
            ],
        )

    # Store the question in conversation history
    _store_question_in_history(state, question, "pregnancy_check")

    state["last_question"] = "pregnancy_check"
    state["pending_node"] = "collect_pregnancy_check"
    return state


def collect_pregnancy_warning_confirmation(state: State) -> State:
    """Node: Ask user to confirm they want to proceed after pregnancy/breastfeeding warning."""
    # Check if already confirmed (session resume)
    if state.get("pregnancy_warning_confirmed") is not None:
        logger.info(
            f"Pregnancy warning confirmation already collected for user {state['user_id']}"
        )
        state["last_question"] = "pregnancy_warning_confirmation"
        return state

    # Determine the next message based on whether user wants meal plan or not
    wants_meal_plan = state.get("wants_meal_plan", False)

    if wants_meal_plan:
        next_step_message = "Perfect! Let's move on to your meal plan 💚"
    else:
        # User doesn't want meal plan, so next step is SNAP
        next_step_message = f"💪 Now let's move on to your SNAP analysis {state.get('user_name', 'there')}!"

    question = "Keeping this in mind, would you still like to proceed?"
    if _gut_voice_owns_turn(state):
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_buttons(
            state["user_id"],
            question,
            [
                {
                    "type": "reply",
                    "reply": {"id": "pregnancy_proceed_yes", "title": "Proceed anyway"},
                },
            ],
        )

    # Store the question in conversation history
    _store_question_in_history(state, question, "pregnancy_warning_confirmation")

    state["last_question"] = "pregnancy_warning_confirmation"
    state["pending_node"] = "collect_pregnancy_warning_confirmation"
    # Store the next step message for later use
    state["pregnancy_confirmation_next_message"] = next_step_message
    return state


def transition_to_snap(state: State) -> State:
    """Node: Automatic transition from meal plan to SNAP analysis."""
    # Capture detox experience/reason if coming from profiling (no meal plan path)
    last_q = state.get("last_question")
    msg = (state.get("user_msg") or "").lower()
    msg_id = state.get("user_msg", "")

    if last_q == "detox_experience":
        for condition_fn, value, label in DETOX_EXPERIENCE_MAP:
            if condition_fn(msg, msg_id):
                state["detox_experience"] = value
                _update_last_answer_in_history(state, label)
                break
        # Mark profiling as explicitly collected since we finished the flow
        state["profiling_collected"] = True

    elif last_q == "detox_recent_reason":
        for condition_fn, value, label in DETOX_REASON_MAP:
            if condition_fn(msg, msg_id):
                state["detox_recent_reason"] = value
                _update_last_answer_in_history(state, label)
                break
        # Mark profiling as explicitly collected since we finished the flow
        state["profiling_collected"] = True

    user_name = state.get("user_name", "there")
    msg1 = f"Now let's move on to your SNAP analysis {user_name}!"
    msg2 = "Please share an image of your meal, fridge ingredients, or food item, and I'll analyze it for you!"
    
    # Check if voice mode owns the turn
    from app.services.chatbot.bugzy_gut_cleanse.voice_message_utils import _gut_voice_owns_turn
    if _gut_voice_owns_turn(state):
        state.setdefault("messages", []).append({"role": "assistant", "content": f"{msg1} {msg2}"})
    else:
        send_whatsapp_message(
            state["user_id"], f"\n💪 {msg1}"
        )
        import time
        time.sleep(1.5)
        send_whatsapp_message(
            state["user_id"],
            f"📸 SNAP Image Analysis\n\n{msg2}",
        )
    
    state["current_agent"] = "snap"
    state["last_question"] = "transitioning_to_snap"
    return state


def snap_image_analysis(state: State) -> State:
    """Node: SNAP - Image analysis tool for food/meal analysis."""
    # Import here to avoid circular imports
    from app.services.chatbot.bugzy_gut_cleanse.router import (
        is_meal_edit_request,
        extract_day_number,
    )
    from app.services.chatbot.bugzy_gut_cleanse.nodes.qna_nodes import (
        handle_meal_edit_request,
    )

    # Check if we already have an analysis result (from API processing)
    if state.get("snap_analysis_sent") and state.get("snap_analysis_result"):
        # Analysis already done in the API layer, just return the state
        logger.info("Image already analyzed in API layer, skipping analysis")
        state["last_question"] = "snap_complete"
        return state

    # CHECK FOR PLAN EDIT REQUESTS (before SNAP processing)
    # This allows users to edit their meal plans during SNAP analysis phase
    user_msg = state.get("user_msg", "")
    if user_msg and user_msg.strip():
        if is_meal_edit_request(user_msg):
            logger.info("SNAP PHASE - MEAL EDIT REQUEST DETECTED: %s", user_msg)
            day_num = extract_day_number(user_msg)
            logger.info("DAY NUMBER EXTRACTED: %s", day_num)
            return handle_meal_edit_request(state, day_num)

        # NEW: Handle general text/questions (Skip SNAP)
        # If user sends text that isn't a plan edit and isn't an image (no snap_analysis_result),
        # assume they want to ask a question or skip SNAP.
        if not state.get("snap_analysis_result"):
            logger.info("Text input detected in SNAP (skipping analysis): %s", user_msg)

            # Manually set state to post_plan_qna mode (skipping SNAP transition message)
            # This ensures we don't send "All set..." if user is just asking a question.
            state["current_agent"] = "post_plan_qna"
            state["last_question"] = "post_plan_qna"

            # Immediately answer the question via post_plan_qna_node
            # This ensures "what is X?" is answered immediately.
            # IMPORTANT: We return 'state' here and let the agent.py conditional edge
            # route us to 'post_plan_qna'. We do NOT call post_plan_qna_node(state) directly
            # because that causes double execution (once here, once by the graph).
            return state

    # If no analysis has been done yet, send the prompt STRICTLY if not just transitioned
    if state.get("last_question") != "transitioning_to_snap":
        send_whatsapp_message(
            state["user_id"],
            "📸 SNAP Image Analysis\n\nPlease share an image of your meal, fridge ingredients, or food item, and I'll analyze it for you!",
        )

    # Note: The actual image analysis happens in the API layer when the user sends an image
    # This hardcoded analysis will only be used if the API layer fails to process the image

    # Simulate analysis result for fallback
    analysis_result = """📸 Image Analysis Results:

Based on the image provided:

🔍 **Detected Items:**
- Mixed vegetables
- Protein source
- Complex carbohydrates

📊 **Nutritional Breakdown (Estimated):**
- Calories: ~400-500 kcal
- Protein: ~25-30g
- Carbs: ~45-50g
- Fats: ~15-20g
- Fiber: ~8-10g

✅ **Health Assessment:**
This meal appears to be well-balanced with good portions of vegetables, protein, and complex carbs. Great choice for maintaining energy levels!

💡 **Suggestions:**
- Consider adding more leafy greens for additional micronutrients
- Ensure adequate hydration with this meal
- This meal aligns well with your fitness goals!"""

    # Only send the hardcoded analysis if we don't already have one from the API
    # AND if we haven't transitioned (which happens above for text)
    if not state.get("snap_analysis_result") and not (user_msg and user_msg.strip()):
        # Convert markdown to WhatsApp format before sending
        cleaned_analysis = remove_markdown(analysis_result)
        send_whatsapp_message(state["user_id"], cleaned_analysis)
        state["snap_analysis_result"] = cleaned_analysis
        state["snap_analysis_sent"] = True

    state["last_question"] = "snap_complete"

    return state


def transition_to_gut_coach(state: State) -> State:
    """Node: Automatic transition from SNAP to gut coach and post-plan Q&A."""
    user_name = state.get("user_name", "there")
    message = TRANSITION_TO_GUT_COACH_MESSAGES[-1]["template"].format(
        user_name=user_name
    )

    for msg_config in TRANSITION_TO_GUT_COACH_MESSAGES:
        if msg_config["condition"](state):
            message = msg_config["template"].format(user_name=user_name)
            break

    send_whatsapp_message(state["user_id"], message)
    state["current_agent"] = "post_plan_qna"
    state["last_question"] = "post_plan_qna"
    return state


def collect_health_safety_screening(state: State) -> State:
    """Node: Collect health safety screening status."""

    # Capture prior state based on path (transferred from removed collect_health_conditions_overview)
    last_q = state.get("last_question")
    msg = (state.get("user_msg") or "").lower()
    msg_id = state.get("user_msg", "")

    # Check if we're resuming from QnA (don't process user_msg as answer)
    is_resuming = last_q in [
        "resuming_from_health_qna",
        "resuming_from_product_qna",
        "resuming_from_snap",
    ]

    if last_q == "gender" and not is_resuming:
        # Coming from gender (Male or Prefer Not to Say)
        if msg_id == "gender_male" or msg == "male":
            state["gender"] = "male"
            _update_last_answer_in_history(state, "Male")
            confirmation = "Got it 💚 You may continue."
            if _gut_voice_owns_turn(state):
                state.setdefault("messages", []).append({"role": "assistant", "content": confirmation})
            else:
                send_whatsapp_message(state["user_id"], confirmation)
        elif msg_id == "gender_prefer_not_to_say" or "prefer not" in msg:
            state["gender"] = "prefer_not_to_say"
            _update_last_answer_in_history(state, "Prefer not to say")
            confirmation = "Got it 💚 You may continue."
            if _gut_voice_owns_turn(state):
                state.setdefault("messages", []).append({"role": "assistant", "content": confirmation})
            else:
                send_whatsapp_message(state["user_id"], confirmation)

    elif last_q == "pregnancy_check" and not is_resuming:
        # Coming from pregnancy check (Females)
        if msg_id == "pregnancy_no" or (
            msg == "no" and "✅" in state.get("user_msg", "")
        ):
            state["is_pregnant"] = False
            state["is_breastfeeding"] = False
            _update_last_answer_in_history(state, "No")
        elif (
            msg_id == "pregnancy_yes_pregnant"
            or "pregnant" in msg
            or "🤰" in state.get("user_msg", "")
        ):
            state["is_pregnant"] = True
            state["is_breastfeeding"] = False
            _update_last_answer_in_history(state, "Yes, pregnant")
        elif (
            msg_id == "pregnancy_yes_breastfeeding"
            or "breastfeeding" in msg
            or "🤱" in state.get("user_msg", "")
        ):
            state["is_pregnant"] = False
            state["is_breastfeeding"] = True
            _update_last_answer_in_history(state, "Yes, breastfeeding")

    # Check if already collected (session resume) - BUT NOT if resuming from QnA
    if state.get("health_safety_status") and not is_resuming:
        logger.info(
            f"Health safety screening already collected for user {state['user_id']}"
        )
        # IMPORTANT: Do NOT override last_question here - it resets routing to health screening question.
        return state

    # Update last answer from previous question (skip if resuming from QnA)
    if state.get("user_msg") and not is_resuming:
        _update_last_answer_in_history(state, state["user_msg"])

    question = "💚 This helps ensure the cleanse is safe for you\n\nSelect the option that applies.\n\n*Note:* Type 'None' if not any."

    if _gut_voice_owns_turn(state):
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("health_safety_screening", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_list(
            state["user_id"],
            question,
            "Health Status 🩺",
            HEALTH_SAFETY_LIST_ITEMS,
            header_text="Health Safety Check",
        )

    _store_question_in_history(state, question, "health_safety_screening")
    state["last_question"] = "health_safety_screening"
    state["pending_node"] = "collect_health_safety_screening"
    return state


def collect_detox_experience(state: State) -> State:
    """Node: Collect previous detox/cleanse experience."""

    # Check if we're resuming from QnA or Snap
    last_q = state.get("last_question")
    is_resuming = last_q in [
        "resuming_from_health_qna",
        "resuming_from_product_qna",
        "resuming_from_snap",
    ]

    # Capture health_safety_status from previous step (router usually sets this; keep in sync with new list IDs)
    # Skip if resuming from QnA
    if last_q == "health_safety_screening" and not is_resuming:
        msg = (state.get("user_msg") or "").lower()
        msg_id = state.get("user_msg", "")

        # Resolve specific condition using the same map as the router
        specific_status = resolve_health_safety_status(msg, msg_id)

        if specific_status:
            block_conditions = {"under_18", "pregnant", "ulcers", "diarrhea", "ibs_ibd"}
            state["health_safety_status"] = specific_status
            state["health_safety_group"] = "gut_condition" if specific_status in block_conditions else "medical_condition"
            state["specific_health_condition"] = msg

        _update_last_answer_in_history(state, state["user_msg"])


    # Check if already collected (session resume) - BUT NOT if resuming from QnA
    if state.get("detox_experience") is not None and not is_resuming:
        logger.info(
            f"Detox experience already collected for user {state['user_id']}: {state['detox_experience']}"
        )
        # Don't overwrite last_question if router specifically set it to detox_recent_reason
        if state.get("last_question") != "detox_recent_reason":
            state["last_question"] = "detox_experience"
        return state

    # Update last answer from previous question (skip if resuming from QnA)
    if state.get("user_msg") and not is_resuming:
        _update_last_answer_in_history(state, state["user_msg"])

    # Send safety warnings if needed (from previous health_safety_screening) - skip if resuming from QnA
    if last_q == "health_safety_screening" and not is_resuming:
        safety_status = state.get("health_safety_status")
        warning = HEALTH_SAFETY_WARNINGS.get(safety_status)
        if warning and not state.get("health_safety_warning_sent"):
            if _gut_voice_owns_turn(state):
                state.setdefault("messages", []).append({"role": "assistant", "content": warning})
            else:
                send_whatsapp_message(state["user_id"], warning)
            _store_system_message(state, warning)
            state["health_safety_warning_sent"] = True
            if not _gut_voice_owns_turn(state):
                time.sleep(2.5)
    question = "🌿 Experience check\n\nHave you done a gut cleanse or detox before?"

    if _gut_voice_owns_turn(state):
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        question = VOICE_QUESTIONS.get("detox_experience", question)
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        _send_whatsapp_buttons(
            state["user_id"],
            question,
            [
                {
                    "type": "reply",
                    "reply": {"id": "detox_exp_no", "title": "No, first time 🆕"},
                },
                {
                    "type": "reply",
                    "reply": {"id": "detox_exp_recent", "title": "Yes (< 6 months)"},
                },
                {
                    "type": "reply",
                    "reply": {"id": "detox_exp_long_ago", "title": "Yes, but long ago"},
                },
            ],
        )

    _store_question_in_history(state, question, "detox_experience")
    state["last_question"] = "detox_experience"
    state["pending_node"] = "collect_detox_experience"
    return state
