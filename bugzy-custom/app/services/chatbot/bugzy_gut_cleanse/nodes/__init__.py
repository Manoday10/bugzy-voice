"""
Nodes package for the Bugzy chatbot agent.

This package contains all node functions organized by functionality:
- user_verification_nodes: User verification and basic info collection
- meal_plan_nodes: Meal plan generation and management
- qna_nodes: Health, product, and post-plan Q&A handling
"""

# Import all node functions for easy access
from app.services.chatbot.bugzy_gut_cleanse.nodes.user_verification_nodes import (
    verify_user_node,
    collect_age_eligibility,
    collect_age_warning_confirmation,
    collect_gender,
    collect_pregnancy_check,
    collect_pregnancy_warning_confirmation,
    collect_health_safety_screening,
    collect_detox_experience,
    transition_to_snap,
    snap_image_analysis,
    transition_to_gut_coach,
    validate_input,
    handle_validated_input,
)

from app.services.chatbot.bugzy_gut_cleanse.nodes.meal_plan_nodes import (

    collect_dietary_preference,
    collect_cuisine_preference,
    collect_food_allergies_intolerances,
    collect_daily_eating_pattern,
    collect_foods_avoid,
    collect_supplements,
    collect_digestive_issues,
    collect_hydration,
    collect_other_beverages,
    collect_gut_sensitivity,
    generate_all_remaining_meal_days,
    generate_meal_plan,  # This is the Day 1 meal plan function
    generate_meal_day2_plan,
    generate_meal_day3_plan,
    generate_meal_day4_plan,
    generate_meal_day5_plan,
    generate_meal_day6_plan,
    generate_meal_day7_plan,
    handle_meal_day1_review_choice,
    collect_meal_day1_changes,
    regenerate_meal_day1_plan,
    handle_meal_day1_revised_review,
    ask_meal_plan_preference,
    ask_existing_meal_plan_choice,
    load_existing_meal_plan_for_edit,
    voice_agent_promotion_meal,
)

from app.services.chatbot.bugzy_gut_cleanse.nodes.qna_nodes import (
    health_qna_node,
    product_qna_node,
    post_plan_qna_node,
    resume_from_qna_node,
    resume_from_qna_node,
    # Note: The following functions remain in agent.py for now
    handle_meal_edit_request,
    handle_meal_day_selection_for_edit,
    collect_meal_day_edit_changes,
)

__all__ = [
    # User verification nodes - New profiling flow
    'verify_user_node',
    'collect_age_eligibility',
    'collect_age_warning_confirmation',
    'collect_gender',
    'collect_pregnancy_check',
    'collect_pregnancy_warning_confirmation',
    'collect_health_safety_screening',
    'collect_detox_experience',
    'transition_to_snap',
    'snap_image_analysis',
    'transition_to_gut_coach',
    'validate_input',
    'handle_validated_input',
    
    # Meal plan nodes

    'collect_dietary_preference',
    'collect_cuisine_preference',
    'collect_food_allergies_intolerances',
    'collect_daily_eating_pattern',
    'collect_foods_avoid',
    'collect_supplements',
    'collect_digestive_issues',
    'collect_hydration',
    'collect_other_beverages',
    'collect_gut_sensitivity',
    'generate_all_remaining_meal_days',
    'generate_meal_plan',  # This is the Day 1 meal plan function
    'generate_meal_day2_plan',
    'generate_meal_day3_plan',
    'generate_meal_day4_plan',
    'generate_meal_day5_plan',
    'generate_meal_day6_plan',
    'generate_meal_day7_plan',
    'handle_meal_day1_review_choice',
    'collect_meal_day1_changes',
    'regenerate_meal_day1_plan',
    'handle_meal_day1_revised_review',
    "ask_meal_plan_preference",
    'ask_existing_meal_plan_choice',
    'load_existing_meal_plan_for_edit',
    'voice_agent_promotion_meal',
    
    # QnA nodes
    'health_qna_node',
    'product_qna_node',
    'post_plan_qna_node',
    'resume_from_qna_node',
    'resume_from_qna_node',
    # Note: The following functions remain in agent.py for now
    'handle_meal_edit_request',
    'handle_meal_day_selection_for_edit',
    'collect_meal_day_edit_changes',
]
