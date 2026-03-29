"""
User verification and basic info collection nodes.

This module contains nodes for user verification, collecting basic information
(age, height, weight), BMI calculation, and SNAP image analysis transitions.
"""

import re
import time
import logging
from typing import Tuple

from app.services.chatbot.bugzy_ams.state import State
from app.services.whatsapp.utils import (
    _set_if_expected,
    _store_question_in_history,
    _update_last_answer_in_history,
    _store_system_message,
    parse_height_weight,
    parse_number_from_text,
    extract_age,
)
from app.services.whatsapp.client import send_whatsapp_message
from app.services.whatsapp.messages import remove_markdown
from app.services.crm.sessions import (
    fetch_user_details,
    save_session_to_file,
    fetch_order_details,
    extract_order_details,
)
from app.services.prompts.ams.validation_config import VALIDATION_RULES
from app.services.prompts.ams.conversational import get_conversational_response
from app.services.chatbot.bugzy_ams.constants import (
    TRANSITION_TO_GUT_COACH_MESSAGES,
    AMS_KEYS_TO_CLEAR,
    AMS_CRM_GREETING_1,
    AMS_CRM_GREETING_2,
    AMS_CRM_GREETING_3,
    AMS_GENERIC_GREETING_1,
    AMS_GENERIC_GREETING_2,
    AMS_GENERIC_GREETING_3,
    BMI_TEXT_CATEGORIES,
    BMI_NUMERIC_CATEGORIES,
    BMI_LAST_CATEGORY,
)

# SHARED VALIDATION IMPORTS
from app.services.chatbot.bugzy_shared.validation import (
    validate_input as shared_validate_input,
    handle_validated_input as shared_handle_validated_input,
)

logger = logging.getLogger(__name__)


def _ams_voice_owns_turn(state: State) -> bool:
    """True when voice owns the turn — avoid duplicate WhatsApp UI during LiveKit call."""
    return _ams_voice_owns_turn(state) or state.get("voice_call_active") is True


def validate_input(user_input: str, expected_field: str) -> Tuple[bool, str]:
    """
    Wrapper for shared validation logic.
    Maintains original signature for compatibility.
    """
    return shared_validate_input(
        user_input=user_input,
        expected_field=expected_field,
        validation_rules=VALIDATION_RULES,
        # Pass defaults for other args if needed, or rely on shared defaults
    )


def handle_validated_input(
    state: State, expected_field: str, max_attempts: int = 3
) -> str:
    """
    Wrapper for shared validated input handling.
    Maintains original signature for compatibility.
    """
    # Define specific feedback maps used in AMS
    ams_feedback_map = {
        "age": '"{user_input}" does not actually tell an actual age number.\nFor example: 25 or 30 years.',
        "height": '"{user_input}" does not actually tell an actual height.\nShare your height like this: 170 cm, 5\'8", or 1.75 m.',
        "weight": '"{user_input}" does not actually tell an actual weight.\nExamples: 70 kg or 150 lbs.',
    }

    return shared_handle_validated_input(
        state=state,
        expected_field=expected_field,
        validation_rules=VALIDATION_RULES,
        field_feedback_map=ams_feedback_map,
        max_attempts=max_attempts,
    )


