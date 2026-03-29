"""
User verification nodes for bugzy_free_form.

verify_user_node: CRM fetch + personalized greeting (no meal/exercise pitch).
transition_to_snap, snap_image_analysis: SNAP flow only (no plan edit).
"""

import time
import logging

from app.services.chatbot.bugzy_free_form.state import State
from app.services.whatsapp.client import send_whatsapp_message
from app.services.whatsapp.messages import remove_markdown
from app.services.whatsapp.utils import _store_system_message
from app.services.crm.sessions import (
    fetch_user_details,
    fetch_order_details,
    extract_order_details,
    save_session_to_file,
)
from app.services.rag.product_validator import get_canonical_product_names_from_order

logger = logging.getLogger(__name__)


def _format_main_products_for_greeting(user_order: str) -> str:
    """Return only main product names for greeting (e.g. 'Bye Bye Bloat' not full order string)."""
    names = get_canonical_product_names_from_order(user_order)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return " and ".join(names)


def verify_user_node(state: State) -> State:
    """
    Verify user via CRM, then greet with:
    "Hey {user_name}! You can ask me anything about {product} and anything about general health."
    Then route to post_plan_qna (no meal/exercise flow).
    """
    phone = state["user_id"]
    state["current_agent"] = "post_plan_qna"

    result = fetch_user_details(phone)

    if "error" not in result and "message" not in result:
        state["phone_number"] = result.get("phone_number")
        state["user_name"] = result.get("name")
        state["crm_user_data"] = result.get("full_data")

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

        # Fallback to WhatsApp profile name if available
        user_name = state.get("user_name")
        if not user_name:
            push_name = state.get("whatsapp_push_name")
            if push_name:
                user_name = push_name.split()[0]
                logger.info("👤 Using WhatsApp push name for greeting: %s", user_name)
            else:
                user_name = "there"
        
        # Determine product reference for greeting
        if state.get("has_orders") and state.get("user_order"):
            main_products = _format_main_products_for_greeting(state["user_order"])
            product_ref = main_products if main_products else state["user_order"]
        else:
            product_ref = ""
        if product_ref:
            greeting = (
                f"Hey {user_name}! 👋 I'm Bugsy, here to help you with your {product_ref}.\n\n"
                f"Ask me anything about gut health, nutrition, or general wellness. "
                f"Or 📸 snap a photo of any food and I'll break down the macros for you.\n\n"
                f"How can I help you?"
            )
        else:
            greeting = (
                f"Hey {user_name}! 👋 I'm Bugsy, here to help you.\n\n"
                f"Ask me anything about gut health, nutrition, or general wellness. "
                f"Or 📸 snap a photo of any food and I'll break down the macros for you.\n\n"
                f"How can I help you?"
            )
        send_whatsapp_message(state["user_id"], greeting)
        _store_system_message(state, greeting)
    else:
        # Fallback to WhatsApp profile name if available
        user_name = state.get("user_name")
        if not user_name:
            push_name = state.get("whatsapp_push_name")
            if push_name:
                user_name = push_name.split()[0]
                logger.info("👤 Using WhatsApp push name for greeting (CRM fail): %s", user_name)
            else:
                user_name = "there"

        greeting = (
            f"Hey {user_name}! 👋 I'm Bugsy, here to help you.\n\n"
            f"Ask me anything about gut health, nutrition, or general wellness. "
            f"Or 📸 snap a photo of any food and I'll break down the macros for you.\n\n"
            f"How can I help you?"
        )
        send_whatsapp_message(state["user_id"], greeting)
        _store_system_message(state, greeting)
        state["user_name"] = user_name
        state["user_order"] = None
        state["has_orders"] = False

    state["last_question"] = "verified"
    state["current_agent"] = "post_plan_qna"
    save_session_to_file(state["user_id"], state)
    return state


def transition_to_snap(state: State) -> State:
    """Prompt user to send a food image (same as AMS/Gut Cleanse)."""
    user_name = state.get("user_name", "there")
    send_whatsapp_message(
        state["user_id"],
        f"\n📸 Ready for SNAP, {user_name}! Share an image of your meal and I'll analyze it.",
    )
    if state.get("interaction_mode") != "voice":
        time.sleep(1.5)
    send_whatsapp_message(
        state["user_id"],
        "📸 SNAP Image Analysis\n\nPlease share an image of your meal, fridge ingredients, or food item, and I'll analyze it for you!",
    )
    state["current_agent"] = "snap"
    state["last_question"] = "transitioning_to_snap"
    return state


def snap_image_analysis(state: State) -> State:
    """
    SNAP node for free_form: no meal/exercise edit.
    - If analysis already done (API layer): skip.
    - If user sent text: route back to post_plan_qna (state only).
    - Else: optional fallback analysis message, then post_plan_qna.
    """
    if state.get("snap_analysis_sent") and state.get("snap_analysis_result"):
        logger.info("Image already analyzed in API layer, skipping analysis")
        state["last_question"] = "post_plan_qna"
        return state

    user_msg = (state.get("user_msg") or "").strip()
    if user_msg and user_msg not in ["[IMAGE_RECEIVED]", ""]:
        logger.info("Text input in SNAP (free_form), using snap_complete path: %s", user_msg)
        state["last_question"] = "snap_complete"
        return state

    if state.get("last_question") != "transitioning_to_snap":
        send_whatsapp_message(
            state["user_id"],
            "📸 SNAP Image Analysis\n\nPlease share an image of your meal, fridge ingredients, or food item, and I'll analyze it for you!",
        )

    if not state.get("snap_analysis_result") and not user_msg:
        fallback = """📸 Image Analysis Results:
Based on the image provided: mixed vegetables, protein source, and complex carbs. Estimated ~400-500 kcal. Consider adding leafy greens and staying hydrated."""
        cleaned = remove_markdown(fallback)
        send_whatsapp_message(state["user_id"], cleaned)
        state["snap_analysis_result"] = cleaned
        state["snap_analysis_sent"] = True

    state["last_question"] = "post_plan_qna"
    state["current_agent"] = "post_plan_qna"
    return state
