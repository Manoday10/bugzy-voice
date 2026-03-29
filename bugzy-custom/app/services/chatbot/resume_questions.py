"""
Resume question text for flexible chat/voice journey.

Maps last_question → actual question text so we can:
- Re-ask on chat when user returns from voice drop
- Speak on voice when user joins from chat drop

Uses VOICE_QUESTIONS as source (conversational, modality-agnostic).
"""


def get_question_for_resume(product: str, last_question: str) -> str | None:
    """
    Return the question text for resuming at last_question.
    Works for both chat and voice.
    """
    # Steps that don't need a re-asked question (handled by flow)
    skip_resume_question = {
        "voice_agent_promotion_meal",
        "voice_agent_promotion_exercise",
        "ask_meal_plan_preference",
        "verified",
        "post_plan_qna",
        "health_qna_answered",
        "product_qna_answered",
        "resuming_from_snap",
        "snap_complete",
        "transitioning_to_snap",
        "transitioning_to_gut_coach",
        "transitioning_to_exercise",
    }
    if last_question in skip_resume_question:
        return None

    # Fallback generic by category
    fallbacks: dict[str, str] = {
        "meal_day1_plan_review": "Would you like to make changes to Day 1, or continue with your 7-day plan?",
        "meal_day1_revised_review": "Would you like more changes or continue with your 7-day plan?",
        "awaiting_meal_day1_changes": "What changes would you like to make to Day 1?",
        "meal_day1_complete": "I'm generating your complete 7-day plan now. You'll get it shortly.",
    }
    if last_question in fallbacks:
        return fallbacks[last_question]

    # Load from product-specific VOICE_QUESTIONS
    if product == "ams":
        from app.services.chatbot.bugzy_ams.voice_questions import VOICE_QUESTIONS
        return VOICE_QUESTIONS.get(last_question)
    if product == "gut_cleanse":
        from app.services.chatbot.bugzy_gut_cleanse.voice_questions import VOICE_QUESTIONS
        return VOICE_QUESTIONS.get(last_question)
    # free_form has minimal voice questions
    from app.services.chatbot.bugzy_free_form.voice_questions import VOICE_QUESTIONS
    return VOICE_QUESTIONS.get(last_question)
