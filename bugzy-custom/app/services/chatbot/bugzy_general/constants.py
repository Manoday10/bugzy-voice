# ==============================================================================
# NODE CONFIGURATION & MAPPING
# ==============================================================================

QUESTION_TO_NODE = {
    "age": "collect_age",
    "height": "collect_height",
    "weight": "collect_weight",
    "health_conditions": "collect_health_conditions",
    "medications": "collect_medications",
    "meal_timing_breakfast": "collect_meal_timing_breakfast",
    "meal_timing_lunch": "collect_meal_timing_lunch",
    "meal_timing_dinner": "collect_meal_timing_dinner",
    "current_breakfast": "collect_current_breakfast",
    "current_lunch": "collect_current_lunch",
    "current_dinner": "collect_current_dinner",
    "diet_preference": "collect_diet_preference",
    "cuisine_preference": "collect_cuisine_preference",
    "allergies": "collect_allergies",
    "water_intake": "collect_water_intake",
    "beverages": "collect_beverages",
    "lifestyle": "collect_lifestyle",
    "activity_level": "collect_activity_level",
    "sleep_stress": "collect_sleep_stress",
    "supplements": "collect_supplements",
    "gut_health": "collect_gut_health",
    "meal_goals": "collect_meal_goals",
    "fitness_level": "collect_fitness_level",
    "activity_types": "collect_activity_types",
    "exercise_frequency": "collect_exercise_frequency",
    "exercise_intensity": "collect_exercise_intensity",
    "session_duration": "collect_session_duration",
    "sedentary_time": "collect_sedentary_time",
    "exercise_goals": "collect_exercise_goals",
    
    # Single-call 7-day plan generation nodes
    "generating_remaining_meal_days": "generate_all_remaining_meal_days",
    "generating_remaining_exercise_days": "generate_all_remaining_exercise_days",
    
    # Meal Plan Nodes
    "handle_meal_day1_review_choice": "handle_meal_day1_review_choice",
    "collect_meal_day1_changes": "collect_meal_day1_changes",
    "regenerate_meal_day1_plan": "regenerate_meal_day1_plan",
    "handle_meal_day1_revised_review": "handle_meal_day1_revised_review",
    "generate_all_remaining_meal_days": "generate_all_remaining_meal_days",
    "meal_day1_plan_review": "handle_meal_day1_review_choice",
    "meal_day1_revised_review": "handle_meal_day1_revised_review",
    "generate_meal_day1_plan": "generate_meal_plan",
    
    # Exercise Plan Nodes
    "generate_all_remaining_exercise_days": "generate_all_remaining_exercise_days",
    "handle_day1_review_choice": "handle_day1_review_choice",
    "collect_day1_changes": "collect_day1_changes",
    "regenerate_day1_plan": "regenerate_day1_plan",
    "handle_day1_revised_review": "handle_day1_revised_review",
    "day1_plan_review": "handle_day1_review_choice",
    "day1_revised_review": "handle_day1_revised_review",
    "generate_day1_plan": "generate_day1_plan",
}

TRANSITION_MESSAGES = [
    "💚 Let's pick up where we left off...",
    "🌟 Now, back to your personalized plan...",
    "✨ Great! Let's continue with your wellness journey...",
    "💫 Perfect! Now let's get back to creating your plan...",
    "🌸 Awesome! Let's continue where we paused...",
    "💝 I hope you're feeling better! Now, back to your plan...",
    "🌿 Got it! Let's resume building your wellness plan...",
    "💖 Take care of yourself! Now, let's continue...",
    "🌺 Wonderful! Let's get back to your personalized journey...",
    "✨ That's sorted! Now, back to crafting your plan...",
    "💚 Perfect! Let's continue with the next step...",
    "🌟 Great! Now, let's pick up where we were..."
]