# --- SHARED NODES ---
def verify_user_node(state: State) -> State:
    """Node: Verify user by phone number against CRM."""
    phone = state["user_id"]
    result = fetch_user_details(phone)

    # Reset all profiling and plan data to ensure a fresh start
    for key in AMS_KEYS_TO_CLEAR:
        if key in state:
            state[key] = None

    # Always reset agent to meal initially
    state["current_agent"] = "meal"

    if "error" not in result and "message" not in result:
        state["phone_number"] = result.get("phone_number")
        state["user_name"] = result.get("name")
        state["crm_user_data"] = result.get("full_data")

        # --- NEW: Fetch Latest Order Details ---
        try:
            order_response = fetch_order_details(phone)
            order_info = extract_order_details(order_response)

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
            state["user_order"] = None
            state["user_order_date"] = None
            state["has_orders"] = False

        greeting_msg1 = AMS_CRM_GREETING_1.format(user_name=state["user_name"])
        send_whatsapp_message(state["user_id"], greeting_msg1)

        greeting_msg2 = AMS_CRM_GREETING_2
        send_whatsapp_message(state["user_id"], greeting_msg2)

        greeting_msg3 = AMS_CRM_GREETING_3
        send_whatsapp_message(state["user_id"], greeting_msg3)

        _store_system_message(state, greeting_msg1)
        _store_system_message(state, greeting_msg2)
        _store_system_message(state, greeting_msg3)
    else:
        greeting_msg1 = AMS_GENERIC_GREETING_1
        send_whatsapp_message(state["user_id"], greeting_msg1)

        greeting_msg2 = AMS_GENERIC_GREETING_2
        send_whatsapp_message(state["user_id"], greeting_msg2)

        greeting_msg3 = AMS_GENERIC_GREETING_3
        send_whatsapp_message(state["user_id"], greeting_msg3)

        _store_system_message(state, greeting_msg1)
        _store_system_message(state, greeting_msg2)
        _store_system_message(state, greeting_msg3)

    state["last_question"] = "verified"
    state["current_agent"] = "meal"

    save_session_to_file(state["user_id"], state)

    return state


def collect_age(state: State) -> State:
    """Node: Collect age with context-aware intro message."""
    msg = (state.get("user_msg") or "").lower()
    # If we have age and user_msg looks like height (wrong router), treat as height and advance
    if state.get("age") and state.get("last_question") == "age":
        height_kw = ("cm", "centimeter", "feet", "foot", "inch", "meter", "m ")
        if any(kw in msg for kw in height_kw):
            updates: dict = {
                "height": (state.get("user_msg") or "").strip(),
                "last_question": "height",
                "pending_node": "collect_weight",
            }
            if _ams_voice_owns_turn(state):
                from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
                q = VOICE_QUESTIONS.get("weight", "What's your weight?")
                msgs = list(state.get("messages", [])) + [{"role": "assistant", "content": q}]
                return state | updates | {"messages": msgs}
            return state | updates
    is_yes = any(keyword in msg for keyword in ["yes", "create", "plan", "ok", "sure"])
    if state.get("last_question") == "ask_meal_plan_preference" and is_yes:
        state["wants_meal_plan"] = True
        state["wants_exercise_plan"] = False
        state["current_agent"] = "meal"
    elif state.get("last_question") == "ask_exercise_plan_preference" and is_yes:
        state["wants_exercise_plan"] = True
        state["current_agent"] = "exercise"

    # Voice-only: validate → parse → store (chat uses _set_if_expected unchanged)
    is_voice = _ams_voice_owns_turn(state)
    if is_voice and state.get("user_msg") and state.get("last_question") in ("age", "voice_agent_promotion_meal"):
        user_input = state["user_msg"].strip()
        is_valid, _ = validate_input(user_input, "age")
        if not is_valid:
            retry_msg = "I didn't quite catch that. What's your age? Just a number like 25 or 30."
            msgs = list(state.get("messages", [])) + [{"role": "assistant", "content": retry_msg}]
            return state | {"messages": msgs}
        age_val = parse_number_from_text(user_input.lower())
        if age_val is None:
            age_val = extract_age(user_input)
        if age_val is not None:
            n = int(age_val) if isinstance(age_val, str) else age_val
            if 1 <= n <= 120:
                state["age"] = str(age_val) if not isinstance(age_val, str) else age_val
        elif user_input and re.search(r"\d", user_input):
            state["age"] = user_input

    # Extract age from user_msg when coming from age question or voice promotion (chat path)
    # Skip overwriting if we already have valid age — user may be giving height (e.g. "one seven" = 170)
    if not (has_valid_age := (existing_age := state.get("age")) and re.search(r"\d", str(existing_age))):
        if not is_voice:
            for expected in ("age", "voice_agent_promotion_meal"):
                if state.get("last_question") == expected:
                    _set_if_expected(state, expected, "age")
                    break

    if state.get("age"):
        # Validate the stored value is an actual age number, not corrupted text from a QnA
        # interruption (e.g., "how to take ams" stored as age before the graph ran).
        if re.search(r"\d", str(state.get("age", ""))):
            logger.info(
                f"Age already collected for user {state['user_id']}: {state['age']}"
            )
            updates: dict = {"last_question": "age", "pending_node": "collect_height"}
            if _ams_voice_owns_turn(state):
                from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
                q = VOICE_QUESTIONS.get("height", "What's your height?")
                msgs = list(state.get("messages", [])) + [{"role": "assistant", "content": q}]
                updates["messages"] = msgs
            return state | updates
        logger.info(f"Clearing invalid age for {state['user_id']}: '{state['age']}'")
        state["age"] = None

    intro_message = ""
    if state.get("wants_meal_plan") and not state.get("meal_plan_sent"):
        intro_message = "✨ Perfect! Before we design your personalized meal plan, let me learn a bit about you. This will only take a moment."
    elif state.get("wants_exercise_plan") and not state.get("exercise_plan_sent"):
        intro_message = "🏋️ Great choice! Before we create your workout plan, I'd like to understand your baseline. This helps me tailor everything perfectly for you."
    else:
        intro_message = "✨ Before I lock everything in, I'd love to personalize it just a bit more for you. This will only take a moment."

    is_voice = _ams_voice_owns_turn(state)
    if is_voice:
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        greetings = {"hi", "hello", "hey", "namaste", "good morning", "good afternoon", "good evening"}
        msg_clean = msg.strip().rstrip("?!.").lower()
        is_greeting = msg_clean in greetings or (len(msg.split()) <= 2 and any(g in msg for g in greetings))
        if is_greeting and state.get("user_msg"):
            question = "Could you tell me your age—just a number like 25 or 30?"
            content = "I'd love to personalize your plan! " + question
        else:
            question = VOICE_QUESTIONS.get("age", "What's your age?")
            content = f"{intro_message} {question}"
        state.setdefault("messages", []).append({"role": "assistant", "content": content})
    else:
        send_whatsapp_message(state["user_id"], intro_message)
        _store_system_message(state, intro_message)
        if not _ams_voice_owns_turn(state):
            time.sleep(1)
        question = "🌸 Can you tell me your age?"
        send_whatsapp_message(state["user_id"], question)

    _store_question_in_history(state, question, "age")

    state["last_question"] = "age"
    state["pending_node"] = "collect_age"
    return state


