import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional, List

from app.api.v1.constants import (
    KEY_CONVERSATION_HISTORY, 
    KEY_FULL_CHAT_HISTORY,
    KEY_USER_ID,
    KEY_USER_MSG,
    KEY_LAST_QUESTION,
    KEY_JOURNEY_HISTORY
)
from app.api.v1.http_client import HTTPClient
from app.services.crm.sessions import SESSIONS, save_session, load_user_session, save_session_to_file, fetch_order_details, extract_order_details
from app.services.whatsapp.client import send_whatsapp_message, send_whatsapp_message_async
from app.services.whatsapp.parser import extract_age
from app.services.rag.qna import MedicalGuardrails, EmergencyDetector

logger = logging.getLogger(__name__)

async def handle_interruption(user_id: str, state: dict, user_msg: str, response_message: str, trigger_type: str) -> None:
    """
    Handles emergency or guardrail interruption by sending a response
    and logging to history.
    """
    await send_whatsapp_message_async(user_id, response_message)
    
    # Ensure history lists exist
    if KEY_CONVERSATION_HISTORY not in state:
        state[KEY_CONVERSATION_HISTORY] = []
    if KEY_FULL_CHAT_HISTORY not in state:
        state[KEY_FULL_CHAT_HISTORY] = []

    state[KEY_CONVERSATION_HISTORY].append({"role": "user", "content": user_msg})
    state[KEY_CONVERSATION_HISTORY].append({"role": "assistant", "content": response_message})
    state[KEY_FULL_CHAT_HISTORY].append({"role": "user", "content": user_msg, "timestamp": datetime.now().isoformat()})
    state[KEY_FULL_CHAT_HISTORY].append({"role": "assistant", "content": response_message, "timestamp": datetime.now().isoformat()})
    
    SESSIONS[user_id] = state
    # We use save_session_to_file here as a safe default.
    save_session_to_file(user_id, state)


async def _run_callback(callback: Callable, *args):
    """Helper to run a callback whether it is sync or async."""
    if asyncio.iscoroutinefunction(callback):
        await callback(*args)
    else:
        await asyncio.to_thread(callback, *args)


