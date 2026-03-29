import logging
import sys
import os
import time
import asyncio
import base64
import json
from collections import OrderedDict
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

# Load environment variables immediately
load_dotenv()

from app.api.v1.constants import (
    STATE_TRANSITIONING_TO_SNAP,
    STATE_SNAP_COMPLETE,
    STATE_VERIFIED,
    STATE_POST_PLAN_QNA,
    STATE_HEALTH_QNA_ANSWERED,
    STATE_PRODUCT_QNA_ANSWERED,
    KEY_MEAL_PLAN_SENT,
    KEY_EXERCISE_PLAN_SENT,
    KEY_LAST_QUESTION
)
from app.api.v1.http_client import HTTPClient
from app.api.v1.chat_routes import router as chat_router
# Import node logic from the new general API location
from app.api.v1.orchestrator import (
    handle_resume_flow, 
    get_button_text_from_id,
    process_node_reaction,
    handle_incoming_text_message,
    handle_resume_button
)

from app.config.product_registry import detect_product_from_order, BugzyProduct
from app.services.snap.transition import continue_snap_flow_after_image
from app.services.crm.sessions import SESSIONS, save_session_to_file, load_user_session, _init_mongo_if_needed, save_snap_analysis
from app.services.whatsapp.client import set_whatsapp_sender, set_whatsapp_sender_async
from app.services.whatsapp.messages import remove_markdown
from app.services.scheduler import start_scheduler
from app.services.snap import analyze_food_image

# Only importing for type hints if needed, but we don't use it directly here anymore
# QUESTION_TO_NODE moved to product-specific APIs (ams_api, gut_cleanse_api, free_form_api)

# Initialize logging configuration as early as possible
logging.basicConfig(
    level=logging.INFO,
    format="[APP] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

# Ensure the root logger and app logger are at INFO level
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)



logger = logging.getLogger(__name__)
logger.info("🚀 Webhook server logger initialized")

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting up FastAPI webhook server...")
    
    # Initialize MongoDB connection (lazy load)
    try:
        _init_mongo_if_needed()
    except Exception as e:
        logger.error("⚠️ Error initializing MongoDB: %s", e)
    
    # Start the scheduler for sending periodic health messages
    try:
        start_scheduler()
        logger.info("✅ Scheduler started successfully")
    except Exception as e:
        logger.error("⚠️ Could not start scheduler: %s", e)
    
    # Register WhatsApp sender
    try:
        # Register both sync and async senders
        set_whatsapp_sender(_send_whatsapp_via_meta_sync)
        set_whatsapp_sender_async(_send_whatsapp_via_meta_async)
        logger.info("✅ WhatsApp sender registered")
        
    except Exception as e:
        logger.error("⚠️ Error registering WhatsApp sender: %s", e)
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down webhook server...")
    # Close HTTPClient session
    await HTTPClient.close()

app = FastAPI(lifespan=lifespan)

# WhatsApp API credentials
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

# Idempotency for processed WhatsApp message IDs
PROCESSED_MESSAGE_IDS: OrderedDict[str, float] = OrderedDict()
PROCESSED_TTL_SECONDS = 60 * 10  # 10 minutes
PROCESSED_MAX_SIZE = 2048

def _mark_processed(message_id: str) -> None:
    now = time.time()
    PROCESSED_MESSAGE_IDS[message_id] = now
    cutoff = now - PROCESSED_TTL_SECONDS
    keys_to_delete = [k for k, ts in PROCESSED_MESSAGE_IDS.items() if ts < cutoff]
    for k in keys_to_delete:
        PROCESSED_MESSAGE_IDS.pop(k, None)
    while len(PROCESSED_MESSAGE_IDS) > PROCESSED_MAX_SIZE:
        PROCESSED_MESSAGE_IDS.popitem(last=False)


def _already_processed(message_id: str) -> bool:
    ts = PROCESSED_MESSAGE_IDS.get(message_id)
    if ts is None:
        return False
    if time.time() - ts > PROCESSED_TTL_SECONDS:
        PROCESSED_MESSAGE_IDS.pop(message_id, None)
        return False
    return True


