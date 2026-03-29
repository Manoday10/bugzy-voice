"""
Chat handler for REST API integration.

This module provides message collection and processing logic for REST API requests,
using context variables (contextvars) for message collection without modifying WhatsApp functionality.
"""

from typing import List, Optional, Dict, Any
from app.api.v1.orchestrator import get_product_module
from app.services.crm.sessions import SESSIONS, save_session_to_file, load_user_session
from app.services.whatsapp import client as whatsapp_client

import logging
logger = logging.getLogger(__name__)


def process_chat_message(
    user_id: str,
    message: str,
    conversation_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a chat message and collect the response without sending to WhatsApp.

    This function uses context variables (contextvars) to intercept messages
    without modifying the global WHATSAPP_SENDER configuration.

    Args:
        user_id: The user's ID
        message: The message text from the user
        conversation_id: Optional conversation ID (appended to user_id for session key)
        context: Optional context object with recent_messages

    Returns:
        Dict containing:
        - messages: List of structured message dicts with role, content, timestamp, metadata
        - joined_response: All messages joined with double newlines (for backward compat)
    """
    # Create a list to collect messages in this context
    message_list: List[str] = []
    
    try:
        # Set the context-local message collector
        # The WhatsApp client will check for this and collect instead of send
        whatsapp_client.set_message_collector(message_list)

        session_key = user_id  # user_id = phone number
        
        old_session_key = None
        old_saved = None
        if conversation_id:
            old_session_key = f"{user_id}_{conversation_id}"
            if old_session_key not in SESSIONS:
                # Try loading old composite key from DB
                old_saved = load_user_session(old_session_key)
        
        # Get or create session state using unified phone-based key
        if session_key not in SESSIONS:
            # Try to load from persistent storage first
            saved_session = load_user_session(session_key)
            
            if saved_session:
                # Resume from saved session
                SESSIONS[session_key] = saved_session
            else:
                # Create new session
                SESSIONS[session_key] = {
                    "user_id": session_key,
                    "conversation_history": [],
                    "journey_history": [],
                    "current_agent": None,
                }
        
        if old_session_key and old_session_key != session_key:
            old_session = None
            if old_session_key in SESSIONS:
                old_session = SESSIONS[old_session_key]
            elif old_saved:
                # Use the already-loaded session from above
                old_session = old_saved
            else:
                old_session = load_user_session(old_session_key)
            
            if old_session:
                # Merge conversation_history (avoid duplicates)
                old_history = old_session.get("conversation_history", [])
                current_history = SESSIONS[session_key].get("conversation_history", [])
                
                # Merge histories, avoiding duplicates
                for old_msg in old_history:
                    if old_msg not in current_history:
                        current_history.append(old_msg)
                
                SESSIONS[session_key]["conversation_history"] = current_history
                
                # Merge full_chat_history if exists
                old_full_history = old_session.get("full_chat_history", [])
                current_full_history = SESSIONS[session_key].get("full_chat_history", [])
                
                for old_msg in old_full_history:
                    # Check if message already exists (by role, content, timestamp)
                    exists = any(
                        msg.get("role") == old_msg.get("role") and
                        msg.get("content") == old_msg.get("content") and
                        msg.get("timestamp") == old_msg.get("timestamp")
                        for msg in current_full_history
                    )
                    if not exists:
                        current_full_history.append(old_msg)
                
                SESSIONS[session_key]["full_chat_history"] = current_full_history
                
                # Update other fields if not already set
                for key in ["user_name", "phone_number", "current_agent", "last_question"]:
                    if key not in SESSIONS[session_key] and key in old_session:
                        SESSIONS[session_key][key] = old_session[key]
        
        # Store conversation_id as metadata if provided
        if conversation_id:
            if "conversation_ids" not in SESSIONS[session_key]:
                SESSIONS[session_key]["conversation_ids"] = []
            if conversation_id not in SESSIONS[session_key]["conversation_ids"]:
                SESSIONS[session_key]["conversation_ids"].append(conversation_id)
            SESSIONS[session_key]["active_conversation_id"] = conversation_id
        
        # Merge provided context if available
        if context and context.get("recent_messages"):
            # Update conversation history with provided context
            # Only add if not already present (avoid duplicates)
            existing_history = SESSIONS[session_key].get("conversation_history", [])
            
            # Convert recent_messages to the format expected by the system
            for ctx_msg in context["recent_messages"]:
                # Check if this message already exists in history
                already_exists = any(
                    h.get("role") == ctx_msg.get("role") and 
                    h.get("content") == ctx_msg.get("content")
                    for h in existing_history
                )
                
                if not already_exists:
                    existing_history.append({
                        "role": ctx_msg.get("role"),
                        "content": ctx_msg.get("content")
                    })
            
            SESSIONS[session_key]["conversation_history"] = existing_history
        
        # Set current message
        SESSIONS[session_key]["user_msg"] = message
        
        # Add current user message to conversation history
        if SESSIONS[session_key].get("conversation_history") is None:
            SESSIONS[session_key]["conversation_history"] = []
        
        user_message = {
            "role": "user",
            "content": message
        }
        SESSIONS[session_key]["conversation_history"].append(user_message)
        
        # Log user message to full_chat_history with source="app"
        if SESSIONS[session_key].get("full_chat_history") is None:
            SESSIONS[session_key]["full_chat_history"] = []
        
        from datetime import datetime
        SESSIONS[session_key]["full_chat_history"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
            "source": "app"  # Track that this message came from the app
        })
        
        product_module = get_product_module(user_id)
        graph = product_module.graph
        SESSIONS[session_key]["interaction_mode"] = "chat"
        result = graph.invoke(SESSIONS[session_key])
        
        # Update session with result
        SESSIONS[session_key].update(result)
        
        # Log assistant responses to full_chat_history with source="app"
        # The graph may have already logged some messages via _log_to_history, but we ensure all collected messages are logged
        if message_list:
            if SESSIONS[session_key].get("full_chat_history") is None:
                SESSIONS[session_key]["full_chat_history"] = []
            
            from datetime import datetime
            for msg in message_list:
                # Check if this message was already logged (avoid duplicates)
                already_logged = any(
                    h.get("content") == msg and h.get("role") == "assistant" and h.get("source") == "app"
                    for h in SESSIONS[session_key]["full_chat_history"]
                )
                if not already_logged:
                    SESSIONS[session_key]["full_chat_history"].append({
                        "role": "assistant",
                        "content": msg,
                        "timestamp": datetime.now().isoformat(),
                        "source": "app"  # Track that this response came from app interaction
                    })
        
        # Save session to persistent storage
        save_session_to_file(session_key, SESSIONS[session_key])

        # Build structured messages array for REST API response
        structured_messages = []
        for msg in message_list:
            structured_messages.append({
                "role": "assistant",
                "content": msg,
                "timestamp": datetime.now().isoformat(),
                "metadata": None
            })

        # Return structured response dict
        return {
            "messages": structured_messages,
            "joined_response": "\n\n".join(message_list)
        }
    
    except Exception as e:
        raise

    finally:
        # Always clear the message collector for this context
        whatsapp_client.clear_message_collector()


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string.
    Uses a simple approximation: ~4 characters per token.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated token count
    """
    return len(text) // 4


def process_image_analysis(
    user_id: str,
    image_url: str,
    message: str,
    conversation_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process an image analysis request using SNAP food analysis.

    This is a stateless function that uses the SNAP service to perform
    food classification and nutritional analysis.

    Note: The 'message' parameter is accepted for API compatibility but
    SNAP performs automated food analysis regardless of the user's question.

    Args:
        user_id: The user's ID (for logging/tracking)
        image_url: URL of the image to analyze
        message: User's question (informational only, not used by SNAP)
        conversation_id: Optional conversation ID (for context tracking)
        context: Optional context with recent_messages
        auth_token: Optional authentication token for image download

    Returns:
        Dict containing:
        - response: str (formatted food analysis from SNAP)
        - confidence: float (0.0-1.0)
        - intent: str (category-based: food_prepared, food_raw, non_food)
        - metadata: dict with SNAP validation details
        - error: Optional error message
    """
    from app.services.image_analysis import analyze_image_with_snap

    logger.info("🖼️ Processing SNAP food analysis for user: %s | Image URL: %s | Message: %s%s", user_id, image_url, message, f" | Context messages: {len(context.get('recent_messages', []))}" if context else "")
    # Perform SNAP food analysis
    result = analyze_image_with_snap(
        image_url=image_url,
        auth_token=auth_token
    )

    return result


def process_food_tracker_request(
    image_url: str,
    user_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a Food Tracker request.
    
    Downloads image and uses SNAP tracker analysis to return strict JSON macros.
    """
    from app.services.image_analysis.downloader import download_image_from_url, cleanup_temp_file
    from app.services.snap.analyzer import analyze_food_tracker_image
    
    logger.info("🥗 Processing Food Tracker request for user: %s", user_id)
    
    temp_file_path = None
    try:
        # 1. Download Image
        temp_file_path, _ = download_image_from_url(
            image_url=image_url,
            auth_header=auth_token,
            timeout=15,
            max_size_mb=10
        )
        
        # 2. Analyze
        result = analyze_food_tracker_image(temp_file_path)
        
        if result.get("error"):
            raise Exception(result["error"])
            

        
        if not result.get("success"):
            raise Exception("Analysis failed")
            
        # 3. Format Response
        data = result.get("data", {})
        
        # Ensure numerical values are parsed safely
        def safe_float(val):
            try:
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    # Remove non-numeric characters except dot
                    clean_val = "".join(c for c in val if c.isdigit() or c == '.')
                    return float(clean_val) if clean_val else None
                return None
            except Exception:
                return None

        return {
            "success": True,
            "data": {
                "food_name": data.get("food_name"),
                "calories": safe_float(data.get("calories")),
                "protein": safe_float(data.get("protein")),
                "fiber": safe_float(data.get("fiber")),
                "fat": safe_float(data.get("fat"))
            },
            "confidence": 0.9,
            "metadata": result.get("metadata", {})
        }

        
    except Exception as e:
        logger.error("❌ Food Tracker Process Error: %s", e)
        # Re-raise exception to be handled by the route
        raise e
        
    finally:
        if temp_file_path:
            cleanup_temp_file(temp_file_path)



def get_chat_history_by_phone(
    phone_number: str,
    conversation_id: Optional[str] = None,
    source: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Get chat history for a user by their phone number with optional filtering and pagination.
    
    Args:
        phone_number: The user's phone number
        conversation_id: Optional conversation ID to filter by
        source: Optional source filter ("whatsapp" or "app")
        limit: Optional limit on number of messages returned
        offset: Pagination offset (default: 0)
        
    Returns:
        Dict containing:
        - success: bool
        - user_id: str (if found)
        - phone_number: str
        - user_name: str (if available)
        - conversation_history: list of chat messages
        - full_chat_history: complete chat history with timestamps (filtered/paginated)
        - total_messages: int (total before filtering/pagination)
        - last_updated: str (if available)
        - error: str (if not found or error occurred)
    """
    from app.services.crm.sessions import get_user_session_by_phone
    
    try:
        
        # Get user session from MongoDB
        session = get_user_session_by_phone(phone_number)
        
        if not session:
            return {
                "success": False,
                "error": f"No user found with phone number {phone_number}"
            }
        
        # Extract relevant fields
        user_id = session.get("user_id", "")
        user_name = session.get("user_name")
        conversation_history = session.get("conversation_history", [])
        full_chat_history = session.get("full_chat_history", [])
        last_updated = session.get("last_updated")
        
        # Ensure backward compatibility: add source="whatsapp" to messages without source
        # Check if any messages need source migration
        needs_source_migration = any("source" not in msg for msg in full_chat_history)
        
        # Create a deep copy for filtering to avoid mutating cached session
        import copy
        filtered_history = copy.deepcopy(full_chat_history)
        
        # Add source defaults to the copy for filtering
        for msg in filtered_history:
            if "source" not in msg:
                msg["source"] = "whatsapp"  # Default for legacy messages
        
        # If migration needed, update the original session and persist
        if needs_source_migration:
            # Update the session's full_chat_history with source defaults
            for msg in full_chat_history:
                if "source" not in msg:
                    msg["source"] = "whatsapp"
            
            # Update cached session if it exists
            if user_id in SESSIONS:
                SESSIONS[user_id]["full_chat_history"] = full_chat_history
            
            # Persist the update to MongoDB
            from app.services.crm.sessions import save_session_to_file
            save_session_to_file(user_id, session)
        
        # Apply filters (filtered_history already has source defaults applied)
        
        # Filter by conversation_id if provided (if conversation_id is stored in message metadata)
        # Note: Currently conversation_id is stored at session level, not message level
        # This is a placeholder for future enhancement
        if conversation_id:
            # For now, we can't filter by conversation_id at message level
            # This would require storing conversation_id in each message
            pass
        
        # Filter by source if provided
        if source:
            filtered_history = [msg for msg in filtered_history if msg.get("source") == source]
        
        # Sort by timestamp (oldest first for chronological order)
        filtered_history.sort(key=lambda x: x.get("timestamp", ""))
        
        # Store total before pagination
        total_messages = len(filtered_history)
        
        # Apply pagination - take most recent messages (from the end)
        # For chat UI, we want the latest messages, not the oldest
        if limit and len(filtered_history) > limit:
            # Skip offset from the end, then take limit
            start_index = max(0, total_messages - limit - offset)
            end_index = total_messages - offset if offset > 0 else total_messages
            filtered_history = filtered_history[start_index:end_index]
        elif offset > 0:
            filtered_history = filtered_history[:-offset] if offset < len(filtered_history) else []
        
        return {
            "success": True,
            "user_id": user_id,
            "phone_number": phone_number,
            "user_name": user_name,
            "conversation_history": conversation_history,
            "full_chat_history": filtered_history,
            "total_messages": total_messages,
            "last_updated": last_updated
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Error fetching chat history: {str(e)}"
        }


def get_messages_since(
    user_id: str,
    since_timestamp: str,
    source: Optional[str] = "app"
) -> Dict[str, Any]:
    """
    Get assistant messages for a user that were logged after a given timestamp.
    
    Args:
        user_id: The user's ID (phone number with country code)
        since_timestamp: ISO-8601 timestamp - only return messages after this time
        source: Optional source filter ("app" or "whatsapp")
        
    Returns:
        Dict containing:
        - success: bool
        - messages: list of assistant message dicts
        - total_count: int
        - error: str (if error occurred)
    """
    try:
        from datetime import datetime
        
        # Parse the since_timestamp
        try:
            since_dt = datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid timestamp format: {since_timestamp}"
            }
        
        # Get session from memory or DB
        session = SESSIONS.get(user_id)
        if not session:
            session = load_user_session(user_id)
        
        if not session:
            return {
                "success": True,
                "messages": [],
                "total_count": 0
            }
        
        full_chat_history = session.get("full_chat_history", [])
        
        # Filter for assistant messages after the given timestamp
        filtered_messages = []
        for msg in full_chat_history:
            # Only include assistant messages
            if msg.get("role") != "assistant":
                continue
            
            # Filter by source if specified
            msg_source = msg.get("source", "whatsapp")
            if source and msg_source != source:
                continue
            
            # Filter by timestamp
            msg_timestamp = msg.get("timestamp", "")
            if msg_timestamp:
                try:
                    msg_dt = datetime.fromisoformat(msg_timestamp.replace('Z', '+00:00'))
                    if msg_dt > since_dt:
                        filtered_messages.append(msg)
                except ValueError:
                    # Skip messages with invalid timestamps
                    continue
        
        # Sort by timestamp (oldest first)
        filtered_messages.sort(key=lambda x: x.get("timestamp", ""))
        
        return {
            "success": True,
            "messages": filtered_messages,
            "total_count": len(filtered_messages)
        }
    
    except Exception as e:
        return {
            "success": False,
            "messages": [],
            "total_count": 0,
            "error": f"Error fetching messages: {str(e)}"
        }
