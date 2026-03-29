"""
Context Manager for Bugzy Gut Cleanse Chatbot.

This module handles the construction of optimized, intent-aware context for the LLM.
It creates a modular, token-efficient context by selectively including information
based on the user's detected intent and current conversation state.
"""

import logging
from typing import List, Dict, Optional

from app.services.chatbot.bugzy_gut_cleanse.state import State
from app.services.crm.sessions import load_meal_plan
from app.services.chatbot.bugzy_shared.context import (
    build_profile_memory_from_mapping,
    detect_user_intent,
    detect_followup_question,
    INTENT_MEAL,
    INTENT_PRODUCT,
    INTENT_HEALTH,
    INTENT_GENERAL,
    DEFAULT_PRODUCT_KEYWORDS,
    DEFAULT_HEALTH_KEYWORDS
)


def build_profile_memory(state: State) -> str:
    """Extract ONLY essential demographics + critical health info + NEW 11-QUESTION MEAL PLAN fields.
    
    Include: name, allergies, supplements, digestive_issues
    And New Meal Plan Fields: dietary_preference, cuisine_preference, food_allergies_intolerances, etc.
    
    Returns: Semicolon-separated string.
    """
    mapping = [
        {"key": "user_name", "label": "Name"},
        {"key": "supplements", "label": "Supplements"},
        {"key": "digestive_issues", "label": "Digestive Issues"},
        {"key": "specific_health_condition", "label": "Specific Condition"},
        {"key": "health_safety_status", "label": "Safety Status"},
        {"key": "detox_experience", "label": "Detox Exp"},
        {"key": "detox_recent_reason", "label": "Recent Detox Reason", "include_if": "detox_experience"},
        {"key": "dietary_preference", "label": "Dietary Preference"},
        {"key": "cuisine_preference", "label": "Cuisine Preference"},
        {"key": "food_allergies_intolerances", "label": "Allergies/Intolerances"},
        {"key": "daily_eating_pattern", "label": "Daily Eating Pattern"},
        {"key": "foods_avoid", "label": "Foods Avoid"},
        {"key": "hydration", "label": "Hydration"},
        {"key": "other_beverages", "label": "Other Beverages"},
        {"key": "gut_sensitivity", "label": "Gut Sensitivity"},
    ]
    
    return build_profile_memory_from_mapping(state, mapping)

def build_system_memory(state: State) -> str:
    """Track current journey phase & completion status.
    
    Returns: Compact summary string.
    """
    parts = []
    
    # Current Phase
    current_node = state.get("pending_node") or state.get("current_agent") or "onboarding"
    parts.append(f"Phase: {current_node}")
    
    # Plan Status (Detailed to prevent hallucinations)
    if state.get("meal_plan_sent"):
         parts.append("Meal plan: Active (7-Day Gut Cleanse Plan)")
    else:
         parts.append("Meal plan: Not created yet")
         
    # Explicitly clarify exercise plan status to prevent hallucinations
    parts.append("Exercise plan: Not supported (Gut Cleanse focuses on rest & nutrition)")
    
    return "; ".join(parts)

def build_plan_memory(state: State, intent: str, max_chars: int = 3000) -> str:
    """Load meal plan ONLY if relevant to intent.
    
    Intent-gating logic:
    - 'meal' intent → load meal_day{1-7}_plan (truncate to max_chars)
    - Others → return empty string
    
    Returns: Formatted plan string or empty string
    """
    if intent == INTENT_MEAL:
        return _get_meal_plan_content(state, max_chars)
    
    return ""

def _get_meal_plan_content(state: State, max_chars: int) -> str:
    """Helper to extract relevant meal plan days."""
    # Try to get from state first, fallback to DB
    user_id = state.get("user_id", "")
    product = state.get("product", "gut_cleanse")  # Default to gut_cleanse for this module
    meal_plan_db = {}

    # Check if we need to hit DB (if key fields missing in state)
    if not state.get("meal_day1_plan") and not state.get("meal_plan"):
         meal_plan_db = load_meal_plan(user_id, product=product) or {}

    days_content = []
    for d in range(1, 8):
        key = f"meal_day{d}_plan"
        content = state.get(key) or meal_plan_db.get(key)
        if content:
            days_content.append(content)
            
    if not days_content:
        # Fallback to monolithic field
        full_plan = state.get("meal_plan") or meal_plan_db.get("meal_plan") or ""
        return full_plan[:max_chars] if full_plan else ""
        
    # Smart truncation: For now, just join and hard truncate
    # Improvement: Could identify "current day" and prioritize that
    full_text = "\n\n".join(days_content)
    if len(full_text) > max_chars:
        return full_text[:max_chars] + "...[truncated]"
    return full_text

def build_session_memory(state: State, max_messages: int = 6) -> List[Dict]:
    """Retrieve only the most recent N messages.
    
    Returns: List of {"role": str, "content": str} dicts
    """
    history = state.get("conversation_history", []) or []
    if not history:
        return []
        
    # Return last N messages
    return history[-max_messages:]

