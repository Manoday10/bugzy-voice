"""
State definition for the chatbot agent.

This module contains the State TypedDict that defines all the fields
used throughout the chatbot conversation flow.

Product: AMS (Active Metabolic Support)
"""

from typing import TypedDict, Optional, Literal


class State(TypedDict):
    user_id: str
    product: Literal["ams"]  # Product identifier
    user_msg: Optional[str]
    last_question: Optional[str]
    conversation_history: Optional[list]
    journey_history: Optional[list]
    full_chat_history: Optional[list]  # Store complete chat history (user + system)
    current_agent: Optional[str]  # 'meal' or 'exercise'
    pending_node: Optional[str]  # Track where user left off for resuming
    
    # User verification
    phone_number: Optional[str]
    user_name: Optional[str]
    crm_user_data: Optional[dict]
    verification_attempts: Optional[int]
    
    # Order details
    user_order: Optional[str]
    user_order_date: Optional[str]
    has_orders: Optional[bool]
    
    # Basic info (shared)
    age: Optional[str]
    height: Optional[str]
    weight: Optional[str]
    # NOTE: BMI stored as string (formatted display value, e.g., "22.5")
    # See: bugzy_ams/nodes/user_verification_nodes.py line 470: state["bmi"] = str(bmi)
    bmi: Optional[str]

    # BMI fields (additional)
    bmi_category: Optional[str]  # CRITICAL: Added BMI category
    bmi_calculated: Optional[bool]  # CRITICAL: Added BMI calculated flag
    
    # Profiling tracking flags
    profiling_collected: Optional[bool]  # CRITICAL: Added profiling collected flag
    profiling_collected_in_meal: Optional[bool]  # CRITICAL: Track if profiling was in meal flow
    profiling_collected_in_exercise: Optional[bool]  # CRITICAL: Track if profiling was in exercise flow
    
    # MEAL PLANNER AGENT - Health & meal info
    health_conditions: Optional[str]
    medications: Optional[str]
    
    # NEW: 9 comprehensive meal plan variables
    diet_preference: Optional[str]
    cuisine_preference: Optional[str]
    current_dishes: Optional[str]
    allergies: Optional[str]
    water_intake: Optional[str]
    beverages: Optional[str]
    supplements: Optional[str]
    gut_health: Optional[str]
    meal_goals: Optional[str]

    # User Preferences
    wants_meal_plan: Optional[bool]
    wants_exercise_plan: Optional[bool]
    
    # Journey restart flags - set when user restarts a journey from post_plan_qna
    journey_restart_mode: Optional[bool]
    existing_meal_plan_choice_origin: Optional[str]  # Track where user chose to recreate meal plan from
    existing_exercise_plan_choice_origin: Optional[str]  # Track where user chose to recreate exercise plan from

    # Voice Agent Tracker
    voice_agent_choice: Optional[str]
    voice_agent_context: Optional[str]
    voice_agent_promotion_shown: Optional[bool]
    voice_agent_declined: Optional[bool]
    voice_agent_accepted: Optional[bool]

    meal_plan: Optional[str]
    meal_plan_sent: Optional[bool]
    
    # MEAL PLANNER - Daily meal plans
    meal_day1_plan: Optional[str]
    meal_day2_plan: Optional[str]
    meal_day3_plan: Optional[str]
    meal_day4_plan: Optional[str]
    meal_day5_plan: Optional[str]
    meal_day6_plan: Optional[str]
    meal_day7_plan: Optional[str]
    old_meal_day1_plans: Optional[list]  # Store previous versions of meal day 1 plan
    meal_day1_change_request: Optional[str]  # User's requested changes for meal day 1
    
    # EXERCISE PLANNER AGENT - FITT Framework Fields
    fitness_level: Optional[str]
    activity_types: Optional[str]
    exercise_frequency: Optional[str]
    exercise_intensity: Optional[str]
    session_duration: Optional[str]
    sedentary_time: Optional[str]
    exercise_goals: Optional[str]
    
    # EXERCISE PLANNER AGENT - Goals & output
    exercise_plan: Optional[str]
    exercise_plan_sent: Optional[bool]
    
    # EXERCISE PLANNER - Daily plans
    day1_plan: Optional[str]
    day2_plan: Optional[str]
    day3_plan: Optional[str]
    day4_plan: Optional[str]
    day5_plan: Optional[str]
    day6_plan: Optional[str]
    day7_plan: Optional[str]
    old_day1_plans: Optional[list]  # Store previous versions of day 1 plan
    day1_change_request: Optional[str]  # User's requested changes for day 1
    
    # SNAP - Image analysis
    snap_image_url: Optional[str]
    snap_analysis_result: Optional[str]
    snap_analysis_sent: Optional[bool]
    
    # Context Optimization
    conversation_summary: Optional[str]  # Compressed history summary
    last_summary_message_count: Optional[int]      # Track when last summarized
    detected_intent: Optional[str]       # Cache detected intent

    # ────────────────────────────────────────────────────────────────────────
    # Voice Integration Fields (Phase 1 — LiveKit / WhatsApp Calling)
    # ────────────────────────────────────────────────────────────────────────
    messages: Optional[list]               # Assistant messages for voice TTS (role/content dicts)
    interaction_mode: Optional[str]        # 'voice' | 'chat' — modality of current turn
    voice_session_id: Optional[str]        # LiveKit room name for this call
    call_start_time: Optional[str]         # ISO timestamp when call connected
    call_end_time: Optional[str]           # ISO timestamp when call ended
    voice_call_active: Optional[bool]      # True while call is in progress
    fresh_meal_plan: Optional[bool]        # Set True when plan is ready to send via Node.js
    fresh_exercise_plan: Optional[bool]    # Set True when exercise plan is ready to send