def _split_message(message: str, max_length: int = 4096) -> list:
    """Split a long message into chunks that fit within WhatsApp's character limit.
    Keeps disclaimers (⚠️, 💊, 🌿) together with the last chunk."""
    if len(message) <= max_length:
        return [message]
    
    # Check if message contains disclaimers at the end
    disclaimer_markers = ['⚠️ *Health Condition Notice:', '💊 *Supplement Disclaimer:', '🌿 *Gut Health Note:']
    has_disclaimers = any(marker in message for marker in disclaimer_markers)
    
    if has_disclaimers:
        # Find where disclaimers start
        disclaimer_start = len(message)
        for marker in disclaimer_markers:
            pos = message.find(marker)
            if pos != -1 and pos < disclaimer_start:
                disclaimer_start = pos
        
        # Split into main content and disclaimers
        main_content = message[:disclaimer_start].rstrip()
        disclaimers = message[disclaimer_start:].strip()
        
        # If disclaimers alone are too long, let them be their own chunk
        if len(disclaimers) > max_length:
            # Split main content normally
            main_chunks = _split_message_simple(main_content, max_length)
            # Add disclaimers as separate chunk
            return main_chunks + [disclaimers]
        
        # Try to keep disclaimers with last chunk of main content
        main_chunks = _split_message_simple(main_content, max_length)
        
        if main_chunks:
            last_chunk = main_chunks[-1]
            combined = last_chunk + "\n\n" + disclaimers
            
            # If combined fits, merge them
            if len(combined) <= max_length:
                main_chunks[-1] = combined
                return main_chunks
            else:
                # Disclaimers need their own chunk
                return main_chunks + [disclaimers]
        else:
            return [disclaimers]
    
    # No disclaimers, split normally
    return _split_message_simple(message, max_length)


def _split_message_simple(message: str, max_length: int) -> list:
    """Simple message splitting by paragraphs."""
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs first (double newlines)
    paragraphs = message.split('\n\n')
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed the limit
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                # Single paragraph is too long, split by sentences
                sentences = paragraph.split('. ')
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = sentence
                        else:
                            # Single sentence is too long, split by words
                            words = sentence.split(' ')
                            for word in words:
                                if len(current_chunk) + len(word) + 1 > max_length:
                                    if current_chunk:
                                        chunks.append(current_chunk.strip())
                                        current_chunk = word
                                    else:
                                        # Single word is too long, force split
                                        chunks.append(word[:max_length])
                                        current_chunk = word[max_length:]
                                else:
                                    current_chunk += (" " + word if current_chunk else word)
                    else:
                        current_chunk += (". " + sentence if current_chunk else sentence)
        else:
            current_chunk += ("\n\n" + paragraph if current_chunk else paragraph)
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def _send_whatsapp_via_meta_sync(user_id: str, message: str) -> None:
    """Synchronous implementation using httpx.Client"""
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.error("WHATSAPP: Missing credentials")
        return
    
    message_chunks = _split_message(message)
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    
    try:
        with httpx.Client(timeout=10.0) as client:
            for i, chunk in enumerate(message_chunks):
                logger.info("📤 SENDING FREE-FORM MESSAGE (SYNC) to %s (chunk %d/%d): %s", user_id, i+1, len(message_chunks), chunk[:100] + ('...' if len(chunk) > 100 else ''))
                payload = {"messaging_product": "whatsapp", "to": user_id, "type": "text", "text": {"body": chunk}}
                
                try:
                    response = client.post(url, headers=headers, json=payload)
                    
                    try:
                        response_data = response.json()
                    except (json.JSONDecodeError, ValueError):
                        response_data = {"error": {"message": response.text[:200], "code": response.status_code}}
                    
                    logger.info("📥 Response Status: %d | Data: %s", response.status_code, response_data)
                    
                    if response.status_code != 200:
                        error_data = response_data.get('error', {})
                        logger.error("❌ Message send failed | Code: %s | Message: %s", error_data.get('code'), error_data.get('message', 'Unknown error'))
                    
                    response.raise_for_status()
                    
                    if i < len(message_chunks) - 1:
                        time.sleep(0.5)
                        
                except Exception as e:
                    logger.error("❌ WHATSAPP API Error (chunk %d/%d) for user %s: %s", i+1, len(message_chunks), user_id, e)
    except Exception as e:
        logger.error("❌ Error initiating httpx Client: %s", e)