def collect_height(state: State) -> State:
    """Node: Collect height."""
    user_msg = state.get("user_msg") or ""
    msg = user_msg.lower()
    # Router sent us here but user gave weight (wrong node) — treat as weight and advance
    if state.get("height") and state.get("user_msg"):
        weight_kw = ("kg", "k g", "kilogram", "pound", "lb", "lbs")
        if any(kw in msg for kw in weight_kw):
            updates: dict = {
                "weight": state["user_msg"].strip(),
                "last_question": "weight",
                "pending_node": "calculate_bmi",
            }
            if _ams_voice_owns_turn(state):
                from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
                bmi_msg = "Perfect! Let me calculate your BMI."
                msgs = list(state.get("messages", [])) + [{"role": "assistant", "content": bmi_msg}]
                return state | updates | {"messages": msgs}
            return state | updates

    if state.get("height"):
        if re.search(r"\d", str(state.get("height", ""))):
            logger.info(
                f"Height already collected for user {state['user_id']}: {state['height']}"
            )
            state["last_question"] = "height"
            if _ams_voice_owns_turn(state):
                from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
                q = VOICE_QUESTIONS.get("weight", "What's your weight?")
                state.setdefault("messages", []).append({"role": "assistant", "content": q})
            return state
        logger.info(
            f"Clearing invalid height for {state['user_id']}: '{state['height']}'"
        )
        state["height"] = None

    msg = (state.get("user_msg") or "").lower()
    is_yes = any(keyword in msg for keyword in ["yes", "create", "plan", "ok", "sure"])
    if state.get("last_question") == "ask_exercise_plan_preference" and is_yes:
        state["wants_exercise_plan"] = True
        state["current_agent"] = "exercise"

    # Router routes to collect_height when last_question=age (we have age, asked height).
    # user_msg is the height answer — do NOT run _set_if_expected(age) or we overwrite age.
    if state.get("last_question") in ("age", "height") and state.get("user_msg"):
        user_input = state["user_msg"].strip()
        if _ams_voice_owns_turn(state):
            is_valid, _ = validate_input(user_input, "height")
            if not is_valid:
                retry_msg = "I didn't catch that. What's your height? You can say 170 cm, 5 foot 8, or 1.75 meters."
                msgs = list(state.get("messages", [])) + [{"role": "assistant", "content": retry_msg}]
                return state | {"messages": msgs}
        state["height"] = user_input
    else:
        _set_if_expected(state, "height", "height")

    # Accept height if it has digits OR measurement units (voice may say "one seventy six centimeters")
    height_val = str(state.get("height", ""))
    height_valid = bool(height_val) and (
        re.search(r"\d", height_val)
        or any(kw in height_val.lower() for kw in ("cm", "centimeter", "feet", "foot", "inch", "meter", "m "))
    )
    if state.get("height") and height_valid:
        logger.info(
            f"Height collected for user {state['user_id']}: {state['height']}"
        )
        state["last_question"] = "height"
        weight_q = "What's your weight? You can tell me in kg or lbs."
        if _ams_voice_owns_turn(state):
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
            weight_q = VOICE_QUESTIONS.get("weight", weight_q)
            state.setdefault("messages", []).append({"role": "assistant", "content": weight_q})
        else:
            send_whatsapp_message(state["user_id"], "⚖️ One more! What's your weight?\n\nE.g., 62 kg or 136 lbs.")
            weight_q = "⚖️ One more! What's your weight?\n\nE.g., 62 kg or 136 lbs."
        _store_question_in_history(state, weight_q, "weight")
        state["pending_node"] = "collect_weight"
        return state

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    is_resuming = state.get("last_question") in [
        "resuming_from_health_qna",
        "resuming_from_product_qna",
    ]

    is_voice = _ams_voice_owns_turn(state)
    question = "What's your height? You can tell me in cm, feet and inches, or meters."
    if is_voice:
        if not is_resuming and state.get("age"):
            from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
            resp = get_conversational_response(
                f"Respond warmly to someone who is {state['age']} years old",
                user_name=state.get("user_name", ""),
            )
            content = f"{resp} {VOICE_QUESTIONS.get('height', question)}"
        else:
            content = question
        state.setdefault("messages", []).append({"role": "assistant", "content": content})
    else:
        if not is_resuming:
            response = get_conversational_response(
                f"Respond warmly to someone who is {state['age']} years old",
                user_name=state.get("user_name", ""),
            )
            send_whatsapp_message(state["user_id"], response)
            _store_system_message(state, response)
        send_whatsapp_message(state["user_id"], "📏 Perfect! Just two more – what's your height?\n\nE.g., 172 cm or 5'8.")

    _store_question_in_history(state, question, "height")

    state["last_question"] = "height"
    state["pending_node"] = "collect_height"
    return state


