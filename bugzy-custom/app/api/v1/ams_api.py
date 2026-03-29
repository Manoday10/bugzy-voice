import logging
import asyncio
import time
import random
import os
from datetime import datetime
from typing import Optional

from app.api.v1.constants import (
    resolve_button_text, AMS_BUTTON_MAP, AMS_INITIAL_STATE_TEMPLATE, AMS_DIRECT_FIELD_MAP, AMS_REACTION_RULES, resolve_node_reaction,
    STATE_TRANSITIONING_TO_SNAP,
    STATE_SNAP_COMPLETE,
    STATE_TRANSITIONING_TO_GUT_COACH,
    STATE_VERIFIED,
    STATE_POST_PLAN_QNA,
    STATE_HEALTH_QNA_ANSWERED,
    STATE_PRODUCT_QNA_ANSWERED,
    STATE_RESUMING_FROM_SNAP,
    KEY_MEAL_PLAN_SENT,
    KEY_EXERCISE_PLAN_SENT,
    KEY_LAST_QUESTION
)
from app.api.v1.http_client import HTTPClient
from app.api.v1.message_util import process_batched_message_util, handle_interruption as shared_handle_interruption
from app.services.crm.sessions import SESSIONS, save_session_to_file, load_user_session, save_session
from app.services.whatsapp.client import send_whatsapp_message, send_whatsapp_message_async
from app.services.whatsapp.parser import extract_age
from app.services.chatbot.bugzy_ams.agent import graph
from app.services.chatbot.bugzy_ams.constants import QUESTION_TO_NODE, TRANSITION_MESSAGES
from app.services.chatbot.bugzy_ams.nodes.qna_nodes import is_contextual_product_question
from app.services.prompts.general.health_product_detection import is_health_question, is_product_question
from app.services.rag.qna import MedicalGuardrails, EmergencyDetector

# Logic constants
MESSAGE_BATCH_WINDOW = 4.5  # seconds to wait for additional messages
PENDING_MESSAGES: dict[str, dict] = {}  # user_id -> {messages: [], timer: time, last_question: str, flusher_running: bool}

# Logger
logger = logging.getLogger(__name__)

# WhatsApp Credentials
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")


# ==============================================================================
# NODE CONFIGURATION & MAPPING
# ==============================================================================






# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


async def wa_typing(to_phone_number: str, duration_ms: int = 800) -> None:
    """Send a typing indicator to WhatsApp user."""
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        return
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_number,
        "type": "typing",
        "typing": {"duration": max(300, min(20000, int(duration_ms)))}
    }
    try:
        client = HTTPClient.get_client()
        await client.post(url, headers=headers, json=payload)
    except Exception:
        pass


async def send_whatsapp_reaction(to_phone_number: str, message_id: str, emoji: str) -> None:
    """Send a reaction emoji to a specific message."""
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.error("❌ WHATSAPP: Missing credentials for reaction")
        return
    
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone_number,
        "type": "reaction",
        "reaction": {"message_id": message_id, "emoji": emoji}
    }
    
    try:
        logger.info("📤 Sending reaction %s to message %s", emoji, message_id)
        client = HTTPClient.get_client()
        response = await client.post(url, headers=headers, json=payload)
        # logger.info("📱 Reaction API Response: %d - %s", response.status_code, response.text)
        response.raise_for_status()
        logger.info("✅ Reaction sent successfully: %s", emoji)
    except Exception as e:
        logger.error("❌ Reaction failed: %s", e)


def get_batched_message(user_id: str) -> Optional[str]:
    """Get the combined message from the batch and clear it."""
    batch = PENDING_MESSAGES.get(user_id)
    if not batch or not batch.get("messages"):
        return None
    
    # Combine all messages with newlines
    combined = "\n".join(batch["messages"])
    
    # Clear the batch
    PENDING_MESSAGES.pop(user_id, None)
    
    return combined


async def handle_resume_flow(user_id: str, state: dict, current_question: str) -> None:
    """
    Handle resuming the conversation flow after an interruption (emergency, guardrail, snap).
    Update session state to point to the correct pending node and send transition message.
    """
    # Map current question to the corresponding node
    state["pending_node"] = QUESTION_TO_NODE.get(current_question, "collect_age")
    
    # Set last_question to indicate resuming
    state[KEY_LAST_QUESTION] = STATE_RESUMING_FROM_SNAP
    logger.info("Set pending_node to: %s for user %s", state['pending_node'], user_id)
    logger.info("Set last_question to: resuming_from_snap to match snap behavior")
    
    # Send transition message
    random_message = random.choice(TRANSITION_MESSAGES)
    await send_whatsapp_message_async(user_id, random_message)
    logger.info("📱 Sent transition message: %s", random_message)
    
    # Update session
    SESSIONS[user_id] = state
    save_session_to_file(user_id, state)
    logger.info("💾 Session saved for user %s (resume setup)", user_id)
    
    # Execute graph stream to resume
    try:
        # Ensure user_id is in state before streaming
        if "user_id" not in state:
            state["user_id"] = user_id
        
        def run_graph_sync(state_input):
            events = []
            for event in graph.stream(state_input):
                events.append(event)
            return events

        graph_events = await asyncio.to_thread(run_graph_sync, state)
        final_state_from_graph = graph_events[-1] if graph_events else None
        
        if final_state_from_graph:
            last_node_name = list(final_state_from_graph.keys())[0]
            new_state = final_state_from_graph[last_node_name]
            # Ensure user_id is preserved in the new state
            if "user_id" not in new_state:
                new_state["user_id"] = user_id
            SESSIONS[user_id] = new_state
            logger.info("Resumed to node: %s, now in state: %s", last_node_name, SESSIONS[user_id].get('last_question'))
            save_session_to_file(user_id, SESSIONS[user_id])
    except Exception as resume_error:
        logger.exception("Error during resume: %s", resume_error)
        # Ensure user_id is still in session even if resume fails
        if "user_id" not in state:
            state["user_id"] = user_id
        SESSIONS[user_id] = state
        save_session_to_file(user_id, state)


