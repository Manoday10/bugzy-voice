"""
WhatsApp Client API

This module handles all WhatsApp API interactions including:
- Sending text messages
- Sending template messages
- Sending interactive buttons
- Sending interactive lists
- WhatsApp API configuration
"""

import os
import asyncio
import aiohttp
import httpx
import contextvars
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional
from app.services.crm.sessions import SESSIONS, save_session_to_file, load_user_session
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# WhatsApp API credentials
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

# --- WhatsApp Sender Injection ---
WHATSAPP_SENDER = None
WHATSAPP_SENDER_ASYNC = None

# Rate limiting: Max 50 concurrent WhatsApp API calls to prevent throttling
# Why 50: WhatsApp Business API recommends this limit for sustained throughput
_WHATSAPP_SEMAPHORE = asyncio.Semaphore(50)

_message_collector: contextvars.ContextVar[Optional[List[str]]] = contextvars.ContextVar(
    'message_collector', 
    default=None
)

def get_message_collector() -> Optional[List[str]]:
    """Get the message collector for the current context, if any."""
    return _message_collector.get()

def set_message_collector(collector: List[str]):
    """Set a message collector for the current context."""
    _message_collector.set(collector)

def clear_message_collector():
    """Clear the message collector for the current context."""
    _message_collector.set(None)


def _log_to_history(user_id: str, content: str, role: str = "assistant", metadata: dict = None):
    """
    Helper to log messages to full_chat_history.
    
    Args:
        user_id: The user's ID
        content: The message content (clean text for display)
        role: The role (assistant or user)
        metadata: Optional structured data (e.g., buttons, list options) for app logic
    """
    try:
        session = SESSIONS.get(user_id)
        if not session:
            # Try to load from DB if not in memory (only if really needed, but avoid heavy calls if possible)
            # Since load_user_session is relatively cheap (single doc read), it is okay.
            session = load_user_session(user_id)
        
        if session:
            if session.get("full_chat_history") is None:
                session["full_chat_history"] = []
            
            # Build the history entry
            history_entry = {
                "role": role,
                "content": str(content),
                "timestamp": datetime.now().isoformat()
            }
            
            # Add metadata if provided (backward compatible - only add if present)
            if metadata:
                history_entry["metadata"] = metadata
            
            session["full_chat_history"].append(history_entry)
            save_session_to_file(user_id, session)
            
            # Update cache if it was there (or if we want to populate it? maybe avoid populating blindly to avoid memory bloat)
            # If it was in SESSIONS, it is updated by reference if session came from SESSIONS.
            # If it came from load_user_session, it is a new dict.
            if user_id in SESSIONS:
                SESSIONS[user_id] = session
    except Exception as e:
        logger.error("⚠️ Error logging to history: %s", e)


def set_whatsapp_sender(sender_fn):
    """
    Register a function that actually sends WhatsApp messages (Synchronous).
    Signature: (user_id: str, message: str) -> None
    """
    global WHATSAPP_SENDER
    WHATSAPP_SENDER = sender_fn

def set_whatsapp_sender_async(sender_fn):
    """
    Register a function that actually sends WhatsApp messages (Asynchronous).
    Signature: (user_id: str, message: str) -> Coroutine
    """
    global WHATSAPP_SENDER_ASYNC
    WHATSAPP_SENDER_ASYNC = sender_fn


def send_whatsapp_message(user_id: str, message: str, follow_up: str = None):
    """
    Proxy to the registered synchronous WhatsApp sender.
    
    If a message collector is set for the current thread (via set_message_collector),
    messages will be collected instead of sent.
    """
    logger.info("📨 SENDING FREE-FORM MESSAGE to %s: %s...", user_id, message[:100])
    
    # Log to full_chat_history
    _log_to_history(user_id, message)
    
    # Check if we're in message collection mode (for REST API requests)
    collector = get_message_collector()
    if collector is not None:
        logger.info("📥 Collecting message (REST API mode)")
        collector.append(message)
        if follow_up:
            logger.info("📥 Collecting follow-up message")
            collector.append(follow_up)
            _log_to_history(user_id, follow_up)
        return
    
    if WHATSAPP_SENDER is None:
        logger.warning("❌ Skipping send: WhatsApp sender not configured.")
        return
    try:
        WHATSAPP_SENDER(user_id, message)
        logger.info("✅ Message dispatched to sender function")
        
        # If there's a follow-up message, send it separately
        if follow_up:
            import time
            time.sleep(0.5)  # Small delay between messages
            logger.info("📨 SENDING FOLLOW-UP MESSAGE to %s: %s...", user_id, follow_up[:100])
            WHATSAPP_SENDER(user_id, follow_up)
            logger.info("✅ Follow-up message dispatched to sender function")
            
            # Log follow-up to history
            _log_to_history(user_id, follow_up)
    except Exception as e:
        logger.error("❌ WhatsApp sender error: %s", e, exc_info=True)


