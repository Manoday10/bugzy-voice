"""
QnA node for bugzy_free_form: post_plan_qna only.

Handles two cases strictly (like bugzy_ams):
1. Product question → product QnA API (http://localhost:8000/ask)
2. General health question → guardrails + context + LLM
"""

import re
import random
import logging

from app.services.chatbot.bugzy_free_form.state import State
from app.services.whatsapp.client import send_whatsapp_message
from app.services.whatsapp.utils import llm
from app.services.whatsapp.messages import send_multiple_messages, remove_markdown
from app.services.prompts.free_form.prompt_store import load_prompt
from app.services.chatbot.bugzy_free_form.context_manager import (
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
)
from app.services.chatbot.bugzy_free_form.constants import (
    PRODUCT_SPECIFIC_KEYWORDS,
    COMPANY_KEYWORDS,
    GENERAL_HEALTH_PATTERNS,
    FOLLOW_UP_PATTERNS,
    ORDER_TRACKING_KEYWORDS,
    PERSONAL_MEAL_PLAN_PATTERNS,
    QUESTION_INDICATORS,
    STATEMENT_PATTERNS,
    STRONG_QUESTION_INDICATORS,
    QNA_FALLBACK_GENERAL,
    QNA_FALLBACK_EXCEPTION,
    QNA_FALLBACK_CONTEXTUAL,
    MY_PRODUCT_QUERY_PHRASES,
    PROFILE_DEBUG_KEYS,
    CATEGORY_EMOJI_MAP,
    CATEGORY_EMOJI_DEFAULT,
)

logger = logging.getLogger(__name__)


def is_product_question(user_msg: str) -> bool:
    """Check if user message is a QUESTION about The Good Bug products or company."""

    msg_lower = user_msg.strip().lower()

    if any(keyword in msg_lower for keyword in ORDER_TRACKING_KEYWORDS):
        return True

    words = msg_lower.split()

    if len(words) < 3:
        return False

    if any(re.search(pattern, msg_lower) for pattern in PERSONAL_MEAL_PLAN_PATTERNS):
        return False

    if not any(indicator in msg_lower for indicator in QUESTION_INDICATORS):
        return False

    if any(pattern in msg_lower for pattern in STATEMENT_PATTERNS):
        if not any(indicator in msg_lower for indicator in STRONG_QUESTION_INDICATORS):
            return False

    if any(
        re.search(r"\b" + re.escape(p) + r"\b", msg_lower) for p in DIRECT_PRODUCT_NAMES
    ):
        return True

    if any(keyword in msg_lower for keyword in PRODUCT_SPECIFIC_KEYWORDS):
        return True

    if any(keyword in msg_lower for keyword in COMPANY_KEYWORDS):
        return True

    return False