async def _send_whatsapp_via_meta_async(user_id: str, message: str) -> None:
    """Asynchronous implementation using shared HTTPClient"""
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.error("WHATSAPP: Missing credentials")
        return
    
    message_chunks = _split_message(message)
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    
    client = HTTPClient.get_client()

    for i, chunk in enumerate(message_chunks):
        logger.info("📤 SENDING FREE-FORM MESSAGE (ASYNC) to %s (chunk %d/%d): %s", user_id, i+1, len(message_chunks), chunk[:100] + ('...' if len(chunk) > 100 else ''))
        payload = {"messaging_product": "whatsapp", "to": user_id, "type": "text", "text": {"body": chunk}}
        
        try:
            response = await client.post(url, headers=headers, json=payload)
            
            try:
                response_data = response.json()
            except (json.JSONDecodeError, ValueError):
                response_data = {"error": {"message": response.text[:200], "code": response.status_code}}
            
            logger.info("📥 Response Status: %d | Data: %s", response.status_code, response_data)
            
            if response.status_code != 200:
                error_data = response_data.get('error', {})
                logger.error("❌ Message send failed | Code: %s | Message: %s", error_data.get('code'), error_data.get('message', 'Unknown error'))
            
            response.raise_for_status()
            
            if i < len(message_chunks) - 1:
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.error("❌ WHATSAPP API Error (chunk %d/%d) for user %s: %s", i+1, len(message_chunks), user_id, e)


async def send_whatsapp_reaction_async(to_phone_number: str, message_id: str, emoji: str) -> None:
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
        response.raise_for_status()
        logger.info("✅ Reaction sent successfully: %s", emoji)
    except Exception as e:
        logger.error("❌ Reaction failed: %s", e)


