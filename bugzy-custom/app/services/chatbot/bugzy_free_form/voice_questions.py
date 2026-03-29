"""
Voice questions for the Free Form (general) product.

Rules for voice questions:
- No emojis, no special characters, no markdown
- Short, conversational phrasing
- No numbered lists or button labels
"""

VOICE_QUESTIONS: dict[str, str] = {
    # ── Basic profiling ───────────────────────────────────────────────────────
    "age":    "How old are you?",
    "height": "What is your height? You can say it in feet and inches or centimeters.",
    "weight": "What is your current weight in kilograms?",

    # ── General health ────────────────────────────────────────────────────────
    "health_conditions": (
        "Do you have any health conditions I should be aware of? "
        "For example, diabetes, thyroid, or blood pressure issues."
    ),
    "medications": "Are you currently on any medications?",
    "diet_preference": (
        "What is your dietary preference? Vegetarian, non-vegetarian, vegan, or other?"
    ),
    "cuisine_preference": (
        "Do you have a cuisine preference, like Indian, Chinese, or international?"
    ),
    "allergies": (
        "Do you have any food allergies or intolerances? "
        "For example dairy, gluten, or nuts."
    ),
    "water_intake": "How much water do you drink in a day?",
    "meal_goals": "What is your main health goal right now?",

    # ── Preferences ───────────────────────────────────────────────────────────
    "wants_meal_plan":     "Would you like a personalized meal plan?",
    "wants_exercise_plan": "Would you like a personalized exercise plan as well?",
}
