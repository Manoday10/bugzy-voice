"""
State definition for the bugzy_free_form agent.

Minimal state: no meal planning, no exercise planning, no profiling.
Used for QnA-only flow for users without AMS/Gut Cleanse purchase.
"""

from typing import TypedDict, Optional


class State(TypedDict, total=False):
    """
    Slim state for free_form agent.
    IMPORTANT: Includes optional fields from other modules (ams, gut_cleanse)
    to preserve user profile data when users switch modules or are migrated.
    """

    # Core
    user_id: str
    user_msg: Optional[str]
    last_question: Optional[str]
    current_agent: Optional[str]
    pending_node: Optional[str]

    # Conversation
    conversation_history: Optional[list]
    journey_history: Optional[list]
    full_chat_history: Optional[list]

    # User (from CRM)
    phone_number: Optional[str]
    user_name: Optional[str]
    crm_user_data: Optional[dict]
    whatsapp_push_name: Optional[str]

    # Order (from CRM)
    user_order: Optional[str]
    user_order_date: Optional[str]
    has_orders: Optional[bool]

    # SNAP
    snap_image_url: Optional[str]
    snap_analysis_result: Optional[str]
    snap_analysis_sent: Optional[bool]

    # Context / LLM
    conversation_summary: Optional[str]
    last_summary_message_count: Optional[int]
    detected_intent: Optional[str]

    # ===== CROSS-MODULE FIELDS (Optional) =====
    # These fields allow free_form to access user profile data
    # from previous AMS or Gut Cleanse journeys
    
    # Journey state
    journey_restart_mode: Optional[bool]
    
    # === AMS MODULE FIELDS (Optional) ===
    # Basic profiling
    age: Optional[str]
    height: Optional[str]
    weight: Optional[str]
    bmi: Optional[str]
    bmi_category: Optional[str]
    
    # Health info
    health_conditions: Optional[str]
    medications: Optional[str]
    
    # AMS Meal preferences (9 questions)
    diet_preference: Optional[str]
    cuisine_preference: Optional[str]
    allergies: Optional[str]
    water_intake: Optional[str]
    beverages: Optional[str]
    supplements: Optional[str]
    gut_health: Optional[str]
    meal_goals: Optional[str]
    
    # AMS Exercise preferences (FITT - 7 questions)
    fitness_level: Optional[str]
    activity_types: Optional[str]
    exercise_duration: Optional[str]
    exercise_days_per_week: Optional[str]
    time_of_day_preference: Optional[str]
    exercise_goals: Optional[str]
    exercise_limitations: Optional[str]
    
    # === GUT CLEANSE MODULE FIELDS (Optional) ===
    # Safety screening
    age_eligible: Optional[bool]
    gender: Optional[str]
    is_pregnant: Optional[bool]
    is_breastfeeding: Optional[bool]
    health_safety_status: Optional[str]
    detox_experience: Optional[str]
    
    # Gut Cleanse meal preferences (11 questions)
    dietary_preference: Optional[str]
    food_allergies_intolerances: Optional[str]
    daily_eating_pattern: Optional[str]
    foods_avoid: Optional[str]
    digestive_issues: Optional[str]
    hydration: Optional[str]
    other_beverages: Optional[str]
    gut_sensitivity: Optional[str]
    
    # Plan status (useful context)
    meal_plan_sent: Optional[bool]
    exercise_plan_sent: Optional[bool]
    profiling_collected: Optional[bool]
    profiling_collected_in_meal: Optional[bool]
    profiling_collected_in_exercise: Optional[bool]

    # ────────────────────────────────────────────────────────────────────────
    # Voice Integration Fields (Phase 1 — LiveKit / WhatsApp Calling)
    # ────────────────────────────────────────────────────────────────────────
    messages: Optional[list]               # Assistant messages for voice TTS (role/content dicts)
    interaction_mode: Optional[str]        # 'voice' | 'chat'
    voice_session_id: Optional[str]        # LiveKit room name for this call
    call_start_time: Optional[str]         # ISO timestamp when call connected
    call_end_time: Optional[str]           # ISO timestamp when call ended
    voice_call_active: Optional[bool]      # True while call is in progress
    fresh_meal_plan: Optional[bool]        # Set True when plan is ready to send
    fresh_exercise_plan: Optional[bool]    # Set True when exercise plan ready
