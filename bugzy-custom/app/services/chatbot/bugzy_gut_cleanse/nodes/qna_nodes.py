"""
QnA nodes for health, product, and post-plan questions.

This module contains nodes for handling health-related questions, product questions,
post-plan Q&A, and plan editing functionality.
"""

import re
import random
from typing import Optional
from app.services.chatbot.bugzy_gut_cleanse.state import State
from app.services.whatsapp.client import send_whatsapp_message
import logging

logger = logging.getLogger(__name__)
from app.services.whatsapp.utils import (
    llm,
)
from app.services.whatsapp.messages import send_multiple_messages, remove_markdown
from app.services.prompts.gut_cleanse.prompt_store import load_prompt
from app.services.chatbot.bugzy_gut_cleanse.router import _is_greeting_message
from app.services.crm.sessions import (
    load_meal_plan,
    save_meal_plan,
    extract_gut_cleanse_meal_user_context,
)

# extract_day_number is now imported from shared extraction
from app.services.chatbot.bugzy_gut_cleanse.context_manager import (
    build_optimized_context,
    detect_user_intent,
    detect_followup_question,
)
from app.services.chatbot.bugzy_shared.qna import (
    DIRECT_PRODUCT_NAMES,
    is_contextual_product_question,
    is_any_product_query,
    extract_relevant_product_from_history,
    reformulate_with_gpt,
    determine_llm_temperature,
    reformulate_followup_fallback,
)
from app.services.chatbot.bugzy_shared.context import is_meal_edit_request
from app.services.chatbot.bugzy_shared.extraction import (
    is_user_providing_information,
    extract_health_conditions_intelligently,
    extract_allergies_intelligently,
    extract_medications_intelligently,
    extract_supplements_intelligently,
    extract_gut_health_intelligently,
    extract_day_number,
)
from app.services.chatbot.bugzy_gut_cleanse.constants import (
    QUESTION_TO_NODE,
    CATEGORY_EMOJI_MAP,
    CATEGORY_EMOJI_DEFAULT,
)

# Sentinel values that mean "no data" — used when building health context
_EMPTY_VALUES = {"none", "no", "nothing", "n/a", "na"}


def _format_health_field(value) -> str:
    """Normalise a health field to a non-empty string, or return '' for empty/sentinel values."""
    if not value:
        return ""
    text = ", ".join(str(v) for v in value if v) if isinstance(value, (list, tuple, set)) else str(value)
    return text if text.strip() and text.strip().lower() not in _EMPTY_VALUES else ""


def _update_state_field(state: dict, key: str, new_value: str, label: str) -> None:
    """Update a single health-profile field in state only when the value actually changed.

    - new_value is a real value   → store it and log
    - new_value is empty string   → user denied; clear the field and log
    - new_value is a sentinel     → skip (don't overwrite with "none" etc.)
    """
    if new_value == state.get(key, ""):
        return  # no change
    if new_value.strip() and new_value.strip().lower() not in _EMPTY_VALUES:
        state[key] = new_value
        logger.info("UPDATED STATE | %s updated to: %s", label, new_value)
    elif not new_value.strip():  # empty → explicit denial
        state[key] = ""
        logger.info("UPDATED STATE | %s cleared (user denial)", label)