def collect_weight(state: State) -> State:
    """Node: Collect weight."""
    def _weight_valid(w: str) -> bool:
        """Accept if has digits OR has kg/lb (voice: 'seventy five k g')."""
        if not w:
            return False
        s = str(w).lower()
        return bool(re.search(r"\d", s)) or any(
            kw in s for kw in ("kg", "k g", "kgs", "kilogram", "lb", "lbs", "pound")
        )

    if state.get("weight"):
        if _weight_valid(str(state.get("weight", ""))):
            logger.info(
                f"Weight already collected for user {state['user_id']}: {state['weight']}"
            )
            state["last_question"] = "weight"
            state["pending_node"] = "calculate_bmi"
            if _ams_voice_owns_turn(state):
                state.setdefault("messages", []).append({
                    "role": "assistant",
                    "content": "Perfect! Let me calculate your BMI.",
                })
            return state
        logger.info(
            f"Clearing invalid weight for {state['user_id']}: '{state['weight']}'"
        )
        state["weight"] = None

    msg = (state.get("user_msg") or "").lower()
    is_yes = any(keyword in msg for keyword in ["yes", "create", "plan", "ok", "sure"])
    if state.get("last_question") == "ask_exercise_plan_preference" and is_yes:
        state["wants_exercise_plan"] = True
        state["current_agent"] = "exercise"

    # Router routes to collect_weight when last_question=height (we have height, asked weight).
    # Only accept if it looks like weight (digits/units); reject "Okay" etc.
    if state.get("last_question") == "height" and state.get("user_msg"):
        um = state["user_msg"].strip().lower()
        if um not in ("okay", "ok", "yes", "yeah", "yep", "sure", "alright", "got it", "fine"):
            if _ams_voice_owns_turn(state):
                is_valid, _ = validate_input(state["user_msg"].strip(), "weight")
                if not is_valid:
                    retry_msg = "I didn't catch that. What's your weight? You can say 70 kg or 150 lbs."
                    msgs = list(state.get("messages", [])) + [{"role": "assistant", "content": retry_msg}]
                    return state | {"messages": msgs}
            if re.search(r"\d", um) or any(kw in um for kw in ("kg", "k g", "lb", "lbs", "pound")):
                state["weight"] = state["user_msg"].strip()
    if not state.get("weight"):
        _set_if_expected(state, "weight", "weight")

    if state.get("weight") and _weight_valid(str(state.get("weight", ""))):
        logger.info(
            f"Weight collected for user {state['user_id']}: {state['weight']}"
        )
        state["last_question"] = "weight"
        if _ams_voice_owns_turn(state):
            state.setdefault("messages", []).append({
                "role": "assistant",
                "content": "Perfect! Let me calculate your BMI.",
            })
        else:
            send_whatsapp_message(state["user_id"], "💙 Got it! One moment...")
        state["pending_node"] = "calculate_bmi"
        return state

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
    question = VOICE_QUESTIONS.get("weight", "What's your weight? You can tell me in kg or lbs.")
    if _ams_voice_owns_turn(state):
        state.setdefault("messages", []).append({"role": "assistant", "content": question})
    else:
        send_whatsapp_message(state["user_id"], "⚖️ One more! What's your weight?\n\nE.g., 62 kg or 136 lbs.")

    _store_question_in_history(state, question, "weight")

    state["last_question"] = "weight"
    state["pending_node"] = "collect_weight"
    return state