@app.get("/webhook")
async def verify(request: Request):
    """Webhook verification endpoint for WhatsApp."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    
    return PlainTextResponse("Verification failed", status_code=403)


def _handle_status_update(statuses: list) -> None:
    """Handle message status updates (sent, delivered, read, etc)."""
    for status in statuses:
        message_id = status.get("id")
        status_type = status.get("status")
        recipient_id = status.get("recipient_id")
        timestamp = status.get("timestamp")
        errors = status.get("errors", [])
        
        logger.info("📊 MESSAGE STATUS UPDATE | ID: %s | Recipient: %s | Status: %s | Timestamp: %s", 
                    message_id, recipient_id, status_type.upper() if status_type else 'UNKNOWN', timestamp)
        
        if errors:
            for error in errors:
                logger.error("❌ Status error | Code: %s | Title: %s | Message: %s | Data: %s", 
                             error.get('code'), error.get('title'), error.get('message'), error.get('error_data'))

async def _handle_image_message(msg: dict, user_id: str) -> None:
    """Handle image messages: download, analyze, and trigger flows."""
    image_info = msg.get("image", {})
    image_caption = image_info.get("caption", "")
    message_id = msg.get('id')
    
    logger.info("📸 Image message received from %s | ID: %s%s", user_id, message_id, f" | Caption: {image_caption}" if image_caption else "")
    
    # Send reaction
    if message_id:
        try:
            await send_whatsapp_reaction_async(user_id, message_id, "📸")
        except Exception:
            pass
            
    # Download image
    media_id = image_info.get('id')
    if not (media_id and WHATSAPP_API_TOKEN):
        return

    try:
        client = HTTPClient.get_client()
        headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}"}

        # Step 1: Get media URL
        media_url_endpoint = f"https://graph.facebook.com/v20.0/{media_id}"
        media_response = await client.get(media_url_endpoint, headers=headers)
        media_response.raise_for_status()
        media_url = media_response.json().get('url')
        logger.info("Media URL retrieved: %s", media_url)
        
        # Step 2: Download image content
        image_response = await client.get(media_url, headers=headers)
        image_response.raise_for_status()
        
        # Step 3: Base64 encode (not strictly needed for analysis variable but good for check)
        # base64.b64encode(image_response.content).decode('utf-8')
        logger.info("Image downloaded successfully, size: %d bytes", len(image_response.content))
        
        # Send typing indicator
        try:
            if all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
                url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
                headers_json = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id,
                    "typing_indicator": {"type": "text"}
                }
                await client.post(url, headers=headers_json, json=payload)
        except Exception:
            pass
            
        # Step 4: Analyze image (Run blocking analysis in thread)
        def run_analysis():
            return analyze_food_image(
                image_url=media_url,
                whatsapp_token=WHATSAPP_API_TOKEN,
                user_query=image_caption if image_caption else None
            )
        
        result = await asyncio.to_thread(run_analysis)
        
        if not result["success"]:
            error_msg = result.get("error", "Failed to analyze image")
            logger.error("❌ Vision analysis failed: %s", error_msg)
            await _send_whatsapp_via_meta_async(user_id, f"Sorry, I couldn't analyze that image. {error_msg}")
            return
            
        vision_content = result["vision_content"]
        category = result["category"]
        
        logger.info("🤖 Vision Analysis (Category %s) completed successfully", category)

        # Save snap analysis
        snap_data = {
            "image_url": media_url,
            "category": category,
            "analysis": vision_content,
            "raw_output": result.get("raw_output", ""),
            "user_caption": image_caption if image_caption else None,
            "analysis_mode": result.get("analysis_mode"),
        }
        # save_snap_analysis is synchronous
        await asyncio.to_thread(save_snap_analysis, user_id, snap_data)
        
        # Send analysis back
        cleaned_analysis = remove_markdown(vision_content)
        await _send_whatsapp_via_meta_async(user_id, cleaned_analysis)
        
        # Update session
        if user_id in SESSIONS:
            SESSIONS[user_id]["snap_analysis_result"] = cleaned_analysis
            SESSIONS[user_id]["snap_analysis_sent"] = True
            
            # Check flow status
            current_question = SESSIONS[user_id].get(KEY_LAST_QUESTION)
            plans_completed = bool(SESSIONS[user_id].get(KEY_MEAL_PLAN_SENT)) and bool(SESSIONS[user_id].get(KEY_EXERCISE_PLAN_SENT))
            
            snap_states = [STATE_TRANSITIONING_TO_SNAP, STATE_SNAP_COMPLETE]
            # Verify states: verified, post_plan_qna, etc.
            safe_states = [None, STATE_VERIFIED, STATE_POST_PLAN_QNA, STATE_HEALTH_QNA_ANSWERED, STATE_PRODUCT_QNA_ANSWERED] + snap_states

            if current_question and current_question not in safe_states and not plans_completed:
                 # Mid-flow resume
                 logger.info("User %s is in middle of flow at: %s, resuming...", user_id, current_question)
                 await handle_resume_flow(user_id, SESSIONS[user_id], current_question)
            else:
                 # Normal or SNAP flow
                 if current_question == STATE_TRANSITIONING_TO_SNAP:
                     # continue_snap_flow_after_image is sync and likely uses graph.stream
                     await asyncio.to_thread(continue_snap_flow_after_image, user_id, SESSIONS[user_id])
                 elif plans_completed:
                     logger.info("User %s plans completed, image sent separately", user_id)
                     save_session_to_file(user_id, SESSIONS[user_id])
                 else:
                     logger.info("User %s image analyzed, saving session", user_id)
                     SESSIONS[user_id][KEY_LAST_QUESTION] = STATE_SNAP_COMPLETE
                     save_session_to_file(user_id, SESSIONS[user_id])
                     
    except Exception as e:
        logger.exception("Error processing image for user %s", user_id)

def _handle_button_message(msg: dict) -> tuple[str, bool]:
    """Handle button click messages. Returns (text, is_processed)."""
    button_data = msg.get("button", {})
    button_payload = button_data.get("payload")
    button_text = button_data.get("text")
    logger.info("🔘 BUTTON MESSAGE from %s | Payload: '%s' | Text: '%s'", msg.get('from'), button_payload, button_text)
    
    payload_lower = (button_payload or "").lower().strip()
    text_lower = (button_text or "").lower().strip()
    
    is_resume = ("resume" in payload_lower or "resume" in text_lower)
    
    if is_resume:
        logger.info("✅ Resume button detected! Setting text to 'resume_journey'")
        return "resume_journey", True
        
    return (button_text if button_text else button_payload), True

def _handle_interactive_message(msg: dict, user_id: str) -> tuple[str, bool]:
    """Handle interactive messages (list/button replies). Returns (text, is_processed)."""
    interactive_data = msg.get("interactive", {})
    interactive_type = interactive_data.get("type")
    logger.info("📱 INTERACTIVE MESSAGE from %s | Type: %s", user_id, interactive_type)
    
    if interactive_type == "button_reply":
        button_reply = interactive_data.get("button_reply", {})
        button_id = button_reply.get("id")
        button_title = button_reply.get("title")
        logger.info("👆 Button click: ID=%s, Title=%s", button_id, button_title)
        
        text = get_button_text_from_id(button_id, button_title)
        logger.info("✅ Button mapped to text: '%s'", text)
        return text, True
        
    elif interactive_type == "list_reply":
        list_reply = interactive_data.get("list_reply", {})
        list_id = list_reply.get("id")
        list_title = list_reply.get("title")
        logger.info("📋 List selection: ID=%s, Title=%s", list_id, list_title)
        
        text = get_button_text_from_id(list_id, list_title)
        logger.info("✅ List item mapped to text: '%s'", text)
        return text, True
        
    return None, False


async def _process_webhook_payload(data: dict) -> None:
    """Process a WhatsApp webhook payload asynchronously."""
    if not (data and "entry" in data):
        return

    for entry in data["entry"]:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            
            # Handle message status updates
            if "statuses" in value:
                _handle_status_update(value["statuses"])
            
            # Handle messages
            for msg in value.get("messages", []) or []:
                msg_type = msg.get("type")
                user_id = msg.get("from")
                message_id = msg.get("id")
                
                logger.info("🔔 WEBHOOK MESSAGE RECEIVED: type='%s', from=%s, id=%s", msg_type, user_id, message_id)

                if msg_type == "image":
                    await _handle_image_message(msg, user_id)
                    continue
                
                # Handling interactive/button/text messages
                text = None
                interactive_processed = False
                
                if msg_type == "button":
                    text, interactive_processed = _handle_button_message(msg)
                
                elif msg_type == "interactive":
                    text, interactive_processed = _handle_interactive_message(msg, user_id)

                    
                elif msg_type == "text":
                    text = (msg.get("text", {}) or {}).get("body", "")
                    
                else:
                    # Skip other types (audio, video, sticker, etc.)
                    logger.info("⏭️  Skipping message type: %s", msg_type)
                    continue

                if not user_id:
                    continue
                if message_id and _already_processed(message_id):
                    continue
                
                # Send read + typing indicator
                try:
                    if message_id and all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
                        url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
                        headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
                        payload = {
                            "messaging_product": "whatsapp", 
                            "status": "read", 
                            "message_id": message_id,
                            "typing_indicator": {"type": "text"}
                        }
                        client = HTTPClient.get_client()
                        await client.post(url, headers=headers, json=payload)
                except Exception:
                    pass

                # Load session
                if user_id not in SESSIONS:
                    try:
                        # load_user_session is sync
                        saved_session = load_user_session(user_id)
                        if saved_session:
                            logger.info("✅ Loaded session for user %s from persistent storage", user_id)
                            SESSIONS[user_id] = saved_session
                            SESSIONS[user_id]["interaction_mode"] = "chat"
                    except Exception as e:
                        logger.error("⚠️ Error loading session for user %s: %s", user_id, e)
                
                state = SESSIONS.get(user_id, {
                    "user_id": user_id,
                    "conversation_history": [],
                    "full_chat_history": [],
                    "interaction_mode": "chat",
                })
                
                if user_id not in SESSIONS:
                    logger.info("🆕 Creating new session for user %s", user_id)

                # Capture pushed name if available
                contacts = value.get("contacts", [])
                if contacts and isinstance(contacts, list):
                    profile = contacts[0].get("profile", {})
                    push_name = profile.get("name")
                    if push_name:
                         # Update session with push name
                         state = SESSIONS.get(user_id, {})
                         if state.get("whatsapp_push_name") != push_name:
                             logger.info("👤 Captured WhatsApp push name for %s: %s", user_id, push_name)
                             state["whatsapp_push_name"] = push_name
                             # Ensure minimal structure exists if state was empty
                             if "user_id" not in state:
                                 state["user_id"] = user_id
                             SESSIONS[user_id] = state
                             # Save immediately to persist name
                             # We use to_thread to avoid blocking event loop
                             asyncio.create_task(asyncio.to_thread(save_session_to_file, user_id, state))

                # Flow-aware reaction
                if message_id:
                    await process_node_reaction(state, user_id, message_id)

                # Message Batching / Resume Handling
                if interactive_processed and text == "resume_journey":
                    logger.info("⚡ Resume button detected! Bypassing batch queue for user %s", user_id)
                    await handle_resume_button(user_id, text)
                else:
                    handle_incoming_text_message(user_id, text, state.get(KEY_LAST_QUESTION))
                
                if message_id:
                    _mark_processed(message_id)


@app.post("/webhook")
async def webhook(request: Request):
    """Main webhook endpoint for receiving WhatsApp messages."""
    data = await request.json()

    # Fire-and-forget: each webhook is processed concurrently on the event loop
    asyncio.create_task(_process_webhook_payload(data))

    return {"status": "ok"}


# Include REST API routes for Node.js backend integration
app.include_router(chat_router)


if __name__ == "__main__":
    import uvicorn
    # Security: Use environment variable for host binding, default to localhost
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "6000"))
    uvicorn.run(app, host=host, port=port)