def health_qna_node(state: State) -> State:
    """Node: Answer health-related questions and return to flow."""
    user_question = state.get("user_msg", "")

    from app.services.rag.emergency_detection import EmergencyDetector
    from app.services.rag.medical_guardrails import MedicalGuardrails

    # Initialize guardrails
    medical_guardrails = MedicalGuardrails()
    emergency_detector = EmergencyDetector()

    # Detect intent (and store for analytics/debugging)
    detected_intent = detect_user_intent(user_question, state)
    state["detected_intent"] = detected_intent

    # Build optimized context using new modular system
    user_context = build_optimized_context(
        state=state,
        user_question=user_question,
        llm_client=llm,
        intent=detected_intent,
        include_plans=True,
        max_recent_messages=6,
    )

    # =====================================================
    # GUARDRAIL CHECK 1: Emergency Detection (CTAS)
    # =====================================================
    is_emergency, ctas_level, emergency_category, emergency_response = (
        emergency_detector.detect_emergency(user_question)
    )

    if is_emergency:
        # Send emergency response immediately
        send_multiple_messages(
            state["user_id"], emergency_response, send_whatsapp_message
        )

        # Log to conversation history
        if state.get("conversation_history") is None:
            state["conversation_history"] = []
        state["conversation_history"].append({"role": "user", "content": user_question})
        state["conversation_history"].append(
            {"role": "assistant", "content": emergency_response}
        )

        # Keep conversation history manageable
        if len(state["conversation_history"]) > 20:
            state["conversation_history"] = state["conversation_history"][-20:]

        state["health_qna_answered"] = True
        return state

    # =====================================================
    # GUARDRAIL CHECK 2: Medical Guardrails (including Gut Coach Connection)
    # =====================================================
    # Build health context from state
    health_context = {
        "specific_health_condition": state.get("specific_health_condition", ""),
        "food_allergies_intolerances": state.get("food_allergies_intolerances", ""),
        "medications": state.get("medications", ""),
        "supplements": state.get("supplements", ""),
        "digestive_issues": state.get("digestive_issues", ""),
    }

    guardrail_triggered, guardrail_type, guardrail_response = (
        medical_guardrails.check_guardrails(user_question, health_context)
    )

    if guardrail_triggered:
        # Send guardrail response immediately
        send_multiple_messages(
            state["user_id"], guardrail_response, send_whatsapp_message
        )

        # Log to conversation history
        if state.get("conversation_history") is None:
            state["conversation_history"] = []
        state["conversation_history"].append({"role": "user", "content": user_question})
        state["conversation_history"].append(
            {"role": "assistant", "content": guardrail_response}
        )

        # Keep conversation history manageable
        if len(state["conversation_history"]) > 20:
            state["conversation_history"] = state["conversation_history"][-20:]

        state["health_qna_answered"] = True
        return state

    # BIAS FIX: If user mentioned a SPECIFIC product name which is DIFFERENT from their order,
    # pass "None" to the template to avoid biasing the LLM.
    user_order = state.get("user_order", "None")
    product_mentioned = next(
        (
            p
            for p in DIRECT_PRODUCT_NAMES
            if re.search(r"\b" + re.escape(p) + r"\b", user_question.lower())
        ),
        None,
    )
    if (
        product_mentioned
        and user_order
        and user_order.lower() not in product_mentioned.lower()
        and product_mentioned.lower() not in user_order.lower()
    ):
        logger.info(
            f"Bias Fix (Health QnA GUT): Suppressing order '{user_order}' for question about '{product_mentioned}'"
        )
        user_order = "None"

    # Use LLM to answer health question
    template = load_prompt("agent/health_qna_node.md")
    prompt = template.format(
        user_context=user_context,
        user_question=user_question,
        user_name=state.get("user_name", ""),
        user_order=user_order,
        user_order_date=state.get("user_order_date", ""),
    )

    response = llm.invoke(prompt)
    answer = response.content.strip()

    # Send the answer
    send_multiple_messages(
        state["user_id"], remove_markdown(answer), send_whatsapp_message
    )

    # Mirror product_qna_node behavior: log Q&A into conversation history only
    if state.get("conversation_history") is None:
        state["conversation_history"] = []

    # Add user question
    state["conversation_history"].append({"role": "user", "content": user_question})

    # Add assistant answer
    state["conversation_history"].append({"role": "assistant", "content": answer})

    # Keep conversation history manageable (last 20 messages)
    if len(state["conversation_history"]) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]

    # Preserve the current state before setting health_qna_answered
    # Map the current last_question to the appropriate pending_node if not already set
    current_last_question = state.get("last_question", "")

    # Only update pending_node if it's not already set or if we're in a review/plan state
    if not state.get("pending_node") or current_last_question in [
        "day1_plan_review",
        "meal_day1_plan_review",
        "day1_revised_review",
        "meal_day1_revised_review",
        "awaiting_day1_changes",
        "awaiting_meal_day1_changes",
        "day1_complete",
        "meal_day1_complete",
        "day2_complete",
        "meal_day2_complete",
        "day3_complete",
        "meal_day3_complete",
        "day4_complete",
        "meal_day4_complete",
        "day5_complete",
        "meal_day5_complete",
        "day6_complete",
        "meal_day6_complete",
        "meal_plan_complete",
    ]:
        # Set pending_node based on current last_question
        mapped_node = QUESTION_TO_NODE.get(current_last_question)
        if mapped_node:
            state["pending_node"] = mapped_node
            logger.info("HEALTH Q&A: Preserved state - mapped '%s' to '%s'", current_last_question, mapped_node)

    # Mark Q&A handled without touching data-entry fields
    state["last_question"] = "health_qna_answered"

    return state