async def send_whatsapp_message_async(user_id: str, message: str, follow_up: str = None):
    """
    Proxy to the registered ASYNCHRONOUS WhatsApp sender.
    """
    logger.info("📨 (Async) SENDING FREE-FORM MESSAGE to %s: %s...", user_id, message[:100])
    
    # Log to full_chat_history
    _log_to_history(user_id, message)
    
    # Check if we're in message collection mode
    collector = get_message_collector()
    if collector is not None:
        logger.info("📥 Collecting message (REST API mode)")
        collector.append(message)
        if follow_up:
            logger.info("📥 Collecting follow-up message")
            collector.append(follow_up)
            _log_to_history(user_id, follow_up)
        return
    
    if WHATSAPP_SENDER_ASYNC is None:
        if WHATSAPP_SENDER:
            # Fallback to sync sender via thread if async not available
            logger.warning("⚠️ Async sender not configured, falling back to sync sender in thread.")
            await asyncio.to_thread(send_whatsapp_message, user_id, message, follow_up)
            return
        
        logger.warning("❌ Skipping send: WhatsApp async sender not configured.")
        return

    try:
        await WHATSAPP_SENDER_ASYNC(user_id, message)
        logger.info("✅ Message dispatched to async sender function")
        
        # If there's a follow-up message, send it separately
        if follow_up:
            await asyncio.sleep(0.5)  # Async delay
            logger.info("📨 (Async) SENDING FOLLOW-UP MESSAGE to %s: %s...", user_id, follow_up[:100])
            await WHATSAPP_SENDER_ASYNC(user_id, follow_up)
            logger.info("✅ Follow-up message dispatched to async sender function")
            
            # Log follow-up to history
            _log_to_history(user_id, follow_up)
    except Exception as e:
        logger.error("❌ WhatsApp async sender error: %s", e, exc_info=True)


def _resolve_template_message(template_name: str, template_params: list) -> str:
    """
    Resolve WhatsApp template into the actual user-facing message.
    
    Args:
        template_name: Name of the WhatsApp template
        template_params: List of parameters to substitute
    
    Returns:
        str: The formatted message as users see it on WhatsApp
    """
    # Template definitions matching WhatsApp Business Manager templates
    templates = {
        # Meal reminder templates
        "breakfast_reminder_util": "Hello {0}, this is your scheduled breakfast reminder as requested.\n\n{1}",
        "lunch_reminder_util": "Hello {0}, this is your scheduled lunch reminder as requested.\n\n{1}",
        "dinner_reminder_util": "Hello {0}, this is your scheduled dinner reminder as requested.\n\n{1}",
        
        # Health content templates
        "gut_health_tip_utility": "Hey {0}! {1}\n\n{2}",
        "gut_health_joke_utility": "Hey {0}! {1}\n\n{2}",
        "gut_health_fact_utility": "Hey {0}! {1}\n\n{2}",
    }
    
    # Get template format string
    template_format = templates.get(template_name)
    
    if template_format:
        try:
            # Substitute parameters (using 0-indexed placeholders)
            return template_format.format(*template_params)
        except (IndexError, KeyError) as e:
            logger.warning("⚠️ Error resolving template %s: %s", template_name, e)
            # Fallback: return a readable format
            return f"[Template: {template_name}] " + " | ".join(str(p) for p in template_params)
    else:
        # Unknown template: return a readable format
        logger.warning("⚠️ Unknown template: %s", template_name)
        return f"[Template: {template_name}] " + " | ".join(str(p) for p in template_params)


