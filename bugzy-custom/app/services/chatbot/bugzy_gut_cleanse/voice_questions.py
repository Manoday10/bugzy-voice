"""
Voice questions for the Gut Cleanse product.

Aligned with bugzy-voice flow: age_eligibility → gender → pregnancy_check →
health_safety_screening → detox_experience → dietary_preference → cuisine →
food_allergies → daily_eating → foods_avoid → supplements → digestive_issues →
hydration → other_beverages → gut_sensitivity.

Keys must match last_question / QUESTION_TO_NODE for correct lookup.
Rules: No emojis, no markdown, short conversational phrasing, no numbered lists.
"""

VOICE_QUESTIONS: dict[str, str] = {
    # ── Safety screening (matches bugzy-voice gut cleanse flow) ─────────────────
    "age_eligibility":   "Are you 18 years or older?",
    "age_eligible":      "Are you 18 years or older?",  # alias
    "age_warning_confirmation": "The gut cleanse is for 18 and older. Do you want to continue with general wellness tips instead?",
    "gender":            "What's your gender? Male, female, or prefer not to say.",
    "pregnancy_check":   "Are you currently pregnant or breastfeeding?",
    "is_pregnant":       "Are you currently pregnant or breastfeeding?",  # alias

    # ── Health safety ─────────────────────────────────────────────────────────
    "health_safety_screening": (
        "This helps ensure the cleanse is safe for you. "
        "Do you have any of these conditions? None or healthy, ulcers or IBS, or diabetes and thyroid?"
    ),
    "health_safety_status": (
        "How would you describe your overall health? "
        "Healthy, or do you have a gut condition or other medical condition?"
    ),  # alias
    "detox_experience": (
        "Have you done a gut cleanse before? "
        "No first time, yes within the last 6 months, or yes but long ago?"
    ),
    "detox_recent_reason": (
        "Why are you doing another cleanse so soon? "
        "Didn't finish the last one, didn't see results, symptoms came back, or maintenance?"
    ),

    # ── Gut Cleanse meal planner (11-question flow, bugzy-voice phrasing) ───────
    "dietary_preference": (
        "What's your dietary preference? "
        "Non-veg, pure veg, eggitarian, vegan, pescatarian, flexitarian, or keto?"
    ),
    "cuisine_preference": (
        "Do you have any cuisine preferences? "
        "North Indian, South Indian, Gujarati, Chinese, Italian, or all?"
    ),
    "food_allergies_intolerances": (
        "Do you have any food allergies or intolerances? "
        "For example, dairy, gluten, nuts, eggs, lactose, or none."
    ),
    "daily_eating_pattern": (
        "What do you usually eat throughout the day? "
        "Just give me a quick overview of your typical meals."
    ),
    "foods_avoid": "Any foods you absolutely avoid or dislike?",
    "supplements": "Are you currently taking any supplements or vitamins?",
    "digestive_issues": (
        "Quick digestion check. Do you experience bloating, constipation, "
        "acidity, gas, irregular bowel movements, or none?"
    ),
    "hydration": (
        "Hydration check. How much water do you drink daily? "
        "Less than 1 liter, 1 to 2, 2 to 3, or more than 3 liters?"
    ),
    "other_beverages": (
        "Other beverages. How many cups of coffee, tea, or other drinks daily? "
        "None, 1 to 2 cups, 3 to 4, or 5 or more?"
    ),
    "gut_sensitivity": (
        "Last question. How sensitive is your stomach? "
        "Very sensitive, moderately sensitive, or not sensitive?"
    ),

    # ── Plan preferences ──────────────────────────────────────────────────────
    "wants_meal_plan":     "Would you like me to create a personalized meal plan for you?",
    "wants_exercise_plan": "Would you also like a personalized gut-friendly exercise plan?",

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
}