def product_qna_node(state: State) -> State:
    """Node: Answer product/company questions using QnA API and return to flow."""
    user_question = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])

    # Product names to check
    # Product names to check from shared config
    product_names = DIRECT_PRODUCT_NAMES

    # Direct Name Check (Robust)
    user_msg_lower = user_question.lower()
    product_mentioned = next(
        (
            p
            for p in DIRECT_PRODUCT_NAMES
            if re.search(r"\b" + re.escape(p) + r"\b", user_msg_lower)
        ),
        None,
    )

    is_contextual = is_contextual_product_question(user_question, conversation_history)
    relevant_product = extract_relevant_product_from_history(
        conversation_history[-5:], user_question
    )

    # Debug message to help track product questions
    logger.info(
        "PRODUCT QUESTION DETECTED: '%s' - Product: %s",
        user_question,
        product_mentioned or relevant_product or "Not specified",
    )

    try:
        # Call the QnA API
        import requests

        qna_url = "http://localhost:8000/ask"  # Assuming QnA API runs on port 8000

        # CRITICAL FIX: If user asks about THEIR OWN product/order, ignore history-based product context
        # and rely only on user_order from state.
        is_my_product_query = any(
            p in user_msg_lower
            for p in ["my product", "my products", "my order", "my purchase"]
        )

        if state.get("user_order") and is_my_product_query:
            logger.info(
                "OVERRIDE: Detected query about user's own product. "
                "Ignoring history context '%s' to use user_order.",
                relevant_product,
            )
            relevant_product = None

        # REFORMULATE QUESTION using GPT-3.5 Turbo (same as post_plan_qna_node)
        final_question = user_question
        if relevant_product and is_contextual:
            reformulated_question = reformulate_with_gpt(
                user_question, relevant_product, conversation_history[-5:]
            )
            logger.info(
                "PRODUCT Q&A GPT REFORMULATED QUESTION: %s", reformulated_question
            )
            final_question = reformulated_question

        # INTELLIGENTLY DETECT health conditions, allergies, and medications from current question and conversation history
        # This will merge existing conditions/allergies/medications with any newly mentioned ones
        # Also handles denials when user says "I don't have this condition"
        health_conditions = extract_health_conditions_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_health_conditions=state.get("specific_health_condition", ""),
        )

        allergies = extract_allergies_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_allergies=state.get("food_allergies_intolerances", ""),
        )

        medications = extract_medications_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_medications=state.get("medications", ""),
        )

        supplements = extract_supplements_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_supplements=state.get("supplements", ""),
        )

        gut_health = extract_gut_health_intelligently(
            current_question=user_question,
            conversation_history=conversation_history,
            existing_gut_health=state.get("digestive_issues", ""),
        )

        # Build health context lines using the shared helper
        _field_map = [
            (health_conditions, "Health conditions"),
            (allergies, "Allergies"),
            (medications, "Medications"),
            (supplements, "Supplements"),
            (gut_health, "Gut health"),
        ]
        health_context_lines = [
            f"{label}: {_format_health_field(val)}"
            for val, label in _field_map
            if _format_health_field(val)
        ]

        # Add User Order Context
        user_order = state.get("user_order")
        user_order_date = state.get("user_order_date")
        if user_order and str(user_order).lower() not in {"none", "no", "nil", "nothing"}:
            order_context = f"User's Purchased Product: {user_order}"
            if user_order_date:
                order_context += f" (Ordered on {user_order_date})"
            health_context_lines.append(order_context)

        # BIAS FIX: strip purchased-product context if user is asking about a different product
        if health_context_lines:
            if (
                product_mentioned
                and user_order
                and user_order.lower() not in product_mentioned.lower()
                and product_mentioned.lower() not in user_order.lower()
            ):
                logger.info("Bias Fix: asked about '%s' but owns '%s'. Filtering context.", product_mentioned, user_order)
                health_context_lines = [l for l in health_context_lines if "Purchased Product" not in l]

            if health_context_lines:
                final_question = "\n".join(health_context_lines) + "\n\n" + final_question

        # Update state with newly detected health profile fields
        # ONLY if the user is actually providing information
        if is_user_providing_information(user_question):
            _health_field_map = [
                ("health_conditions", health_conditions, "Health conditions"),
                ("allergies",         allergies,         "Allergies"),
                ("medications",       medications,       "Medications"),
                ("supplements",       supplements,       "Supplements"),
                ("gut_health",        gut_health,        "Gut health"),
            ]
            for key, value, label in _health_field_map:
                _update_state_field(state, key, value, label)

        response = requests.post(
            qna_url,
            json={
                "question": final_question,
                "model_type": "llama",  # Use optimized prompts for better responses
            },
            timeout=50,
        )

        if response.status_code == 200:
            qna_data = response.json()
            answer = qna_data.get(
                "answer",
                "I couldn't find specific information about that. Please contact our support team for detailed product information.",
            )
            category = qna_data.get("category", "general")
            knowledge_status = qna_data.get("knowledge_status", "complete")
            health_warnings = qna_data.get("health_warnings", [])

            # If there are health warnings, append them to the answer
            if health_warnings:
                answer = answer + "\n\n" + "\n".join(health_warnings)

            # Add emoji based on category using the constant map
            emoji_prefix = random.choice(CATEGORY_EMOJI_MAP.get(category, CATEGORY_EMOJI_DEFAULT))

            formatted_answer = f"{emoji_prefix} {answer}"

        else:
            # Fallback response if API fails
            formatted_answer = "💚 I'd be happy to help with product information! Please contact our support team at nutritionist@seventurns.in or call +91 8040282085 for detailed product guidance."

    except Exception as e:
        logger.error("QnA API Error: %s", e)
        # Fallback response if API is unavailable
        formatted_answer = "💚 I'd love to help with product information! Please contact our support team at nutritionist@seventurns.in or call +91 8040282085 for detailed product guidance."

    # Send the answer
    send_multiple_messages(state["user_id"], formatted_answer, send_whatsapp_message)

    # Update conversation history with the current exchange
    if state.get("conversation_history") is None:
        state["conversation_history"] = []

    # Add user message to history
    state["conversation_history"].append({"role": "user", "content": user_question})

    # Add assistant response to history
    # Use relevant_product (from history) as fallback if product_mentioned (from current question) is not available
    # This ensures contextual follow-ups are properly tagged in conversation history
    product_for_history = product_mentioned or relevant_product
    content = formatted_answer
    if product_for_history:
        content = f"About {product_for_history}: {content}"

    state["conversation_history"].append({"role": "assistant", "content": content})

    # Keep conversation history manageable (last 20 messages)
    if len(state["conversation_history"]) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]

    # Preserve the current state before setting product_qna_answered
    # Map the current last_question to the appropriate pending_node if not already set
    current_last_question = state.get("last_question", "")

    # Only update pending_node if it's not already set or if we're in a review/plan state
    if not state.get("pending_node") or current_last_question in [
        "day1_plan_review",
        "meal_day1_plan_review",
        "day1_revised_review",
        "meal_day1_revised_review",
        "awaiting_day1_changes",
        "awaiting_meal_day1_changes",
        "day1_complete",
        "meal_day1_complete",
        "day2_complete",
        "meal_day2_complete",
        "day3_complete",
        "meal_day3_complete",
        "day4_complete",
        "meal_day4_complete",
        "day5_complete",
        "meal_day5_complete",
        "day6_complete",
        "meal_day6_complete",
        "meal_plan_complete",
    ]:
        # Set pending_node based on current last_question
        mapped_node = QUESTION_TO_NODE.get(current_last_question)
        if mapped_node:
            state["pending_node"] = mapped_node
            logger.info("PRODUCT Q&A: Preserved state - mapped '%s' to '%s'", current_last_question, mapped_node)

    # Set state to indicate product Q&A is answered
    state["last_question"] = "product_qna_answered"

    return state

    # Helper functions (is_contextual_product_question, extract_relevant_product_from_history,
    # reformulate_with_gpt, extract_*_intelligently, extract_day_number)
    # have been moved to bugzy_shared modules and are imported at the top of this file.

    current_question_lower = current_question.lower()

    # If it's a general health question, don't extract products from history
    if any(pattern in current_question_lower for pattern in general_health_patterns):
        logger.debug(
            "EXTRACTED PRODUCT | Question '%s' is general health - not extracting products",
            current_question,
        )
        return ""

    # Check current question first for direct mentions
    for product in product_names:
        if re.search(r"\b" + re.escape(product) + r"\b", current_question_lower):
            return product

    # If no product in current question, check recent messages (most recent first)
    for message in reversed(recent_messages):
        content = message.get("content", "").lower()
        for product in product_names:
            if re.search(r"\b" + re.escape(product) + r"\b", content):
                logger.debug(
                    "EXTRACTED PRODUCT | Found '%s' in message: '%s...'",
                    product,
                    content[:50],
                )
                return product

    logger.debug(
        "EXTRACTED PRODUCT | No product found for question: '%s'", current_question
    )
    return ""


