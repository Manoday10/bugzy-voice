"""
Context Manager for Bugzy General Chatbot.

This module handles the construction of optimized, intent-aware context for the LLM.
It creates a modular, token-efficient context by selectively including information
based on the user's detected intent and current conversation state.

Simplified for General chatbot - handles only meal and exercise intents.
"""

import logging
from typing import List, Dict, Optional

from app.services.chatbot.bugzy_general.state import State
from app.services.crm.sessions import load_meal_plan, load_exercise_plan

logger = logging.getLogger(__name__)

# Intent Categories (simplified for General chatbot)
INTENT_MEAL = "meal"
INTENT_EXERCISE = "exercise"
INTENT_GENERAL = "general"

def detect_user_intent(user_question: str, state: State) -> str:
    """Classify user question into intent categories.
    
    Categories: 'meal', 'exercise', 'general'
    Uses keyword matching + fallback to state.get("current_agent")
    
    Returns: Intent string (lowercase)
    """
    if not user_question:
        return INTENT_GENERAL
        
    text = user_question.lower()
    
    # Keyword Lists
    meal_keywords = [
        "meal", "food", "diet", "eat", "recipe", "breakfast", "lunch", "dinner", 
        "snack", "cook", "ingredient", "nutrition", "calorie", "protein", "dish",
        "hungry", "serving", "swap", "substitute", "taste", "paneer", "chicken",
        "veg", "non-veg", "vegan", "tofu", "carb", "fat", "fiber"
    ]
    
    exercise_keywords = [
        "exercise", "workout", "gym", "fitness", "cardio", "strength", "training",
        "run", "walk", "jog", "yoga", "stretch", "muscle", "pain", "sore",
        "recovery", "rep", "set", "weight", "dumbbell", "equipment", "movement",
        "squat", "push", "pull", "plank", "lunge", "burpee"
    ]
    
    # Check for meal/exercise specific keywords
    has_meal = any(k in text for k in meal_keywords)
    has_exercise = any(k in text for k in exercise_keywords)
    
    if has_meal and not has_exercise:
        return INTENT_MEAL
    if has_exercise and not has_meal:
        return INTENT_EXERCISE
        
    # Fallback to current agent context if ambiguous
    current_agent = state.get("current_agent", "")
    if current_agent == "meal_planner":
        return INTENT_MEAL
    elif current_agent == "exercise_planner":
        return INTENT_EXERCISE
        
    # Default
    return INTENT_GENERAL

def build_profile_memory(state: State) -> str:
    """Extract ONLY essential demographics + meal/exercise preferences.

    Include: name, and meal/exercise questionnaire fields
    
    Returns: Semicolon-separated string.
    """
    profile_parts = []

    # Identity
    if state.get("user_name"):
        profile_parts.append(f"Name: {state.get('user_name')}")

    # Meal Plan Questionnaire Fields
    if state.get("dietary_preference"):
        profile_parts.append(f"Dietary Preference: {state.get('dietary_preference')}")
    if state.get("cuisine_preference"):
        profile_parts.append(f"Cuisine Preference: {state.get('cuisine_preference')}")
    if state.get("food_allergies_intolerances"):
        profile_parts.append(f"Allergies/Intolerances: {state.get('food_allergies_intolerances')}")
    if state.get("daily_eating_pattern"):
        profile_parts.append(f"Daily Eating Pattern: {state.get('daily_eating_pattern')}")
    if state.get("foods_avoid"):
        profile_parts.append(f"Foods Avoid: {state.get('foods_avoid')}")
    if state.get("hydration"):
        profile_parts.append(f"Hydration: {state.get('hydration')}")
    if state.get("other_beverages"):
        profile_parts.append(f"Other Beverages: {state.get('other_beverages')}")
    if state.get("gut_sensitivity"):
        profile_parts.append(f"Gut Sensitivity: {state.get('gut_sensitivity')}")

    # Exercise Plan (FITT) Questionnaire Fields
    if state.get("fitness_level"):
        profile_parts.append(f"Fitness Level: {state.get('fitness_level')}")
    if state.get("activity_types"):
        profile_parts.append(f"Activity Types: {state.get('activity_types')}")
    if state.get("exercise_frequency"):
        profile_parts.append(f"Exercise Frequency: {state.get('exercise_frequency')}")
    if state.get("exercise_intensity"):
        profile_parts.append(f"Exercise Intensity: {state.get('exercise_intensity')}")
    if state.get("session_duration"):
        profile_parts.append(f"Session Duration: {state.get('session_duration')}")
    if state.get("sedentary_time"):
        profile_parts.append(f"Sedentary Time: {state.get('sedentary_time')}")
    if state.get("exercise_goals"):
        profile_parts.append(f"Exercise Goals: {state.get('exercise_goals')}")

    return "; ".join(profile_parts)

def build_system_memory(state: State) -> str:
    """Track current journey phase & completion status.
    
    Returns: Compact summary string.
    """
    parts = []
    
    # Current Phase
    current_node = state.get("pending_node") or state.get("current_agent") or "onboarding"
    parts.append(f"Phase: {current_node}")
    
    # Plan Status
    meal_status = "✅" if state.get("meal_plan_sent") else "❌"
    exercise_status = "✅" if state.get("exercise_plan_sent") else "❌"
    parts.append(f"Meal plan: {meal_status}")
    parts.append(f"Ex plan: {exercise_status}")
    
    return "; ".join(parts)