def get_button_text_from_id(button_id: str, button_title: str) -> str:
    """
    Maps a button ID to the corresponding text value for the chatbot.
    Returns the text to be processed.
    """

    return resolve_button_text(button_id, button_title, extra_map=AMS_BUTTON_MAP)


async def process_node_reaction(state: dict, user_id: str, message_id: str) -> None:
    """
    Analyzes the current state and sends an appropriate emoji reaction 
    to the user's message based on the active node OR user input content.
    """
    # Control overall reaction probability (50% chance to send a reaction)
    REACTION_PROBABILITY = 0.5
    if random.random() > REACTION_PROBABILITY:
        return

    # PRIORITY: Check if user is asking a health/product question
    # If so, react with Q&A emoji instead of node-based emoji
    user_msg = state.get("user_msg", "")
    conversation_history = state.get("conversation_history", [])

    # Running potentially heavy NLP checks in thread
    def check_questions():
        try:
             is_prod = is_product_question(user_msg)
             is_contextual = is_contextual_product_question(user_msg, conversation_history) if conversation_history else False
             is_med = is_health_question(user_msg)
             return is_prod, is_contextual, is_med
        except Exception:
             return False, False, False

    is_product, is_contextual_product, is_health = await asyncio.to_thread(check_questions)
    
    if is_product or is_contextual_product or is_health:
        # User is asking a question - send Q&A reaction
        qna_emojis = ["❓", "💬", "🤔", "💡"]
        emoji = random.choice(qna_emojis)
        logger.info("🎯 Q&A-based reaction: %s (detected: product=%s, health=%s)", emoji, is_product or is_contextual_product, is_health)
        await send_whatsapp_reaction(user_id, message_id, emoji)
        return

    current_node = None
    try:
        current_node = (state.get("pending_node") or state.get("last_question") or "")
    except Exception:
        current_node = ""
    
    node = (current_node or "").lower()
    emoji = None
    reason = None

    # Resolve using centralized rules specified for AMS
    emoji, reason = resolve_node_reaction(node, AMS_REACTION_RULES)

    if not emoji:
        # Soft fallback by agent context (reduced from 40% to 10%)
        agent = (state.get("current_agent") or "").lower()
        if agent == "meal":
            emoji, reason = random.choice(["🥗", "🍽️", "🍱", "🌱"]), "meal_context"
        elif agent == "exercise":
            emoji, reason = random.choice(["💪🏻", "🏃", "⚡", "🏋️"]), "exercise_context"
        elif random.random() < 0.1:
            emoji, reason = random.choice(["👍🏻", "✨", "🌟", "💫"]), "random"

    if emoji:
        logger.info("🎯 Node-based reaction: %s (node: %s, reason: %s)", emoji, node, reason)
        await send_whatsapp_reaction(user_id, message_id, emoji)


# ==============================================================================
# CORE PROCESSING FUNCTIONS
# ==============================================================================

def schedule_batch_flush(user_id: str) -> None:
    """Start a background flusher that waits for inactivity then processes the batch.
    
    This function schedules the async _flusher task on the running event loop 
    since it is always called from an async context (webhook background task).
    """
    try:
        batch = PENDING_MESSAGES.get(user_id)
        if not batch:
            return
        # If flusher is already running, it will pick up the timer update automatically
        if batch.get("flusher_running"):
            return

        # Mark to avoid duplicate tasks
        batch["flusher_running"] = True

        async def _flusher():
            try:
                # Wait until the inactivity window has elapsed since the last message
                while True:
                    b = PENDING_MESSAGES.get(user_id)
                    if not b:
                        # Already flushed elsewhere
                        return
                    elapsed = time.time() - b.get("timer", 0)
                    remaining = MESSAGE_BATCH_WINDOW - elapsed
                    if remaining <= 0:
                        break
                    # Sleep a little, then re-check (non-blocking)
                    await asyncio.sleep(min(remaining, 0.2))

                # Try to get combined message and clear batch
                combined = get_batched_message(user_id)
                if not combined:
                    return

                # Give user a short typing indicator before sending combined reply
                try:
                    await wa_typing(user_id, duration_ms=800)
                except Exception:
                    pass

                logger.info("📦 Background flush for user %s with batched message", user_id)
                # Process the batched message directly (it handles threading internally where needed)
                await process_batched_message(user_id, combined)
            finally:
                # Ensure flag reset in case batch reappears later
                batch_ref = PENDING_MESSAGES.get(user_id)
                if batch_ref is not None:
                    batch_ref["flusher_running"] = False

        # Schedule the async task on the running loop
        asyncio.create_task(_flusher())
            
    except Exception as e:
        logger.exception("⚠️ Error scheduling batch flush: %s", e)