def handle_meal_day_selection_for_edit(state: State) -> State:
    """Handle day selection for meal plan editing from post-plan Q&A."""
    from app.services.whatsapp.client import send_whatsapp_message
    import re

    user_msg = state.get("user_msg", "").strip()

    # Try to extract day number from ID first (if present in message)
    match = re.search(r"edit_meal_day(\d)", user_msg.lower())
    if match:
        day_num = int(match.group(1))
    else:
        # Fallback to extracting from text (e.g. "Day 3")
        day_num = extract_day_number(user_msg)

    if day_num:
        state["edit_day_number"] = day_num

        send_whatsapp_message(
            state["user_id"],
            f"Got it! 📝 What changes would you like to make to your Day {day_num} meal plan?\n\n"
            f"For example:\n"
            f'- "Add more protein"\n'
            f'- "Make it vegetarian"\n'
            f'- "Replace rice with quinoa"\n'
            f'- "Reduce calories"',
        )

        state[f"meal_day{day_num}_change_request"] = ""
        state["last_question"] = f"awaiting_meal_day{day_num}_edit_changes"
        state["pending_node"] = "collect_meal_day_edit_changes"
    else:
        send_whatsapp_message(
            state["user_id"],
            "I didn't catch which day you want to edit. Please select a day from the list.",
        )
        state["last_question"] = "select_meal_day_to_edit"

    return state


def collect_meal_day_edit_changes(state: State) -> State:
    """Collect user's requested changes for any meal plan day and regenerate."""
    from app.services.whatsapp.client import send_whatsapp_message
    from app.services.prompts.gut_cleanse.meal_plan_template import (
        build_meal_plan_prompt,
        build_disclaimers,
        _remove_llm_disclaimers,
    )
    from app.services.whatsapp.messages import remove_markdown
    from app.services.llm.bedrock_llm import ChatBedRockLLM

    llm = ChatBedRockLLM()
    import re

    user_msg = state.get("user_msg", "").strip()
    day_num = state.get("edit_day_number")

    # Fallback: Extract day number from last_question if not in state
    # last_question format: "awaiting_meal_day3_edit_changes"
    if not day_num:
        last_q = state.get("last_question", "")
        match = re.search(r"awaiting_meal_day(\d)_edit_changes", last_q)
        if match:
            day_num = int(match.group(1))
            state["edit_day_number"] = day_num  # Store for consistency

    if not user_msg or not day_num:
        send_whatsapp_message(
            state["user_id"],
            f"Please tell me what changes you'd like to make to your Day {day_num if day_num else ''} meal plan.",
        )
        return state

    # Filter out acknowledgments
    acknowledgments = [
        "ok",
        "okay",
        "yes",
        "yeah",
        "sure",
        "fine",
        "good",
        "alright",
        "k",
        "kk",
        "👍",
        "✓",
        "✔️",
    ]
    if user_msg.lower() in acknowledgments:
        return state

    # Store the change request
    state[f"meal_day{day_num}_change_request"] = user_msg

    # Get the existing plan
    old_plan = state.get(f"meal_day{day_num}_plan", "")

    # Store old plan for reference (History Tracking)
    history_key = f"old_meal_day{day_num}_plans"
    if not state.get(history_key):
        state[history_key] = []
    state[history_key].append(old_plan)

    # Acknowledge and start regenerating
    send_whatsapp_message(
        state["user_id"],
        f"Got it! 🔄 Regenerating your Day {day_num} meal plan with: {user_msg}\n\n⏳ One moment...",
    )

    # Build revision prompt
    prompt = build_meal_plan_prompt(
        state=state,
        day_number=day_num,
        previous_meals=None,
        day1_plan=None,
        change_request=user_msg,
        is_revision=True,
    )

    revision_context = f"""
═══════════════════════════════════════════════════════════════
🔄 REVISION MODE - DAY {day_num} REGENERATION
═══════════════════════════════════════════════════════════════

ORIGINAL DAY {day_num} PLAN THAT USER WANTS TO CHANGE:
{old_plan}

USER'S REQUESTED CHANGES:
{user_msg}

REVISION INSTRUCTIONS:
1. Incorporate the user's requested changes
2. Maintain the EXACT format from the template
3. Keep the same level of detail as the original plan
4. Ensure all required sections are present (snacks, gut health, etc.)
5. Keep the warm, supportive tone

"""

    full_prompt = revision_context + prompt

    # Generate revised plan
    response = llm.invoke(full_prompt)
    revised_plan = response.content.strip()

    # Clean up
    revised_plan = _remove_llm_disclaimers(revised_plan)
    disclaimers = build_disclaimers(state)
    if disclaimers:
        revised_plan = revised_plan.rstrip() + disclaimers
    revised_plan = remove_markdown(revised_plan)

    # Update state
    state[f"meal_day{day_num}_plan"] = revised_plan

    # Save to dedicated collection with old plans, change request, and user context
    meal_plan_data = {
        f"meal_day{day_num}_plan": revised_plan,
        f"old_meal_day{day_num}_plans": state.get(f"old_meal_day{day_num}_plans", []),
        f"meal_day{day_num}_change_request": user_msg,
        "user_context": extract_gut_cleanse_meal_user_context(state),
    }
    save_meal_plan(
        state["user_id"],
        meal_plan_data,
        product="gut_cleanse",
        increment_change_count=True,
    )

    # Send to user
    send_whatsapp_message(state["user_id"], revised_plan)
    send_whatsapp_message(
        state["user_id"],
        f"✅ Your Day {day_num} meal plan has been updated! You can continue asking questions or request more changes anytime. 💚",
    )

    # Return to post-plan Q&A
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    state["pending_node"] = None
    state["edit_mode"] = None
    state["edit_day_number"] = None

    return state