async def process_batched_message_util(
    user_id: str,
    combined_text: str,
    product_name: str,
    initial_state_template: dict,
    graph: Any,
    field_map: Optional[Dict[str, str]] = None,
    # Hooks
    fast_path_extra_logic: Optional[Callable[[Dict], None]] = None,
    normalize_profiling_logic: Optional[Callable[[Dict], None]] = None,
    clear_profiling_logic: Optional[Callable[[str, Dict], None]] = None,
    special_field_processor: Optional[Callable[[str, Dict, str, str], bool]] = None, # (user_id, state, last_question, text) -> handled
    guardrail_bypass_steps: Optional[set] = None,  # last_question values that should skip API-layer guardrails
):
    """
    Shared utility to process batched messages for AMS, Gut Cleanse, and Free Form agents.
    Handles fast path for new users, existing user loading, guardrails, and graph implementation.
    """
    start_time = time.time()
    logger.info("🔄 Processing message for user %s (Product: %s)", user_id, product_name)
    
    try:
        # Chat flow: ensure interaction_mode for correct node output (WhatsApp vs TTS).
        # Do not downgrade to chat while a LiveKit voice call is active — profile questions
        # belong on the call only; otherwise WhatsApp duplicates UI and confuses users.
        def _ensure_chat_mode(s: dict) -> None:
            if s.get("voice_call_active"):
                s["interaction_mode"] = "voice"
                return
            s["interaction_mode"] = "chat"

        # =====================================================
        # FAST PATH FOR NEW USERS
        # =====================================================
        if user_id not in SESSIONS:
            try:
                # load_user_session is sync (MongoDB), we run it directly as it's typically fast enough,
                # or we could to_thread it if Mongo is slow. Given connection pooling, it's usually fine.
                # But to be safe in async context:
                user_session = await asyncio.to_thread(load_user_session, user_id)
                
                if not user_session:
                    # Brand new user
                    logger.info("🆕 New user %s detected - using fast path", user_id)
                    initial_state = {
                        **initial_state_template,
                        KEY_USER_ID: user_id,
                        KEY_USER_MSG: combined_text,
                        "interaction_mode": "chat",
                        KEY_CONVERSATION_HISTORY: [],
                        KEY_JOURNEY_HISTORY: [],
                        KEY_FULL_CHAT_HISTORY: [{
                            "role": "user", 
                            "content": combined_text,
                            "timestamp": datetime.now().isoformat()
                        }],
                    }

                    # Fast path hook (e.g. for Gut Cleanse order fetch)
                    if fast_path_extra_logic:
                        try:
                            await _run_callback(fast_path_extra_logic, initial_state)
                        except Exception as e:
                            logger.error("⚠️ Error in fast_path_extra_logic: %s", e)
                    
                    # Update product if modified by hook, otherwise use default
                    final_product = initial_state.get("product", product_name)
                    
                    # Save
                    SESSIONS[user_id] = initial_state
                    await asyncio.to_thread(save_session, user_id, final_product, initial_state)
                    
                    # Run Graph
                    # graph.stream is typically sync (LangGraph default). We run it in executor.
                    def run_graph_sync(state_input):
                        events = []
                        for event in graph.stream(state_input):
                            events.append(event)
                        return events

                    graph_events = await asyncio.to_thread(run_graph_sync, initial_state)
                    final_state = graph_events[-1] if graph_events else None
                    
                    if final_state:
                         last_node = list(final_state.keys())[0]
                         graph_state = final_state[last_node]
                         
                         # Merge back
                         if user_id not in SESSIONS:
                             SESSIONS[user_id] = {}
                         for k, v in graph_state.items():
                             SESSIONS[user_id][k] = v
                         SESSIONS[user_id][KEY_USER_ID] = user_id
                         
                         await asyncio.to_thread(save_session, user_id, final_product, SESSIONS[user_id])
                         
                         logger.info("✅ Fast path completed for %s in %.2fs", user_id, time.time() - start_time)
                    return
                
                else:
                    SESSIONS[user_id] = user_session
                    _ensure_chat_mode(SESSIONS[user_id])
                    logger.info("✅ Loaded session from DB for %s", user_id)
            except Exception as e:
                logger.exception("⚠️ Error in fast path check/load for user %s: %s", user_id, e)
                # Fallthrough to normal flow
        
        # =====================================================
        # EXISTING USER FLOW
        # =====================================================
        
        # Get state (fallback to template if missing though should be loaded by now)
        state = SESSIONS.get(user_id)
        if not state:
            state = {
                **initial_state_template,
                KEY_USER_ID: user_id,
                KEY_CONVERSATION_HISTORY: [],
                KEY_FULL_CHAT_HISTORY: [],
            }
            if user_id not in SESSIONS:
                 SESSIONS[user_id] = state
        
        state[KEY_USER_MSG] = combined_text
        
        # Ensure full_chat_history exists
        if KEY_FULL_CHAT_HISTORY not in state:
            state[KEY_FULL_CHAT_HISTORY] = []
            
        # Append user message to full history
        state[KEY_FULL_CHAT_HISTORY].append({
            "role": "user", 
            "content": combined_text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Hooks: Profiling Normalization & Clearing
        if normalize_profiling_logic:
            try:
                await _run_callback(normalize_profiling_logic, state)
            except Exception as e:
                logger.error("Error in normalize_profiling_logic: %s", e)

        if clear_profiling_logic:
            try:
                await _run_callback(clear_profiling_logic, user_id, state)
            except Exception as e:
                 logger.error("Error in clear_profiling_logic: %s", e)

        # =====================================================
        # GUARDRAILS
        # =====================================================
        # Skip guardrails for structured list/button steps where the user is
        # selecting a system-provided option (not asking a free-form health question).
        # Without this bypass, options like "Recent Surgery" or "Kidney Disease"
        # match guardrail patterns and stop the flow before the router runs.
        _current_step = state.get(KEY_LAST_QUESTION)
        _bypass_guardrails = bool(
            guardrail_bypass_steps is not None and _current_step in guardrail_bypass_steps
        )

        try:
            # 1. ALWAYS check emergency first (Even if medical guardrail is bypassed)
            def check_emergency():
                detector = EmergencyDetector()
                return detector.detect_emergency(combined_text)

            is_emergency, _, _, emergency_response = await asyncio.to_thread(check_emergency)

            if is_emergency:
                await handle_interruption(user_id, state, combined_text, emergency_response, "🚨 Emergency")
                return

            # 2. Skip MEDICAL guardrail only if bypass is active
            if _bypass_guardrails:
                logger.info("⏭️  Guardrail bypass active for step '%s' (structured flow answer)", _current_step)
            else:
                def check_medical():
                    mg = MedicalGuardrails()
                    ctx = {
                        "health_conditions": state.get("health_conditions", ""),
                        "allergies": state.get("allergies", ""),
                        "medications": state.get("medications", ""),
                        "supplements": state.get("supplements", ""),
                        "gut_health": state.get("gut_health", "")
                    }
                    return mg.check_guardrails(combined_text, ctx)

                guardrail_triggered, guardrail_type, guardrail_response = await asyncio.to_thread(check_medical)

                if guardrail_triggered:
                    await handle_interruption(user_id, state, combined_text, guardrail_response, f"🛡️ Guardrail triggered ({guardrail_type})")
                    return
        except Exception as e:
            logger.error("Guardrail check failed: %s", e)

        # =====================================================
        # FIELD EXTRACTION
        # =====================================================
        last_question = state.get(KEY_LAST_QUESTION)
        
        handled = False
        if special_field_processor:
             # This hook returns a bool, need to handle return value
             if asyncio.iscoroutinefunction(special_field_processor):
                 handled = await special_field_processor(user_id, state, last_question, combined_text)
             else:
                 handled = await asyncio.to_thread(special_field_processor, user_id, state, last_question, combined_text)
        
        if not handled:
            # Default Age extraction
            if last_question == "age":
                extracted_age = extract_age(combined_text)
                state["age"] = extracted_age if extracted_age else combined_text
            
            # Direct Mapping
            elif field_map and last_question in field_map:
                field = field_map[last_question]
                state[field] = combined_text
        
        # =====================================================
        # UPDATE & RUN GRAPH
        # =====================================================
        try:
            _ensure_chat_mode(state)
            SESSIONS[user_id] = state
            await asyncio.to_thread(save_session, user_id, product_name, state)
            
            def run_graph_sync(state_input):
                 events = []
                 for event in graph.stream(state_input):
                     events.append(event)
                 return events

            graph_events = await asyncio.to_thread(run_graph_sync, state)
            final_state = graph_events[-1] if graph_events else None
            
            if final_state:
                last_node = list(final_state.keys())[0]
                new_state = final_state[last_node]
                
                # Merge
                for k, v in new_state.items():
                    SESSIONS[user_id][k] = v
                if KEY_USER_ID not in SESSIONS[user_id]:
                    SESSIONS[user_id][KEY_USER_ID] = user_id
                
                await asyncio.to_thread(save_session, user_id, product_name, SESSIONS[user_id])
                logger.info("✅ Graph execution completed for %s", user_id)
                
        except Exception as e:
            logger.exception("Error running graph for user %s: %s", user_id, e)
            # Ensure saved even on error?
            await asyncio.to_thread(save_session, user_id, product_name, SESSIONS[user_id])
            
    except Exception as e:
        # Simplified Error Logging as requested
        logger.exception("❌ Error processing message for user %s: %s", user_id, e)