# detect_followup_question logic moved to shared context module.

def build_conversation_summary(state: State, llm_client) -> str:
    """Compress conversation history into 2-3 sentence summary.
    
    Logic:
    - Check if summary needs update (every 10 messages)
    - Summarize messages since last summary using LLM
    - Update state
    
    Returns: Summary string
    """
    history = state.get("conversation_history", []) or []
    current_count = len(history)
    last_count = state.get("last_summary_message_count", 0)
    existing_summary = state.get("conversation_summary", "")
    
    # Update if we have 10+ new messages OR no summary exists but we have history
    if (current_count - last_count >= 10) or (not existing_summary and len(history) > 5):
        try:
            # We want to summarize the *entire* history if it's the first time,
            # or append to existing summary.
            # For simplicity in this v1, we'll summarize the last 20 messages 
            # and merge with existing summary conceptually or just replace relevant context.
            
            messages_to_summarize = history[-20:] # Look at recent window
            msg_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages_to_summarize])
            
            prompt = (
                "Summarize the key points of this conversation in 2-3 sentences. "
                "Focus on user preferences, key decisions, and current health/diet context. "
                "Ignore chit-chat.\n\n"
                f"Previous Context: {existing_summary}\n\n"
                f"Recent Messages:\n{msg_text}"
            )
            
            response = llm_client.invoke(prompt)
            new_summary = response.content.strip()
            
            # Update state explicitly (calling code needs to persist this)
            state["conversation_summary"] = new_summary
            state["last_summary_message_count"] = current_count
            
            return new_summary
            
        except Exception as e:
            logger.error(f"Error building conversation summary: {e}")
            return existing_summary
            
    return existing_summary

def build_optimized_context(
    state: State,
    user_question: str,
    llm_client,
    intent: Optional[str] = None,
    include_plans: bool = True,
    max_recent_messages: int = 6
) -> str:
    """Main orchestrator: Build minimal, intent-aware context.
    
    Returns: Formatted context string ready for LLM prompt
    """
    # 1. Detect Intent
    if not intent:
        # Use shared intent detection with Gut Cleanse specifics (no exercise)
        # Pass exercise_keywords=[] to disable exercise detection
        intent = detect_user_intent(user_question, state, exercise_keywords=[])
    
    # 1.5. Detect if this is a follow-up question
    conversation_history = state.get("conversation_history", []) or []
    is_followup = detect_followup_question(user_question, conversation_history)
        
    # 2. Build Components
    system_mem = build_system_memory(state)
    profile_mem = build_profile_memory(state)
    
    # 3. Handle Summary (Update if needed)
    # Note: We pass llm_client to allow updates. 
    # Ideally, summary updates should be a separate async job, 
    # but for now we do it inline or on-demand.
    summary_mem = build_conversation_summary(state, llm_client)
    
    # 4. Session Memory (Recent messages)
    # CRITICAL: If this is a follow-up question, increase the window to capture more context
    if is_followup:
        max_recent_messages = max(8, max_recent_messages)
    
    recent_msgs = build_session_memory(state, max_recent_messages)
    recent_msgs_str = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in recent_msgs])
    
    # 5. Plan Memory (Intent Gated)
    plan_mem = ""
    if include_plans:
        plan_mem = build_plan_memory(state, intent)
        
    # 6. Assemble
    context_parts = []
    
    context_parts.append(f"**Session Context**\n{system_mem}")
    
    # NEW: Add Order ONLY if relevant (Intent Gated)
    # This prevents the LLM from over-biasing towards the product when the user follows up
    # on general topics (e.g., "how black coffee helps" -> "what are its benefits").
    # CRITICAL: For follow-up questions, EXCLUDE user order to prevent topic switching
    if state.get("user_order") and intent == INTENT_PRODUCT and not is_followup:
        order_str = f"Order: {state.get('user_order')}"
        if state.get("user_order_date"):
            order_str += f" (Date: {state.get('user_order_date')})"
        context_parts.append(f"**User Order**\n{order_str}")

    context_parts.append(f"**User Profile**\n{profile_mem}")
    
    if summary_mem:
        context_parts.append(f"**Conversation Summary**\n{summary_mem}")
    
    # CRITICAL FIX: For follow-up questions, emphasize recent conversation context
    if recent_msgs_str:
        if is_followup:
            # Add a stronger emphasis for follow-up questions
            context_parts.append(f"**Recent Conversation (IMPORTANT - User is asking a follow-up question)**\n{recent_msgs_str}")
        else:
            context_parts.append(f"**Recent Messages**\n{recent_msgs_str}")
        
    if plan_mem:
        # Add a clear header derived from intent
        plan_title = "Meal Plan"
        context_parts.append(f"**User's {plan_title}**\n{plan_mem}")
        
    return "\n\n".join(context_parts)