def post_plan_qna_node(state: State) -> State:
    """Node: Unified Q&A handler for both health and product questions after plan completion."""
    user_question = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])

    # Skip processing if this is a silent return from journey restart
    if state.get("silent_return"):
        logger.info("Silent return from journey restart - skipping greeting messages")
        state["silent_return"] = False  # Clear the flag
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
        return state

    # Skip processing if this is a system/dummy message (e.g., from SNAP flow)
    if not user_question or user_question.strip() in ["[IMAGE_RECEIVED]", ""]:
        logger.info("Skipping post_plan_qna processing for system message")
        state["last_question"] = "post_plan_qna"
        return state

    # Import guardrails for gut coach connection detection
    import sys
    import os

    sys.path.append(os.path.join(os.path.dirname(__file__)))
    from app.services.rag.emergency_detection import EmergencyDetector
    from app.services.rag.medical_guardrails import MedicalGuardrails

    # Initialize guardrails
    medical_guardrails = MedicalGuardrails()
    emergency_detector = EmergencyDetector()

    # Build concise user context from profile and meal plan

    # Detect intent (and store for analytics/debugging)
    detected_intent = detect_user_intent(user_question, state)
    state["detected_intent"] = detected_intent

    # Only process if there's actually a user question
    # This prevents automatic responses when transitioning from meal plan completion
    if not user_question or not user_question.strip():
        # Just set the state without sending any message
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
        return state

    # CHECK FOR JOURNEY RESTART REQUESTS
    # This allows users to restart meal plan journey
    from app.services.chatbot.bugzy_gut_cleanse.router import is_journey_restart_request

    restart_type = is_journey_restart_request(user_question)

    if restart_type == "meal":
        wants_meal_plan = state.get("wants_meal_plan", False)
        meal_plan_sent = state.get("meal_plan_sent", False)

        if not wants_meal_plan and not meal_plan_sent:
            has_new_profiling = (
                state.get("age_eligible") is not None
                and state.get("gender") is not None
            )
            logger.info(
                "🔄 JOURNEY RESTART: Meal Plan | profiling_collected=%s age_eligible=%s gender=%s is_pregnant=%s is_breastfeeding=%s | skip_profiling=%s",
                state.get("profiling_collected"), state.get("age_eligible"), state.get("gender"),
                state.get("is_pregnant"), state.get("is_breastfeeding"),
                has_new_profiling or bool(state.get("profiling_collected")),
            )

            # Send empathetic acknowledgment message
            user_name = state.get("user_name", "there")
            send_whatsapp_message(
                state["user_id"],
                f"Absolutely, {user_name}! 🌟 I'd love to create a fresh meal plan for you. Let me ask you a few quick questions to personalize it perfectly for your needs.",
            )

            state["wants_meal_plan"] = True
            state["current_agent"] = "meal"  # Set agent to meal for proper routing
            state["journey_restart_mode"] = (
                True  # Flag to return to post_plan_qna after completion
            )
            logger.info(
                "🎯 Starting meal journey - First question will be: collect_dietary_preference"
            )
            # Start meal journey
            from app.services.chatbot.bugzy_gut_cleanse.nodes.meal_plan_nodes import (
                collect_dietary_preference,
            )

            return collect_dietary_preference(state)

    # CHECK FOR PLAN EDIT REQUESTS (before product/health routing)
    # This allows users to edit their meal plans from the post-plan Q&A phase
    # NEW: If user asks to create a NEW meal plan but already has one, ask Edit vs Create New.
    # This prevents "create a meal plan" from being treated as an edit-day flow.
    try:
        msg_lower = user_question.lower()
        create_intent_terms = [
            "create",
            "new",
            "fresh",
            "restart",
            "start over",
            "start again",
            "another",
            "generate",
            "make me",
            "make a",
            "build",
            "plan for me",
        ]
        edit_intent_terms = [
            "edit",
            "change",
            "modify",
            "update",
            "revise",
            "adjust",
            "tweak",
            "replace",
            "swap",
            "day ",
        ]
        meal_keywords = [
            "meal", "diet", "food", "breakfast", "lunch", "dinner", "snack",
            "eating", "nutrition", "menu", "recipe", "plan"
        ]
        exercise_keywords = [
            "exercise", "workout", "fitness", "training", "gym", "cardio", "stretch", "yoga"
        ]

        has_meal_keyword = any(k in msg_lower for k in meal_keywords)
        is_exercise_intent = any(k in msg_lower for k in exercise_keywords)

        is_create_new_intent = (
            any(t in msg_lower for t in create_intent_terms)
            and not any(t in msg_lower for t in edit_intent_terms)
            and has_meal_keyword
            and not is_exercise_intent
        )
        if is_create_new_intent:
            from app.services.crm.sessions import load_meal_plan

            existing_plan = load_meal_plan(state.get("user_id", "")) or {}
            # CRITICAL FIX: ALWAYS set origin flag even if plan doesn't have meal_day1_plan
            # This ensures journey_restart_mode gets set in router
            state["existing_meal_plan_choice_origin"] = "post_plan_qna"
            if existing_plan and existing_plan.get("meal_day1_plan"):
                from app.services.chatbot.bugzy_gut_cleanse.nodes.meal_plan_nodes import (
                    ask_existing_meal_plan_choice,
                )

                state["existing_meal_plan_data"] = existing_plan
                return ask_existing_meal_plan_choice(state)
            else:
                # Plan doesn't exist or is incomplete - treat as if user doesn't have one
                logger.info(
                    "⚠️  Could not load existing meal plan, treating as new plan request"
                )
                from app.services.chatbot.bugzy_gut_cleanse.nodes.meal_plan_nodes import (
                    collect_dietary_preference,
                )

                state["wants_meal_plan"] = True
                state["current_agent"] = "meal"
                state["journey_restart_mode"] = True
                return collect_dietary_preference(state)
    except Exception:
        pass

    try:
        msg_lower = user_question.lower()
        create_intent_terms = [
            "create",
            "new",
            "fresh",
            "restart",
            "start over",
            "start again",
            "another",
            "generate",
            "make me",
            "make a",
            "build",
        ]
        edit_intent_terms = [
            "edit",
            "change",
            "modify",
            "update",
            "revise",
            "adjust",
            "tweak",
            "replace",
            "swap",
            "day ",
        ]
    except Exception:
        pass

    if is_meal_edit_request(user_question):
        logger.info("MEAL EDIT REQUEST DETECTED: %s", user_question)
        day_num = extract_day_number(user_question)
        logger.info("DAY NUMBER EXTRACTED: %s", day_num)
        return handle_meal_edit_request(state, day_num)

    # 1. Broad Product Check (Standardized & Robust)
    user_msg_lower = user_question.lower()
    is_product_query = is_any_product_query(user_question, conversation_history)

    # Direct check for specific name (for bias fix below)
    product_mentioned = next(
        (
            p
            for p in DIRECT_PRODUCT_NAMES
            if re.search(r"\b" + re.escape(p) + r"\b", user_msg_lower)
        ),
        None,
    )
    is_contextual = is_contextual_product_question(user_question, conversation_history)

    # Debug to trace routing decisions
    try:
        has_product_name = (
            product_mentioned is not None
        )  # Define has_product_name for the log
        logger.debug(
            "QNA ROUTING | has_product_name=%s | is_contextual=%s | is_product_query=%s",
            has_product_name,
            is_contextual,
            is_product_query,
        )
    except Exception:
        pass

    # SPECIAL HANDLING FOR BUGZY_GUT_CLEANSE:
    # Prevent exercise-related questions from being routed to product Q&A since bugzy_gut_cleanse doesn't offer exercise plans
    if is_product_query:
        # Check if this is an exercise-related query
        exercise_indicators = [
            "exercise",
            "workout",
            "fitness",
            "training",
            "gym",
            "movements",
            "movement",
            "routine",
            "plan",
            "journey",
            "plam",
            "pla",
            "program",
            "schedule",
        ]
        is_exercise_related = any(
            term in user_msg_lower for term in exercise_indicators
        )

        # For bugzy_gut_cleanse product (which only supports meal plans),
        # treat exercise-related queries as health questions instead of product questions
        if is_exercise_related:
            # Check if we're in bugzy_gut_cleanse context by looking for relevant state indicators
            # If user has meal_plan_sent, they're likely in bugzy_gut_cleanse context
            is_bugzy_gut_cleanse_context = state.get("meal_plan_sent") is True

            if is_bugzy_gut_cleanse_context:
                logger.info(
                    "EXERCISE QUERY DETECTED: Treating exercise-related query as health question for bugzy_gut_cleanse"
                )
                is_product_query = False  # Prevent routing to product Q&A

    if is_product_query:
        # Handle product question using QnA API
        try:
            import requests

            qna_url = "http://localhost:8000/ask"

            # Prepare context for reformulation
            recent_msgs = (
                conversation_history[-5:]
                if len(conversation_history) > 5
                else conversation_history
            )
            relevant_prod = extract_relevant_product_from_history(
                recent_msgs, user_question
            )

            # Special handling for "my product" - override history-based inference
            is_my_product_query = any(
                p in user_msg_lower
                for p in ["my product", "my products", "my order", "my purchase"]
            )

            if state.get("user_order") and is_my_product_query:
                relevant_prod = None  # Force use of user_order

            final_q = user_question

            # Reformulate if contextual and no explicit product name mentioned
            if relevant_prod and is_contextual and not has_product_name:
                final_q = reformulate_with_gpt(
                    user_question, relevant_prod, recent_msgs
                )
                logger.info(f"Reformulated Question: {final_q}")

            # Add User Context headers to the question for RAG
            health_ctx = []
            if state.get("health_conditions"):
                health_ctx.append(f"User Conditions: {state.get('health_conditions')}")
            if state.get("user_order"):
                health_ctx.append(f"User Product: {state.get('user_order')}")

            if health_ctx:
                # BIAS FIX: If user mentioned a SPECIFIC product name which is DIFFERENT from their order,
                # remove the ordered product context.
                user_order = state.get("user_order")
                if (
                    product_mentioned
                    and user_order
                    and user_order.lower() not in product_mentioned.lower()
                    and product_mentioned.lower() not in user_order.lower()
                ):
                    logger.info(
                        f"Bias Fix (Post-Plan): User asked about '{product_mentioned}' but owns '{user_order}'. Filtering context."
                    )
                    health_ctx = [c for c in health_ctx if "User Product" not in c]

                if health_ctx:
                    final_q = "\n".join(health_ctx) + "\n\n" + final_q

            # Call RAG API
            # Explicitly match ams params
            resp = requests.post(
                qna_url, json={"question": final_q, "model_type": "llama"}, timeout=50
            )

            answer = ""
            if resp.status_code == 200:
                qna_data = resp.json()
                answer = qna_data.get("answer", "")
                category = qna_data.get("category", "general")

                # Check for empty/useless
                if (
                    not answer
                    or len(answer) < 5
                    or "I don't have enough information" in answer
                ):
                    pass
                else:
                    # Emojis (keeping logic from gut_cleanse)
                    if category == "product":
                        emoji = random.choice(["🦠", "🧬", "🧪", "🔬"])
                    elif category == "shipping":
                        emoji = random.choice(["📦", "🚚", "🚢", "✈️"])
                    elif category == "refund":
                        emoji = random.choice(["💰", "💳", "🧾", "🔄"])
                    elif category == "policy":
                        emoji = random.choice(["📋", "📜", "📖", "⚖️"])
                    else:
                        emoji = random.choice(["💚", "❤️", "💙", "💜"])

                    answer = f"{emoji} {answer}"

            if answer:
                send_multiple_messages(
                    state["user_id"], remove_markdown(answer), send_whatsapp_message
                )
            else:
                # Standard fallback
                send_multiple_messages(
                    state["user_id"],
                    "💚 I'd be happy to help with more specific product information! Please contact our support team at [nutritionist@seventurns.in](mailto:nutritionist@seventurns.in) or call/WhatsApp 8369744934 for detailed guidance.",
                    send_whatsapp_message,
                )

            # Update history
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append(
                {"role": "user", "content": user_question}
            )
            state["conversation_history"].append(
                {
                    "role": "assistant",
                    "content": answer if answer else "No answer found",
                }
            )

        except Exception as e:
            logger.error(f"QnA API Error: {e}")
            send_multiple_messages(
                state["user_id"],
                "💚 I'd love to help! Please contact our support team at [nutritionist@seventurns.in](mailto:nutritionist@seventurns.in).",
                send_whatsapp_message,
            )

        state["last_question"] = "post_plan_qna"
        return state
    else:
        # Default to health question handling using LLM
        # No need to check is_health_question - if it's not a product question, treat it as health

        # =====================================================
        # GUARDRAIL CHECK 1: Emergency Detection (CTAS)
        # =====================================================
        is_emergency, ctas_level, emergency_category, emergency_response = (
            emergency_detector.detect_emergency(user_question)
        )

        if is_emergency:
            # Send emergency response immediately
            send_multiple_messages(
                state["user_id"], emergency_response, send_whatsapp_message
            )

            # Log to conversation history
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append(
                {"role": "user", "content": user_question}
            )
            state["conversation_history"].append(
                {"role": "assistant", "content": emergency_response}
            )

            # Keep conversation history manageable
            if len(state["conversation_history"]) > 20:
                state["conversation_history"] = state["conversation_history"][-20:]

            state["post_plan_qna_answered"] = True
            return state

        # =====================================================
        # GUARDRAIL CHECK 2: Medical Guardrails (including Gut Coach Connection)
        # =====================================================
        # Build health context from state
        health_context = {
            "health_conditions": state.get("health_conditions", ""),
            "allergies": state.get("allergies", ""),
            "medications": state.get("medications", ""),
            "supplements": state.get("supplements", ""),
            "gut_health": state.get("gut_health", ""),
        }

        guardrail_triggered, guardrail_type, guardrail_response = (
            medical_guardrails.check_guardrails(user_question, health_context)
        )

        if guardrail_triggered:
            # Send guardrail response immediately
            send_multiple_messages(
                state["user_id"], guardrail_response, send_whatsapp_message
            )

            # Log to conversation history
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append(
                {"role": "user", "content": user_question}
            )
            state["conversation_history"].append(
                {"role": "assistant", "content": guardrail_response}
            )

            # Keep conversation history manageable
            if len(state["conversation_history"]) > 20:
                state["conversation_history"] = state["conversation_history"][-20:]

            state["post_plan_qna_answered"] = True
            return state

        # Build optimized context using new modular system
        user_context = build_optimized_context(
            state=state,
            user_question=user_question,
            llm_client=llm,
            intent=detected_intent,
            include_plans=True,
            max_recent_messages=8,
        )

        task_template = load_prompt("agent/post_plan_qna_node.md")
        task_prompt = task_template.format(
            user_context=user_context,
            user_question=user_question,
            user_name=state.get("user_name", ""),
            user_order=state.get("user_order", "None"),
            user_order_date=state.get("user_order_date", ""),
        )

        # Load System Persona
        persona_prompt = load_prompt("system/bugzy_persona.md")

        # Construct messages with System Persona + User Task
        messages = [
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": task_prompt},
        ]

        # Detect if this is a follow-up question
        is_followup = detect_followup_question(user_question, conversation_history)

        # Determine optimal temperature based on question type and context
        optimal_temperature = determine_llm_temperature(
            user_question=user_question,
            detected_intent=detected_intent,
            is_followup=is_followup,
            conversation_history=conversation_history,
        )

        logger.info(
            f"🌡️ Using temperature={optimal_temperature} for intent='{detected_intent}', followup={is_followup}"
        )

        # Invoke LLM with adaptive temperature
        response = llm.invoke(messages, temperature=optimal_temperature)
        answer = response.content.strip()
        send_multiple_messages(
            state["user_id"], remove_markdown(answer), send_whatsapp_message
        )

        # Update conversation history with health exchange
        if state.get("conversation_history") is None:
            state["conversation_history"] = []

        state["conversation_history"].append({"role": "user", "content": user_question})

        state["conversation_history"].append({"role": "assistant", "content": answer})

    # Keep conversation history manageable (last 20 messages)
    if len(state["conversation_history"]) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]

    # Stay in post-plan Q&A state
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"

    return state