async def send_whatsapp_template(
    user_id: str,
    template_name: str,
    template_params: list,
    language_code: str = "en_US"
):
    """
    Send WhatsApp template message with parameters.
    
    Args:
        user_id: The recipient's WhatsApp ID
        template_name: Name of the approved WhatsApp template
        template_params: List of parameters to fill in the template
        language_code: Language code for the template (default: en_US)
    
    Returns:
        dict: Response data from WhatsApp API or error dict
    """
    logger.info("📤 SENDING TEMPLATE '%s' to %s with params: %s", template_name, user_id, template_params)
    
    # Log the actual formatted message content to history (not template metadata)
    content = _resolve_template_message(template_name, template_params)
    metadata = {
        "type": "template",
        "template_name": template_name,
        "template_params": template_params
    }
    _log_to_history(user_id, content, metadata=metadata)
    
    # Construct API endpoint
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    # Build headers
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Build template parameters
    parameters = [
        {"type": "text", "text": str(param)}
        for param in template_params
    ]
    
    # Build payload
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            },
            "components": [
                {
                    "type": "body",
                    "parameters": parameters
                }
            ]
        }
    }
    
    logger.debug("📦 Payload: %s", payload)
    
    try:
        # Async HTTP with rate limiting to prevent WhatsApp API throttling
        async with _WHATSAPP_SEMAPHORE:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_data = await response.json()
                    status_code = response.status
                    
                    logger.debug("📥 Response Status: %s, Data: %s", status_code, response_data)
                    
                    if status_code == 200:
                        logger.info("✅ Template sent successfully!")
                        return response_data
                    else:
                        logger.error("❌ Template send failed!")
                        return {"error": response_data}
            
    except Exception as e:
        logger.error("❌ WhatsApp template sender error: %s", e)
        return {"error": str(e)}


def _send_whatsapp_buttons(user_id: str, body_text: str, buttons: list):
    """
    Send an interactive button message via WhatsApp Cloud API.
    
    Args:
        user_id: The recipient's WhatsApp ID
        body_text: The main message text
        buttons: List of button objects with 'type', 'reply', and 'id' fields
    """
    # Log the body text with button metadata
    # Content: clean text for display
    # Metadata: structured button data for app logic
    button_metadata = {
        "type": "buttons",
        "options": [
            {
                "id": btn.get("reply", {}).get("id", ""),
                "title": btn.get("reply", {}).get("title", "")
            }
            for btn in buttons
        ]
    }
    _log_to_history(user_id, body_text, metadata=button_metadata)

    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.warning("WHATSAPP: Missing credentials for buttons")
        logger.warning("WHATSAPP_API_TOKEN present: %s", bool(WHATSAPP_API_TOKEN))
        logger.warning("WHATSAPP_PHONE_NUMBER_ID present: %s", bool(WHATSAPP_PHONE_NUMBER_ID))
        return

    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": buttons
            }
        }
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        logger.info("WHATSAPP BUTTONS Response: %s - %s", response.status_code, response.text)
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {})
            if error_msg.get('code') == 10:
                logger.error("❌ WhatsApp API Permission Error (#10): %s", error_msg.get('message', 'OAuthException'))
                logger.error("   This usually means:")
                logger.error("   1. Access token is expired or invalid")
                logger.error("   2. Token doesn't have 'whatsapp_business_messaging' permission")
                logger.error("   3. Phone number ID is incorrect")
                logger.error("   4. App needs to be re-authorized in Meta Business Suite")
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("Error sending interactive buttons: %s", e)
    except Exception as e:
        logger.error("Error sending interactive buttons: %s", e)


def _send_whatsapp_call_button(user_id: str, body_text: str, phone_number: str, call_button_title: str = "📞 Call Voice Agent"):
    """
    Send an interactive message with a native WhatsApp 'voice_call' button.

    When the user taps this button, WhatsApp immediately initiates an in-app
    voice call to `phone_number` (the business number). The call is received by
    server.js which bridges it to LiveKit and the Python agent.

    Args:
        user_id:            Recipient's WhatsApp ID
        body_text:          Main message text shown above the button
        phone_number:       Business phone number to call (e.g. '+919082131232')
        call_button_title:  Button label shown to user (max 20 chars)
    """
    _log_to_history(user_id, body_text, metadata={"type": "call_button", "phone": phone_number, "title": call_button_title})

    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.warning("WHATSAPP: Missing credentials for call button")
        return

    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}

    # WhatsApp native voice_call interactive message triggers an in-app voice call to the business
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "interactive",
        "interactive": {
            "type": "voice_call",
            "body": {"text": body_text},
            "action": {
                "name": "voice_call",
                "parameters": {
                    "display_text": call_button_title[:20]
                }
            }
        }
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        logger.info("WHATSAPP CALL BUTTON Response: %s - %s", response.status_code, response.text)
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            logger.error("❌ WhatsApp call button error: %s", error_data.get("error", response.text))
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("Error sending call button: %s", e)
    except Exception as e:
        logger.error("Error sending call button: %s", e)