def post_plan_qna_node(state: State) -> State:
    """
    Answer general health/product questions.
    No plan editing. Use RAG for product Q, LLM for health Q.
    """
    user_question = (state.get("user_msg") or "").strip()
    if not user_question:
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
        return state

    # DEBUG: Log state keys to see what data exists
    existing_keys = [k for k in PROFILE_DEBUG_KEYS if state.get(k)]
    logger.info(
        "🔍 [FREE_FORM QNA] State has %d/%d profile fields: %s",
        len(existing_keys),
        len(PROFILE_DEBUG_KEYS),
        existing_keys,
    )

    conversation_history = state.get("conversation_history") or []

    if not user_question or user_question in ["[IMAGE_RECEIVED]", ""]:
        logger.info("Skipping post_plan_qna for system/empty message")
        state["last_question"] = "post_plan_qna"
        state["current_agent"] = "post_plan_qna"
        return state

    from app.services.rag.emergency_detection import EmergencyDetector
    from app.services.rag.medical_guardrails import MedicalGuardrails

    emergency_detector = EmergencyDetector()
    medical_guardrails = MedicalGuardrails()

    detected_intent = detect_user_intent(user_question, state)
    state["detected_intent"] = detected_intent

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

    # Debug
    logger.info(
        "QNA ROUTING | product_mentioned=%s | is_contextual=%s | is_product_query=%s",
        product_mentioned,
        is_contextual,
        is_product_query,
    )

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

            # Special handling for "my product"
            is_my_product_query = any(
                p in user_msg_lower
                for p in ["my product", "my products", "my order", "my purchase"]
            )

            if state.get("user_order") and is_my_product_query:
                relevant_prod = None

            final_q = user_question

            # Reformulate if contextual and no explicit product name mentioned
            if (
                relevant_prod and is_contextual and not product_mentioned
            ):  # Corrected from has_product_name
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
                        f"Bias Fix (Free-Form): User asked about '{product_mentioned}' but owns '{user_order}'. Filtering context."
                    )
                    health_ctx = [c for c in health_ctx if "User Product" not in c]

                if health_ctx:
                    final_q = "\n".join(health_ctx) + "\n\n" + final_q

            # Call RAG API
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
                    emoji = random.choice(
                        CATEGORY_EMOJI_MAP.get(category, CATEGORY_EMOJI_DEFAULT)
                    )
                    answer = f"{emoji} {answer}"

            if answer:
                send_multiple_messages(
                    state["user_id"], remove_markdown(answer), send_whatsapp_message
                )
            else:
                # Standard fallback
                send_multiple_messages(
                    state["user_id"],
                    QNA_FALLBACK_GENERAL,
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
                QNA_FALLBACK_EXCEPTION,
                send_whatsapp_message,
            )

        state["last_question"] = "post_plan_qna"
        return state
    else:
        # Case 2: General health question → guardrails + LLM
        is_emergency, _, _, emergency_response = emergency_detector.detect_emergency(
            user_question
        )
        if is_emergency:
            send_multiple_messages(
                state["user_id"],
                remove_markdown(emergency_response),
                send_whatsapp_message,
            )
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append(
                {"role": "user", "content": user_question}
            )
            state["conversation_history"].append(
                {"role": "assistant", "content": emergency_response}
            )
            if len(state["conversation_history"]) > 20:
                state["conversation_history"] = state["conversation_history"][-20:]
            state["last_question"] = "post_plan_qna"
            state["current_agent"] = "post_plan_qna"
            return state

        health_context = {}
        guardrail_triggered, _, guardrail_response = (
            medical_guardrails.check_guardrails(user_question, health_context)
        )
        if guardrail_triggered:
            send_multiple_messages(
                state["user_id"],
                remove_markdown(guardrail_response),
                send_whatsapp_message,
            )
            if state.get("conversation_history") is None:
                state["conversation_history"] = []
            state["conversation_history"].append(
                {"role": "user", "content": user_question}
            )
            state["conversation_history"].append(
                {"role": "assistant", "content": guardrail_response}
            )
            if len(state["conversation_history"]) > 20:
                state["conversation_history"] = state["conversation_history"][-20:]
            state["last_question"] = "post_plan_qna"
            state["current_agent"] = "post_plan_qna"
            return state

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
        persona_prompt = load_prompt("system/bugzy_persona.md")
        messages = [
            {"role": "system", "content": persona_prompt},
            {"role": "user", "content": task_prompt},
        ]
        is_followup = detect_followup_question(user_question, conversation_history)
        temp = determine_llm_temperature(
            user_question, detected_intent, is_followup, conversation_history
        )
        logger.info(
            "free_form post_plan_qna temperature=%s intent=%s followup=%s",
            temp,
            detected_intent,
            is_followup,
        )
        response = llm.invoke(messages, temperature=temp)
        answer = remove_markdown((response.content or "").strip())
        
        # NEW: Add voice agent mention for complex queries
        if len(state.get("user_msg", "").split()) > 10 and not state.get("voice_agent_promotion_shown"):
            answer += (
                "\n\n💡 *Tip*: For detailed questions like this, you can also talk to our "
                "Voice Agent! Just type *'call'* to connect."
            )
            
        send_multiple_messages(state["user_id"], answer, send_whatsapp_message)

        if state.get("conversation_history") is None:
            state["conversation_history"] = []
        state["conversation_history"].append({"role": "user", "content": user_question})
        state["conversation_history"].append({"role": "assistant", "content": answer})

    if len(state.get("conversation_history", [])) > 20:
        state["conversation_history"] = state["conversation_history"][-20:]
    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    return state


def _handle_product_question(
    state: State,
    user_question: str,
    conversation_history: list,
    user_msg_lower: str,
    is_contextual_product: bool,
    mentioned_product: str | None,
) -> str:
    """Call product QnA API and return formatted answer. Fallback on error."""
    try:
        import requests

        qna_url = "http://localhost:8000/ask"
        recent_messages = (
            conversation_history[-5:]
            if len(conversation_history) > 5
            else conversation_history
        )
        relevant_product = extract_relevant_product_from_history(
            recent_messages, user_question
        )

        is_my_product_query = any(p in user_msg_lower for p in MY_PRODUCT_QUERY_PHRASES)
        if state.get("user_order") and is_my_product_query:
            logger.info(
                "free_form product QnA: query about user's own product, using user_order (ignore history product)"
            )
            relevant_product = None

        if relevant_product and is_contextual_product:
            reformulated_question = reformulate_with_gpt(
                user_question, relevant_product, recent_messages
            )
            logger.debug(
                "free_form GPT reformulated question: %s", reformulated_question
            )
            final_question = reformulated_question
        else:
            final_question = user_question

        health_context_parts = []
        user_order = state.get("user_order")
        user_order_date = state.get("user_order_date")
        if user_order and str(user_order).lower() not in [
            "none",
            "no",
            "nil",
            "nothing",
        ]:
            order_ctx = f"User's Purchased Product: {user_order}"
            if user_order_date:
                order_ctx += f" (Ordered on {user_order_date})"
            health_context_parts.append(order_ctx)
        if health_context_parts:
            final_question = "\n".join(health_context_parts) + "\n\n" + final_question

        response = requests.post(
            qna_url,
            json={"question": final_question, "model_type": "llama"},
            timeout=50,
        )

        if response.status_code == 200:
            qna_data = response.json()
            answer = qna_data.get("answer", "")
            category = qna_data.get("category", "general")
            health_warnings = qna_data.get("health_warnings", [])
            if health_warnings and answer:
                answer = answer + "\n\n" + "\n".join(health_warnings)

            if answer and answer.strip() and len(answer.strip()) > 20:
                emoji_prefix = random.choice(
                    CATEGORY_EMOJI_MAP.get(category, CATEGORY_EMOJI_DEFAULT)
                )
                return f"{emoji_prefix} {answer}"
            if is_contextual_product:
                return QNA_FALLBACK_CONTEXTUAL
            return QNA_FALLBACK_GENERAL

        return QNA_FALLBACK_GENERAL
    except Exception as e:
        logger.error("free_form QnA API error: %s", e)
        return QNA_FALLBACK_EXCEPTION