def resume_from_qna_node(state: State) -> State:
    """Node: Resume the conversation flow after health or product Q&A."""
    # Random transition messages to make it feel more natural
    transition_messages = [
        "💚 Let's pick up where we left off...",
        "🌟 Now, back to your personalized plan...",
        "✨ Great! Let's continue with your wellness journey...",
        "💫 Perfect! Now let's get back to creating your plan...",
        "🌸 Awesome! Let's continue where we paused...",
        "💝 Thanks for that question! Now, back to your plan...",
        "🌿 Got it! Let's resume building your wellness plan...",
        "💖 Hope that helped! Now, let's continue...",
        "🌺 Wonderful! Let's get back to your personalized journey...",
        "✨ That's sorted! Now, back to crafting your plan...",
        "💚 Perfect! Let's continue with the next step...",
        "🌟 Great question! Now, let's pick up where we were...",
    ]

    random_message = random.choice(transition_messages)
    send_whatsapp_message(state["user_id"], random_message)

    # Clear pending_node if meal plan is completed
    if state.get("meal_plan_sent"):
        state["pending_node"] = None
    # Make sure we have a pending node only if we're still in plan generation
    elif not state.get("pending_node"):
        # Default to age_eligibility if we're coming from profiling
        if state.get("age_eligible") is None:
            state["pending_node"] = "collect_age_eligibility"
        else:
            # Use the current last_question as a fallback
            current_question = state.get("last_question", "").replace("_answered", "")
            if current_question in ["health_qna", "product_qna"]:
                # If we don't have a valid pending node, go to age as fallback
                state["pending_node"] = "collect_age_eligibility"

    # Set the appropriate last_question for resumption
    if state.get("last_question") == "health_qna_answered":
        state["last_question"] = "resuming_from_health_qna"
    elif state.get("last_question") == "product_qna_answered":
        state["last_question"] = "resuming_from_product_qna"

    return state