def _send_whatsapp_cta_url(user_id: str, body_text: str, button_text: str, url: str, footer_text: str = None):
    """
    Send a WhatsApp CTA URL button message (interactive type: cta_url).
    When the user taps the button, the URL is opened directly.

    Use wa.me/<phone>?type=call to trigger a direct phone call.

    Args:
        user_id:      Recipient's WhatsApp ID
        body_text:    Main message text
        button_text:  Label on the CTA button
        url:          URL to open when button is tapped (e.g. https://wa.me/919082131233?type=call)
        footer_text:  Optional footer text below the message
    """
    _log_to_history(user_id, f"{body_text}\n[CTA: {button_text} → {url}]")

    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):

        logger.warning("WHATSAPP: Missing credentials for CTA URL button")
        return

    api_url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}

    interactive_block: dict = {
        "type": "cta_url",
        "body": {"text": body_text},
        "action": {
            "name": "cta_url",
            "parameters": {
                "display_text": button_text,
                "url": url,
            },
        },
    }
    if footer_text:
        interactive_block["footer"] = {"text": footer_text}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "interactive",
        "interactive": interactive_block,
    }

    try:
        response = httpx.post(api_url, headers=headers, json=payload, timeout=10.0)
        logger.info("WHATSAPP CTA URL Response: %s - %s", response.status_code, response.text)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("Error sending CTA URL button: %s", e)
    except Exception as e:
        logger.error("Error sending CTA URL button: %s", e)


def _send_whatsapp_list(user_id: str, body_text: str, button_text: str, sections: list, header_text: str = None, footer_text: str = None):
    """
    Send an interactive list message via WhatsApp Cloud API.
    
    Args:
        user_id: The recipient's WhatsApp ID
        body_text: The main message text
        button_text: Text displayed on the button that opens the list
        sections: List of sections, each with a title and rows
        header_text: Optional text for the header
        footer_text: Optional text for the footer
    """
    # Log the body text with list metadata
    # Content: clean text for display
    # Metadata: structured list data for app logic
    list_metadata = {
        "type": "list",
        "button_text": button_text,
        "header_text": header_text,
        "footer_text": footer_text,
        "sections": [
            {
                "title": section.get("title", ""),
                "rows": [
                    {
                        "id": row.get("id", ""),
                        "title": row.get("title", ""),
                        "description": row.get("description", "")
                    }
                    for row in section.get("rows", [])
                ]
            }
            for section in sections
        ]
    }
    _log_to_history(user_id, body_text, metadata=list_metadata)

    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.warning("WHATSAPP: Missing credentials for list")
        return

    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}", "Content-Type": "application/json"}
    
    # Build the interactive payload
    interactive_payload = {
        "type": "list",
        "header": {"type": "text", "text": header_text},
        "body": {"text": body_text},
        "action": {
            "button": button_text,
            "sections": sections
        }
    }
    
    # Add header if provided
    if header_text:
        interactive_payload["header"] = {"type": "text", "text": header_text}
    
    # Add footer if provided
    if footer_text:
        interactive_payload["footer"] = {"text": footer_text}
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "interactive",
        "interactive": interactive_payload
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        logger.info("WHATSAPP LIST Response: %s - %s", response.status_code, response.text)
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {})
            if error_msg.get('code') == 10:
                logger.error("❌ WhatsApp API Permission Error (#10): %s", error_msg.get('message', 'OAuthException'))
                logger.error("   This usually means:")
                logger.error("   1. Access token is expired or invalid")
                logger.error("   2. Token doesn't have 'whatsapp_business_messaging' permission")
                logger.error("   3. Phone number ID is incorrect")
                logger.error("   4. App needs to be re-authorized in Meta Business Suite")
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error("Error sending interactive list: %s", e)
    except Exception as e:
        logger.error("Error sending interactive list: %s", e)