def calculate_bmi_node(state: State) -> State:
    """Node: Calculate and share BMI."""
    msg = (state.get("user_msg") or "").lower()
    is_yes = any(keyword in msg for keyword in ["yes", "create", "plan", "ok", "sure"])
    if state.get("last_question") == "ask_exercise_plan_preference" and is_yes:
        state["wants_exercise_plan"] = True
        state["current_agent"] = "exercise"

    # Don't overwrite weight with greetings or affirmations when we already have valid weight
    um = (state.get("user_msg") or "").lower().strip().rstrip("?.")
    is_ack = um in ("hi", "hello", "hey", "namaste", "okay", "ok", "yes", "yeah", "sure",
                    "good morning", "good afternoon", "good evening")
    has_valid_weight = state.get("weight") and re.search(r"\d", str(state.get("weight", "")))
    if not (has_valid_weight and is_ack):
        _set_if_expected(state, "weight", "weight")

    if state.get("user_msg"):
        _update_last_answer_in_history(state, state["user_msg"])

    weight_text = state.get("weight", "").lower()
    category = "Unknown"
    bmi_display = "Unknown"

    # Try parsing text-based selections first (array lookup replaces if-elif chain)
    matched = next(
        ((cat, disp) for cond, cat, disp in BMI_TEXT_CATEGORIES if cond(weight_text)),
        None,
    )
    if matched:
        category, bmi_display = matched
    else:
        # Fallback to manual calculation
        height_text = state.get("height") or ""
        weight_text_original = state.get("weight") or ""
        height_cm, weight_kg = parse_height_weight(height_text, weight_text_original)

        if height_cm and weight_kg and height_cm > 0 and weight_kg > 0:
            bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)

            if 10 <= bmi <= 60:
                # Numeric BMI lookup replaces if-elif chain
                category = BMI_LAST_CATEGORY
                for threshold, label in BMI_NUMERIC_CATEGORIES:
                    if bmi < threshold:
                        category = label
                        break

                state["bmi"] = str(bmi)
                state["bmi_category"] = category
                state["bmi_calculated"] = True
                state["profiling_collected"] = True
                # Ensure meal flow continues: chain path (collect_weight→calculate_bmi) skips
                # the router's profiling_collected_in_meal set, so set it here for meal journey
                if (
                    state.get("current_agent") == "meal"
                    or state.get("voice_agent_context") == "meal_planning"
                    or state.get("wants_meal_plan")
                ) and not state.get("meal_plan_sent"):
                    state["profiling_collected_in_meal"] = True

                bmi_message = (
                    f"Your BMI is {bmi}, which falls in the {category} category."
                )
                if _ams_voice_owns_turn(state):
                    state.setdefault("messages", []).append({"role": "assistant", "content": bmi_message})
                send_whatsapp_message(state["user_id"], f"💙 {bmi_message}")
                _store_system_message(state, bmi_message)

                state["last_question"] = "bmi_calculated"
                return state

        # Calculation failed or invalid — still advance meal journey
        generic_msg = "Thanks for sharing that with me!"
        if _ams_voice_owns_turn(state):
            state.setdefault("messages", []).append({"role": "assistant", "content": generic_msg})
        send_whatsapp_message(state["user_id"], f"💙 {generic_msg}")
        _store_system_message(state, generic_msg)
        state["last_question"] = "bmi_calculated"
        if (
            state.get("current_agent") == "meal"
            or state.get("voice_agent_context") == "meal_planning"
            or state.get("wants_meal_plan")
        ) and not state.get("meal_plan_sent"):
            state["profiling_collected_in_meal"] = True
        return state

    state["bmi"] = bmi_display
    state["bmi_category"] = category
    state["bmi_calculated"] = True
    state["profiling_collected"] = True

    bmi_message = f"Based on your selections, your BMI is in the {category} range."
    if _ams_voice_owns_turn(state):
        state.setdefault("messages", []).append({"role": "assistant", "content": bmi_message})
    send_whatsapp_message(state["user_id"], f"💙 {bmi_message}")
    _store_system_message(state, bmi_message)

    state["last_question"] = "bmi_calculated"
    return state


