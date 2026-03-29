"""
State definition for the chatbot agent.

This module contains the State TypedDict that defines all the fields
used throughout the chatbot conversation flow.
"""

from typing import TypedDict, Optional


class State(TypedDict):
    user_id: str
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
    bmi: Optional[float]
    
    # MEAL PLANNER AGENT - Health & meal info
    health_conditions: Optional[str]
    medications: Optional[str]
    meal_timings: Optional[dict]
    current_breakfast: Optional[str]
    current_lunch: Optional[str]
    current_dinner: Optional[str]
    
    # MEAL PLANNER AGENT - Preferences
    diet_preference: Optional[str]
    cuisine_preference: Optional[str]
    allergies: Optional[str]
    
    # MEAL PLANNER AGENT - Lifestyle
    water_intake: Optional[str]
    beverages: Optional[str]
    lifestyle: Optional[str]
    activity_level: Optional[str]
    sleep_stress: Optional[str]
    supplements: Optional[str]
    gut_health: Optional[str]
    
    # MEAL PLANNER AGENT - Goals & output
    meal_goals: Optional[str]
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
    
    # EXERCISE PLANNER AGENT - Fitness assessment
    fitness_level: Optional[str]
    activity_types: Optional[str]
    exercise_frequency: Optional[str]
    exercise_intensity: Optional[str]
    session_duration: Optional[str]
    sedentary_time: Optional[str]
    
    # EXERCISE PLANNER AGENT - Goals & output
    exercise_goals: Optional[str]
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
