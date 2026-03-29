import logging
import asyncio
import time
import random
import os
from datetime import datetime
from typing import Dict, Optional

from app.api.v1.constants import (
    STATE_TRANSITIONING_TO_SNAP,
    STATE_SNAP_COMPLETE,
    STATE_TRANSITIONING_TO_GUT_COACH,
    STATE_VERIFIED,
    STATE_POST_PLAN_QNA,
    STATE_RESUMING_FROM_SNAP,
    KEY_LAST_QUESTION
)
from app.api.v1.http_client import HTTPClient
from app.api.v1.message_util import process_batched_message_util, handle_interruption as shared_handle_interruption
from app.services.crm.sessions import SESSIONS, save_session_to_file, load_user_session
from app.services.whatsapp.client import send_whatsapp_message, send_whatsapp_message_async
from app.services.chatbot.bugzy_free_form.agent import graph
from app.services.chatbot.bugzy_free_form.constants import QUESTION_TO_NODE, TRANSITION_MESSAGES
from app.services.rag.qna import MedicalGuardrails, EmergencyDetector

# Re-export for compatibility (e.g. orchestrator / other modules importing handle_interruption from here)
handle_interruption = shared_handle_interruption

MESSAGE_BATCH_WINDOW = 4.5
PENDING_MESSAGES: Dict[str, dict] = {}
MAIN_EVENT_LOOP = None
logger = logging.getLogger(__name__)

WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")


def set_main_event_loop(loop):
    global MAIN_EVENT_LOOP
    MAIN_EVENT_LOOP = loop


async def wa_typing(to_phone_number: str, duration_ms: int = 800) -> None:
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
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
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
        client = HTTPClient.get_client()
        await client.post(url, headers=headers, json=payload)
    except Exception as e:
        logger.error("Reaction failed: %s", e)


def get_batched_message(user_id: str) -> Optional[str]:
    batch = PENDING_MESSAGES.get(user_id)
    if not batch or not batch.get("messages"):
        return None
    combined = "\n".join(batch["messages"])
    PENDING_MESSAGES.pop(user_id, None)
    return combined


async def handle_resume_flow(user_id: str, state: dict, current_question: str) -> None:
    state["pending_node"] = QUESTION_TO_NODE.get(current_question, "post_plan_qna")
    state[KEY_LAST_QUESTION] = STATE_RESUMING_FROM_SNAP
    msg = random.choice(TRANSITION_MESSAGES)
    await send_whatsapp_message_async(user_id, msg)
    SESSIONS[user_id] = state
    save_session_to_file(user_id, state)
    try:
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
            if "user_id" not in new_state:
                new_state["user_id"] = user_id
            SESSIONS[user_id] = new_state
            save_session_to_file(user_id, SESSIONS[user_id])
    except Exception as e:
        logger.error("Resume error: %s", e)
        state["user_id"] = user_id
        SESSIONS[user_id] = state
        save_session_to_file(user_id, state)


def get_button_text_from_id(button_id: str, button_title: str = None) -> str:
    return button_title if button_title else button_id


async def process_node_reaction(state: dict, user_id: str, message_id: str) -> None:
    if random.random() > 0.5:
        return
    node = (state.get("pending_node") or state.get("last_question") or "").lower()
    emoji = None
    if node in ["verify_user", STATE_VERIFIED]:
        emoji = random.choice(["👋", "✨", "🌟"])
    elif STATE_POST_PLAN_QNA in node or "qna" in node:
        emoji = random.choice(["❓", "💬", "🤝"])
    if emoji:
        await send_whatsapp_reaction(user_id, message_id, emoji)


def _minimal_state(user_id: str, user_msg: str) -> dict:
    return {
        "user_id": user_id,
        "user_msg": user_msg,
        "last_question": None,
        "conversation_history": [],
        "journey_history": [],
        "full_chat_history": [{"role": "user", "content": user_msg, "timestamp": datetime.now().isoformat()}],
        "current_agent": None,
        "user_name": None,
        "phone_number": None,
        "crm_user_data": None,
        "user_order": None,
        "user_order_date": None,
        "has_orders": False,
    }


async def process_batched_message(user_id: str, combined_text: str) -> None:
    # Template for Free Form
    free_form_template = {
        "last_question": None,
        "conversation_history": [],
        "journey_history": [],
        "full_chat_history": [],
        "current_agent": None,
        "user_name": None,
        "phone_number": None,
        "crm_user_data": None,
        "user_order": None,
        "user_order_date": None,
        "has_orders": False,
    }

    await process_batched_message_util(
        user_id,
        combined_text,
        product_name="free_form", 
        initial_state_template=free_form_template,
        graph=graph
    )


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
        
        if batch.get("flusher_running"):
            return

        batch["flusher_running"] = True

        async def _flusher():
            try:
                # Wait until the inactivity window has elapsed since the last message
                while True:
                    b = PENDING_MESSAGES.get(user_id)
                    if not b:
                        return
                    elapsed = time.time() - b.get("timer", 0)
                    remaining = MESSAGE_BATCH_WINDOW - elapsed
                    if remaining <= 0:
                        break
                    await asyncio.sleep(min(remaining, 0.2))

                combined = get_batched_message(user_id)
                if not combined:
                    return

                try:
                    await wa_typing(user_id, duration_ms=800)
                except Exception:
                    pass

                logger.info("📦 Background flush for user %s with batched message", user_id)
                # Ensure correct args for free_form process_batched_message
                await process_batched_message(user_id, combined)
            finally:
                batch_ref = PENDING_MESSAGES.get(user_id)
                if batch_ref is not None:
                    batch_ref["flusher_running"] = False

        # Schedule the async task on the running loop
        asyncio.create_task(_flusher())
            
    except Exception as e:
        logger.exception("⚠️ Error scheduling batch flush: %s", e)
