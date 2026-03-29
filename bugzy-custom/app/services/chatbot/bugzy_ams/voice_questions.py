"""
Voice questions for the AMS (Active Metabolic Support) product.

Aligned with bugzy-voice flow: age → height → weight → diet → cuisine → dishes →
allergies → water → beverages → supplements → gut_health → meal_goals →
health_conditions → medications.

Rules: No emojis, no markdown, short conversational phrasing, no numbered lists.
"""

VOICE_QUESTIONS: dict[str, str] = {
    # ── Basic profiling (matches bugzy-voice AMS meal flow) ────────────────────
    "age":     "What's your age?",
    "height":  "What's your height? You can tell me in cm, feet and inches, or meters.",
    "weight":  "What's your weight? You can tell me in kg or lbs.",

    # ── Meal planner flow (14 questions, bugzy-voice order) ───────────────────
    "diet_preference": (
        "What's your dietary preference? "
        "For example, vegetarian, non-veg, vegan, keto, or any other preference."
    ),
    "cuisine_preference": (
        "Do you have any cuisine preferences? "
        "Like Indian, Chinese, Italian, or no preference?"
    ),
    "current_dishes": "What are some of your favorite dishes or meals? This helps me personalize your plan.",
    "allergies": (
        "Do you have any food allergies or intolerances? "
        "Like nuts, dairy, gluten, or none?"
    ),
    "water_intake": (
        "Hydration check. Roughly how much water do you drink daily? "
        "You can say in liters or glasses."
    ),
    "beverages": "Any other beverages you regularly have? Like coffee, tea, alcohol, or none?",
    "supplements": "Are you currently taking any supplements or vitamins? Or none?",
    "gut_health": (
        "How's your gut health? "
        "Do you experience any issues like bloating, constipation, or no issues?"
    ),
    "meal_goals": (
        "What are your main nutrition goals? "
        "Like weight loss, muscle gain, better energy, or something else?"
    ),
    "health_conditions": (
        "Do you have any health conditions we should know about? "
        "Like diabetes, IBS, thyroid issues, or none?"
    ),
    "medications": "Are you taking any medications? Or none?",

    # ── Exercise planner flow ─────────────────────────────────────────────────
    "fitness_level": (
        "How would you describe your current fitness level? "
        "Beginner, intermediate, or advanced?"
    ),
    "activity_types": "What types of physical activity do you currently do or enjoy?",
    "exercise_frequency": "How many days per week do you exercise?",
    "exercise_intensity": "How intense are your typical workouts? Light, moderate, or intense?",
    "session_duration": "How long are your typical workout sessions?",
    "sedentary_time": "How many hours a day do you spend sitting or being inactive?",
    "exercise_goals": "What is your main fitness goal right now?",

    # ── Preferences ───────────────────────────────────────────────────────────
    "wants_meal_plan":     "Would you like me to create a personalized meal plan for you?",
    "wants_exercise_plan": "Would you also like a personalized exercise plan?",

    # ── Meal Day 1 review (after Day 1 plan generated) ───────────────────────
    "meal_day1_review": (
        "Would you like to make any changes to Day 1, or shall I continue with your full 7-day plan?"
    ),
    "meal_day1_changes_prompt": "What changes would you like to make to Day 1?",
    "meal_day1_continue": (
        "Perfect! I'm generating your complete 7-day plan now. You'll receive it on WhatsApp shortly."
    ),
    "meal_day1_revised_review": (
        "Would you like more changes to Day 1, or shall we continue with your full 7-day plan?"
    ),
    "meal_generating_remaining": (
        "I'm generating your complete 7-day meal plan now. You'll get it on WhatsApp in a moment."
    ),
}