# Re-export shared_handle_interruption as handle_interruption
handle_interruption = shared_handle_interruption

def _normalize_ams_profiling(state: dict) -> None:
    """Normalize profiling flags and ensure required fields exist."""
    # CRITICAL: Normalize stale profiling flags
    has_complete_profile = bool(
        state.get("age")
        and state.get("height")
        and state.get("weight")
    )
    if state.get("profiling_collected") and not has_complete_profile:
        logger.info(
            "🧭 Normalizing profiling_collected=False (incomplete profile: age=%s, height=%s, weight=%s)",
            bool(state.get("age")),
            bool(state.get("height")),
            bool(state.get("weight")),
        )
        state["profiling_collected"] = False

    # Initialize other tracking flags if missing
    if "profiling_collected_in_meal" not in state:
        state["profiling_collected_in_meal"] = False
    if "profiling_collected_in_exercise" not in state:
        state["profiling_collected_in_exercise"] = False
    if "bmi_calculated" not in state:
        state["bmi_calculated"] = bool(state.get("bmi_category") or state.get("bmi"))
        
    # CRITICAL FIX: Initialize exercise fields if missing (for sessions created before these fields were added)
    exercise_fields = ["fitness_level", "activity_types", "exercise_frequency", "exercise_intensity", "session_duration", "sedentary_time", "exercise_goals"]
    for field in exercise_fields:
        if field not in state:
            state[field] = None

def _clear_ams_profiling(user_id: str, state: dict) -> None:
    """Clear profiling data if at the start of the journey."""
    last_q = state.get(KEY_LAST_QUESTION)
    
    has_profiling_data = bool(
        state.get("age") or 
        state.get("height") or 
        state.get("weight")
    )
    
    is_journey_start = last_q in [None, "verified", "ask_meal_plan_preference"] and not has_profiling_data
    
    if is_journey_start:
        profiling_keys_to_clear = [
            "age", "height", "weight", "bmi", "bmi_category",
            "health_conditions", "medications",
            "wants_meal_plan",
            "meal_plan_sent",
            "profiling_collected"
        ]
        for key in profiling_keys_to_clear:
             if key in state:
                state[key] = None
        logger.info("🧹 Cleared profiling data for user %s (journey start: %s, has_data: %s)", user_id, last_q, has_profiling_data)
    else:
        logger.info("ℹ️  Skipped profiling data clearing for user %s (mid-journey: %s, has_data: %s)", user_id, last_q, has_profiling_data)

def _process_ams_special_fields(user_id: str, state: dict, last_question: str, text: str) -> bool:
    """Handle special fields that don't map directly or need manual handling."""

    # Meal plan change requests: do NOT overwrite - node accumulates changes
    if last_question == "awaiting_meal_day1_changes":
        return True  # Handled (ignored)

    # Review states
    if last_question in ["meal_day1_plan_review", "meal_day1_revised_review",
                           "day1_plan_review", "day1_revised_review"]:
        return True # Handled (ignored)

    # Preference questions
    if last_question in ["ask_meal_plan_preference", "ask_exercise_plan_preference"]:
        return True # Handled (ignored)

    # CRITICAL FIX: Prevent QnA questions from being stored as field values.
    # When the user asks a product/health question mid-journey (e.g., "how to take my product"
    # while we're waiting for age/height), the message_util blindly stores it as the field value
    # BEFORE the graph runs. The graph then correctly routes to product_qna/health_qna but on
    # resume the collect_* node sees the field as "already collected" and never re-asks.
    # Note: "age" has its own special extraction path in message_util (NOT via field_map), so
    # it must be listed here explicitly alongside the field_map keys.
    _data_collection_fields = {"age"} | set(AMS_DIRECT_FIELD_MAP.keys())
    if last_question in _data_collection_fields:
        if is_product_question(text) or is_health_question(text):
            logger.info(
                "⚠️  Skipping field storage for last_question=%s: detected as QnA query (text=%r)",
                last_question, text
            )
            return True  # Skip storing – graph router will route to product_qna / health_qna

    return False

async def process_batched_message(user_id: str, combined_text: str) -> None:
    await process_batched_message_util(
        user_id,
        combined_text,
        product_name="ams",
        initial_state_template=AMS_INITIAL_STATE_TEMPLATE,
        graph=graph,
        field_map=AMS_DIRECT_FIELD_MAP,
        normalize_profiling_logic=_normalize_ams_profiling,
        clear_profiling_logic=_clear_ams_profiling,
        special_field_processor=_process_ams_special_fields
    )
