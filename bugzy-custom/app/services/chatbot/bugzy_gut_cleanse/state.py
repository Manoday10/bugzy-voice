"""
State definition for the chatbot agent.

This module contains the State TypedDict that defines all the fields
used throughout the chatbot conversation flow.

Product: Gut Cleanse
"""

from typing import TypedDict, Optional, Literal


class State(TypedDict):
    user_id: str
    product: Literal["gut_cleanse"]  # Product identifier
    user_msg: Optional[str]
    last_question: Optional[str]
    conversation_history: Optional[list]
    journey_history: Optional[list]
    full_chat_history: Optional[list]  # Store complete chat history (user + system)
    current_agent: Optional[str]  # 'meal' or 'exercise'
    pending_node: Optional[str]  # Track where user left off for resuming
    messages: Optional[list]  # Track conversational messages for voice/agent output
    
    # User verification
    phone_number: Optional[str]
    user_name: Optional[str]
    crm_user_data: Optional[dict]
    verification_attempts: Optional[int]
    
    # Order details
    user_order: Optional[str]
    user_order_date: Optional[str]
    has_orders: Optional[bool]
    
    # Basic info (shared) - Profiling questions
    age_eligible: Optional[bool]  # Age eligibility (18+)
    gender: Optional[str]  # Gender: "male", "female", "prefer_not_to_say"
    is_pregnant: Optional[bool]  # Pregnancy status (only for females)
    is_breastfeeding: Optional[bool]  # Breastfeeding status (only for females)
    
    # Legacy fields (kept for backward compatibility, but not used in new flow)
    age: Optional[str]
    height: Optional[str]
    weight: Optional[str]
    
    # BMI fields
    bmi: Optional[str]
    bmi_category: Optional[str]
    bmi_calculated: Optional[bool]
    
    # Profiling tracking flags
    profiling_collected: Optional[bool]  # CRITICAL: Added profiling collected flag
    profiling_collected_in_meal: Optional[bool]  # CRITICAL: Track if profiling was in meal flow
    profiling_collected_in_exercise: Optional[bool]  # CRITICAL: Track if profiling was in exercise flow
    
    # New Extended Profiling Fields
    health_safety_status: Optional[str]  # "healthy", "gut_condition", "medical_condition"
    health_safety_warning_sent: Optional[bool]
    detox_experience: Optional[str]  # "no", "recent", "long_ago"
    detox_recent_reason: Optional[str]  # "incomplete", "no_results", "symptoms_back", "maintenance"
    specific_health_condition: Optional[str] # Detailed condition triggered in safety check
    age_eligibility_warning_sent: Optional[bool] # Track if under-18 warning sent
    pregnancy_warning_confirmed: Optional[bool] # Track if user confirmed to proceed after pregnancy/breastfeeding warning
    


    # MEAL PLANNER AGENT - New 11-Question Flow
    # Q1: Dietary Preference
    dietary_preference: Optional[str]
    # Q2: Cuisine Preference
    cuisine_preference: Optional[str]
    # Q4: Food Allergies or Intolerances
    food_allergies_intolerances: Optional[str]
    # Q5: Daily Eating Pattern
    daily_eating_pattern: Optional[str]
    # Q6: Foods You Avoid
    foods_avoid: Optional[str]
    # Q7: Supplements
    supplements: Optional[str]
    # Q8: Digestive Issues
    digestive_issues: Optional[str]
    # Q9: Hydration
    hydration: Optional[str]
    # Q10: Other Beverages and Commitment
    other_beverages: Optional[str]
    # Q11: Gut Sensitivity
    gut_sensitivity: Optional[str]

    # User Preferences
    wants_meal_plan: Optional[bool]
    wants_exercise_plan: Optional[bool]
    
    # Journey restart flags - set when user restarts a journey from post_plan_qna
    journey_restart_mode: Optional[bool]
    existing_meal_plan_choice_origin: Optional[str]  # Track where user chose to recreate meal plan from

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
    

    # GUT CLEANSE - Gut-specific exercise fields
    workout_posture_gut: Optional[str]
    workout_hydration_gut: Optional[str]
    workout_gut_mobility_gut: Optional[str]
    workout_relaxation_gut: Optional[str]
    workout_gut_awareness_gut: Optional[str]
    
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
    last_summary_message_count: Optional[int]  # Track when last summarized
    detected_intent: Optional[str]  # Cache detected intent

    # ────────────────────────────────────────────────────────────────────────
    # Voice Integration Fields (Phase 1 — LiveKit / WhatsApp Calling)
    # ────────────────────────────────────────────────────────────────────────
    interaction_mode: Optional[str]        # 'voice' | 'chat'
    voice_session_id: Optional[str]        # LiveKit room name for this call
    call_start_time: Optional[str]         # ISO timestamp when call connected
    call_end_time: Optional[str]           # ISO timestamp when call ended
    voice_call_active: Optional[bool]      # True while call is in progress
    fresh_meal_plan: Optional[bool]        # Set True when plan is ready to send
    fresh_exercise_plan: Optional[bool]    # Set True when exercise plan is ready