# --- Plan Edit Functions ---


def handle_meal_edit_request(state: State, day_num: Optional[int] = None) -> State:
    """
    Handle meal plan edit request from post-plan Q&A.
    Routes user to meal plan edit flow.
    """
    from app.services.whatsapp.client import send_whatsapp_message, _send_whatsapp_list

    user_id = state.get("user_id")

    if day_num:
        # User specified a day - ask for changes
        send_whatsapp_message(
            user_id,
            f"Got it! 📝 What changes would you like to make to your Day {day_num} meal plan?\n\n"
            f"For example:\n"
            f'- "Add more protein"\n'
            f'- "Make it vegetarian"\n'
            f'- "Replace rice with quinoa"\n'
            f'- "Reduce calories"',
        )
        state["edit_mode"] = "meal"
        state["edit_day_number"] = day_num
        state[f"meal_day{day_num}_change_request"] = (
            ""  # Will be filled when user responds
        )
        state["last_question"] = f"awaiting_meal_day{day_num}_edit_changes"
        state["pending_node"] = f"collect_meal_day_edit_changes"
    else:
        # No day specified - ask which day to edit
        sections = [
            {
                "title": "📅 Select Day to Edit",
                "rows": [
                    {
                        "id": f"edit_meal_day{i}",
                        "title": f"Day {i}",
                        "description": f"Edit Day {i} meal plan",
                    }
                    for i in range(1, 8)
                ],
            }
        ]

        _send_whatsapp_list(
            user_id=user_id,
            body_text="Which day's meal plan would you like to edit?",
            button_text="Select Day 📅",
            sections=sections,
            header_text="Edit Meal Plan",
        )
        state["edit_mode"] = "meal"
        state["last_question"] = "select_meal_day_to_edit"
        state["pending_node"] = "handle_meal_day_selection_for_edit"

    return state