def transition_to_snap(state: State) -> State:
    """Node: Automatic transition from meal plan to SNAP analysis."""
    user_name = state.get("user_name", "there")
    send_whatsapp_message(
        state["user_id"], f"\n💪 Now let's move on to your SNAP analysis {user_name}!"
    )
    if not _ams_voice_owns_turn(state):
        time.sleep(1.5)
    send_whatsapp_message(
        state["user_id"],
        "📸 SNAP Image Analysis\n\nPlease share an image of your meal, fridge ingredients, or food item, and I'll analyze it for you!",
    )
    state["current_agent"] = "snap"
    state["last_question"] = "transitioning_to_snap"
    return state


def snap_image_analysis(state: State) -> State:
    """Node: SNAP - Image analysis tool for food/meal analysis."""
    # Import here to avoid circular imports
    from app.services.chatbot.bugzy_ams.router import (
        is_meal_edit_request,
        is_exercise_edit_request,
        extract_day_number,
    )
    from app.services.chatbot.bugzy_ams.nodes.qna_nodes import (
        handle_meal_edit_request,
        handle_exercise_edit_request,
    )

    if state.get("snap_analysis_sent") and state.get("snap_analysis_result"):
        logger.info("Image already analyzed in API layer, skipping analysis")
        state["last_question"] = "snap_complete"
        return state

    user_msg = state.get("user_msg", "")
    if user_msg and user_msg.strip():
        if is_meal_edit_request(user_msg):
            day_num = extract_day_number(user_msg)
            return handle_meal_edit_request(state, day_num)

        if is_exercise_edit_request(user_msg):
            day_num = extract_day_number(user_msg)
            return handle_exercise_edit_request(state, day_num)

        # Skip SNAP for text analysis — but still go through transition_to_gut_coach
        # so the "✨ All set, {user_name}!" message is always sent.
        if not state.get("snap_analysis_result"):
            logger.info("Text input detected in SNAP (skipping analysis, using snap_complete path): %s", user_msg)
            state["last_question"] = "snap_complete"
            return state

    if state.get("last_question") != "transitioning_to_snap":
        send_whatsapp_message(
            state["user_id"],
            "📸 SNAP Image Analysis\n\nPlease share an image of your meal, fridge ingredients, or food item, and I'll analyze it for you!",
        )

    # Fallback simulation
    analysis_result = "📸 Image Analysis Results:\nBased on the image provided:\n🔍 **Detected Items:**\n- Mixed vegetables\n..."

    if not state.get("snap_analysis_result") and not (user_msg and user_msg.strip()):
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