def build_plan_memory(state: State, intent: str, max_chars: int = 3000) -> str:
    """Load meal OR exercise plan ONLY if relevant to intent.
    
    Intent-gating logic:
    - 'meal' intent → load meal_day{1-7}_plan (truncate to max_chars)
    - 'exercise' intent → load day{1-7}_plan (truncate to max_chars)
    - Others → return empty string
    
    Returns: Formatted plan string or empty string
    """
    if intent == INTENT_MEAL:
        return _get_meal_plan_content(state, max_chars)
    elif intent == INTENT_EXERCISE:
        return _get_exercise_plan_content(state, max_chars)
    
    return ""

def _get_meal_plan_content(state: State, max_chars: int) -> str:
    """Helper to extract relevant meal plan days."""
    # Try to get from state first, fallback to DB
    user_id = state.get("user_id", "")
    product = "general"  # Use "general" product for this module
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

def _get_exercise_plan_content(state: State, max_chars: int) -> str:
    """Helper to extract relevant exercise plan days."""
    user_id = state.get("user_id", "")
    product = "general"  # Use "general" product for this module
    ex_plan_db = {}

    if not state.get("day1_plan") and not state.get("exercise_plan"):
        ex_plan_db = load_exercise_plan(user_id, product=product) or {}
        
    days_content = []
    for d in range(1, 8):
        key = f"day{d}_plan"
        content = state.get(key) or ex_plan_db.get(key)
        if content:
            days_content.append(content)
            
    if not days_content:
        full_plan = state.get("exercise_plan") or ex_plan_db.get("exercise_plan") or ""
        return full_plan[:max_chars] if full_plan else ""
        
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

def detect_followup_question(user_question: str, conversation_history: List[Dict]) -> bool:
    """Detect if the current question is a follow-up to the previous conversation.
    
    This handles meal and exercise topic follow-ups.
    
    Returns: True if this appears to be a follow-up question
    """
    if not conversation_history or len(conversation_history) < 2:
        return False
    
    user_msg_lower = user_question.lower()
    
    # Strong follow-up indicators (high confidence)
    strong_followup_patterns = [
        # Direct follow-up phrases
        'breakdown', 'break down', 'explain more', 'tell me more', 'more about',
        'what about it', 'how about it', 'elaborate',
        
        # Detail requests
        'how does it', 'how it works', 'why does it', 'what makes it',
        
        # Direct pronoun references
        ' it ', ' this ', ' that ', ' these ', ' those ', ' they ', ' them ',
        'about it', 'about this', 'about that', 'with it', 'with this',
        
        # Benefit/effect questions with pronouns
        'its benefits', 'its effects', 'its advantages',
        
        # Usage questions with pronouns
        'how to do it', 'when to do it', 'how much of it',
        
        # Explain/describe with "the" (referring to previously mentioned concept)
        'explain the', 'describe the', 'what is the', 'how does the',
    ]
    
    # Weak follow-up indicators (need additional context)
    weak_followup_patterns = [
        'explain', 'describe', 'benefits', 'effects', 'how does', 'why does',
        'how to', 'when to', 'how much', 'how often',
    ]
    
    # New topic indicators (these suggest it's NOT a follow-up)
    new_topic_indicators = [
        'what exercises', 'what workout', 'what meal', 'what diet',
        'what should i eat', 'what should i do', 'what can i do',
        'how can i lose', 'how can i gain', 'how can i improve',
        'tell me about', 'what is', 'what are', 'who is', 'where is',
        'i want to', 'i need to', 'i would like to',
    ]
    
    # Check for new topic indicators first
    has_new_topic = any(pattern in user_msg_lower for pattern in new_topic_indicators)
    if has_new_topic:
        return False
    
    # Check for strong follow-up patterns
    has_strong_followup = any(pattern in user_msg_lower for pattern in strong_followup_patterns)
    if has_strong_followup:
        return True
    
    # Check for weak follow-up patterns with additional context
    has_weak_followup = any(pattern in user_msg_lower for pattern in weak_followup_patterns)
    
    # Check if question is short (likely a follow-up if combined with other signals)
    is_short = len(user_msg_lower.split()) <= 6
    
    # Check if question has pronouns (strong signal for follow-up)
    pronouns = ['it', 'this', 'that', 'these', 'those', 'they', 'them', 'its']
    has_pronoun = any(f' {pronoun} ' in f' {user_msg_lower} ' or 
                      user_msg_lower.startswith(f'{pronoun} ') or 
                      user_msg_lower.endswith(f' {pronoun}')
                      for pronoun in pronouns)
    
    # A question is likely a follow-up if:
    # 1. It has a weak follow-up pattern AND is short (< 6 words) AND has a pronoun, OR
    # 2. It's very short (< 4 words) AND has a pronoun
    is_very_short = len(user_msg_lower.split()) <= 3
    return (has_weak_followup and is_short and has_pronoun) or (is_very_short and has_pronoun)

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
                "Focus on user preferences, key decisions, and current fitness/diet context. "
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
        intent = detect_user_intent(user_question, state)
    
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
        plan_title = "Meal Plan" if intent == INTENT_MEAL else "Exercise Plan"
        context_parts.append(f"**User's {plan_title}**\n{plan_mem}")
        
    return "\n\n".join(context_parts)
