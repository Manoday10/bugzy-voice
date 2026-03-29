import re
from datetime import datetime

"""
Unified Meal Plan Template Module
All meal plan generation functions should use this template to ensure consistent formatting.
"""

# The exact template format that MUST be followed for every day
MEAL_PLAN_TEMPLATE = """
*Day {day_number}: {day_theme}* 🍽️

🌅 *BREAKFAST:*
{breakfast_content}

{mid_morning_snack_section}

🌤️ *LUNCH:*
{lunch_content}

{evening_snack_section}

🌙 *DINNER:*
{dinner_content}

💧 *HYDRATION:*
{hydration_content}

{supplement_section}

{gut_health_section}

💚 *TODAY'S TIP:*
{daily_tip}
"""

# Snack section templates
MID_MORNING_SNACK_TEMPLATE = """🍎 *MID-MORNING SNACK:*
{snack_content}
"""

EVENING_SNACK_TEMPLATE = """🥜 *EVENING SNACK:*
{snack_content}
"""

# Supplement section template
SUPPLEMENT_SECTION_TEMPLATE = """💊 *SUPPLEMENT SCHEDULE:*
{supplement_content}
"""

# Gut health section template
GUT_HEALTH_SECTION_TEMPLATE = """🌿 *GUT HEALTH BOOST:*
{gut_health_content}
"""


def get_exact_format_instructions():
    """
    Returns the exact format instructions that MUST be included in every meal plan prompt.
    This ensures consistent output across all days.
    """
    return """
═══════════════════════════════════════════════════════════════
📋 MANDATORY OUTPUT FORMAT - FOLLOW THIS EXACTLY
═══════════════════════════════════════════════════════════════

You MUST output the meal plan in THIS EXACT FORMAT. Do not deviate.
Use asterisks (*) for bold headers. Do not use markdown (**).

---BEGIN EXACT TEMPLATE---

*Day {N}: {Theme}* 🍽️

🌅 *BREAKFAST:*
[Meal name with portions]
- [Detail 1]
- [Detail 2 if needed]

🍎 *MID-MORNING SNACK:*
[Snack with portions]
- [Detail]

🌤️ *LUNCH:*
[Meal name with portions]
- [Detail 1]
- [Detail 2 if needed]

🥜 *EVENING SNACK:*
[Snack with portions]
- [Detail]

🌙 *DINNER:*
[Meal name with portions]
- [Detail 1]
- [Detail 2 if needed]

💧 *HYDRATION:*
[Water and beverage recommendations]

💊 *SUPPLEMENT SCHEDULE:*  ← ONLY if user takes supplements
• ⏰ [Supplement]: [timing]
  🎯 Why: [reason]
  🍽️ With: [food pairing]
  ⚠️ Avoid: [foods to avoid]

🌿 *GUT HEALTH BOOST:*  ← ONLY if user has gut issues
[1-2 gut health tips]

💚 *TODAY'S TIP:*
[1-2 actionable tips for the day]

---END EXACT TEMPLATE---

CRITICAL FORMATTING RULES:
1. Use *asterisks* for headers (not **double asterisks**)
2. Each section header MUST have the emoji BEFORE the asterisk
3. Use bullet points (-) for meal details, not numbered lists
4. Keep consistent spacing - one blank line between sections
5. Do NOT add any "⚠️ THIS SECTION IS MANDATORY" warnings in output
6. Do NOT add disclaimers in the output (they are added separately)
"""


def get_day_themes():
    """Returns themed names for each day to add variety."""
    return {
        1: "Fresh Start",
        2: "Gentle Healing",
        3: "Energy & Balance",
        4: "Nourishment Focus",
        5: "Strength & Recovery",
        6: "Harmony & Renewal",
        7: "Complete Wellness"
    }


def build_user_profile_context(state: dict) -> str:
    """
    Builds the user profile context string from state.
    This ensures consistent profile formatting across all functions.
    """
    return f"""
USER PROFILE:
• Name: {state.get('user_name', 'Friend')}
• Age: {state.get('age', 'not provided')}, BMI: {state.get('bmi', 'not calculated')}
• Health conditions: {state.get('health_conditions', 'None')}
• Current medications: {state.get('medications', 'None')}

DIETARY PREFERENCES:
• Diet Type: {state.get('diet_preference', 'Not provided')}
• Cuisine: {state.get('cuisine_preference', 'Not provided')}
• Typical Dishes: {state.get('current_dishes', 'Not provided')}
• Allergies: {state.get('allergies', 'None')}
• Water Intake: {state.get('water_intake', 'Not provided')}
• Beverages: {state.get('beverages', 'None')}
• Supplements: {state.get('supplements', 'None')}
• Gut Health: {state.get('gut_health', 'No issues reported')}
• Meal Goals: {state.get('meal_goals', 'Not provided')}
"""


def get_gut_health_instructions(gut_health: str, has_gut_issues: bool) -> str:
    """Returns gut health specific instructions if applicable."""
    if not has_gut_issues:
        return ""
    
    return f"""
🔴 GUT HEALTH REQUIREMENTS (User reported: {gut_health}):

EVERY MEAL MUST INCLUDE:
- At least ONE probiotic food (yogurt, kefir, buttermilk, curd, fermented foods)
- At least ONE prebiotic food (bananas, oats, garlic, onions, whole grains)
- Anti-inflammatory ingredients (turmeric, ginger, green leafy vegetables)

AVOID THESE GUT IRRITANTS:
- Raw vegetables (use COOKED only)
- Brown rice (use white rice or well-cooked options)
- Heavy, fried, or processed foods
- Excessive spices or chilies
- Raw salads

FOR SNACKS: Use gut-friendly options like curd with fruit, banana with almond butter, probiotic smoothies

YOU MUST INCLUDE the "🌿 *GUT HEALTH BOOST:*" section in your output.
"""


def get_supplement_instructions(supplements: str, has_supplements: bool) -> str:
    """Returns supplement specific instructions if applicable."""
    if not has_supplements:
        return ""
    
    return f"""
💊 SUPPLEMENT REQUIREMENTS (User takes: {supplements}):

YOU MUST INCLUDE the "💊 *SUPPLEMENT SCHEDULE:*" section in your output.

For EACH supplement, specify:
• ⏰ Best time to take
• 🎯 Why that timing
• 🍽️ Food pairings for absorption
• ⚠️ Foods to avoid nearby
"""


def get_day1_structure_instructions(day1_plan: str) -> str:
    """
    Returns instructions to follow Day 1's structure strictly for Days 2-7.
    """
    if not day1_plan:
        return ""
    
    mid_morning_included = "MID-MORNING SNACK" in day1_plan
    evening_included = "EVENING SNACK" in day1_plan
    
    return f"""
═══════════════════════════════════════════════════════════════
🔴 CRITICAL: FOLLOW DAY 1 STRUCTURE EXACTLY
═══════════════════════════════════════════════════════════════

DAY 1 HAD THE FOLLOWING STRUCTURE - YOU MUST MATCH IT:

✓ Breakfast section: YES
✓ Mid-morning snack: {'YES - MUST INCLUDE' if mid_morning_included else 'NO - DO NOT INCLUDE'}
✓ Lunch section: YES
✓ Evening snack: {'YES - MUST INCLUDE' if evening_included else 'NO - DO NOT INCLUDE'}
✓ Dinner section: YES
✓ Hydration section: YES
✓ Gut Health Boost section: {'YES' if 'GUT HEALTH BOOST' in day1_plan else 'NO'}
✓ Supplement Schedule: {'YES' if 'SUPPLEMENT SCHEDULE' in day1_plan else 'NO'}
✓ Today's Tip: YES

🚨 MANDATORY REQUIREMENTS:
1. If Day 1 had mid-morning snack → ALL days 2-7 MUST have it
2. If Day 1 had evening snack → ALL days 2-7 MUST have it
3. Use SAME level of detail as Day 1 (ingredient specifics, portions, preparation notes)
4. Match Day 1's formatting style exactly (bullet points, spacing, emoji placement)
5. Keep meal descriptions as detailed as Day 1

REFERENCE DAY 1 PLAN STRUCTURE:
{day1_plan[:500]}...
[Use this as your structural template]
"""


def build_meal_plan_prompt(
    state: dict,
    day_number: int,
    previous_meals: dict = None,
    day1_plan: str = None,
    change_request: str = None,
    is_revision: bool = False
) -> str:
    """
    Builds a complete, consistent prompt for meal plan generation.
    
    Args:
        state: User state dictionary
        day_number: Which day (1-7)
        previous_meals: Dict tracking previous days' meals for variety
        day1_plan: Day 1 plan text (for Days 2-7 reference)
        change_request: User's change request (for revisions)
        is_revision: Whether this is a revision of an existing plan
    
    Returns:
        Complete prompt string
    """
    # Detect conditions
    health_conditions = (state.get('health_conditions') or 'None').strip().lower()
    has_health_issues = health_conditions not in ['none', 'nil', 'no', 'nothing', '']
    
    supplements = (state.get('supplements') or 'None').strip()
    has_supplements = supplements.lower() not in ['none', 'nil', 'no', 'nothing', '']
    
    gut_health = (state.get('gut_health') or 'No issues reported').strip().lower()
    has_gut_issues = gut_health not in ['no issues reported', 'none', 'nil', 'no', 'nothing', 'good', 'healthy', '']
    
    # Get day theme
    themes = get_day_themes()
    day_theme = themes.get(day_number, "Wellness Day")
    
    # Build the prompt
    prompt_parts = []
    
    # Role
    prompt_parts.append("""
You are Bugzy (Gut Intelligent Assistant), a supportive nutrition coach.
Your task is to create a meal plan that EXACTLY follows the template format below.
""")
    
    # Revision context if applicable – user's change request is HIGHEST priority
    if is_revision and change_request:
        prompt_parts.append(f"""
🔴 REVISION REQUEST (HIGHEST PRIORITY):
The user wants changes to their Day {day_number} plan.
User's requested changes: {change_request}

Where this conflicts with the HEALTHY MEALS FOCUS section below, the user's request takes PRIORITY—follow the user's request.
Please incorporate these changes while maintaining the exact format.
""")
    elif change_request and not is_revision:
        # For Days 2-7: User's Day 1 change request propagates and overrides HEALTHY MEALS FOCUS when conflicting
        prompt_parts.append(f"""
🔴 USER'S DAY 1 FEEDBACK (HIGHEST PRIORITY – Apply to all subsequent days):
The user made the following request when reviewing Day 1:
"{change_request}"

Where this conflicts with the HEALTHY MEALS FOCUS section below, the user's request takes PRIORITY—follow the user's request and ensure ALL days respect this feedback.
""")
    
    # User profile
    prompt_parts.append(build_user_profile_context(state))
    
    # Gut health instructions
    prompt_parts.append(get_gut_health_instructions(gut_health, has_gut_issues))
    
    # Supplement instructions
    prompt_parts.append(get_supplement_instructions(supplements, has_supplements))

    # Personalization based on User Preferences
    prompt_parts.append(f"""
PERSONALIZATION RULES (Apply these based on User Profile):
1. Diet & Cuisine:
   - Respect the user's diet type (Veg/Non-Veg/Vegan/etc.) strictly.
   - Incorporate flavors from their preferred cuisine ({state.get('cuisine_preference', 'Mixed')}).
   - Use their typical dishes ({state.get('current_dishes', 'standard')}) as inspiration for healthy twists.

2. Allergies & Intolerances:
   - STRICTLY AVOID any allergens mentioned in {state.get('allergies', 'None')}.
   - If lactose intolerant, substitute dairy with plant-based alternatives.

3. Hydration & Beverages:
   - Consider their water intake ({state.get('water_intake', 'average')}) when suggesting hydration tips.
   - Account for their beverage habits ({state.get('beverages', 'None')}) in the plan (e.g., healthier coffee creamer if they drink coffee).

4. Goals:
   - align portion sizes and macro focus with their goal: {state.get('meal_goals', 'General Wellness')}.
   - If weight loss: Focus on high volume, protein, and fiber.
   - If muscle gain: Focus on higher protein and complex carbs.
   - If gut health: Focus on probiotics, prebiotics, and easy-to-digest foods.
""")
    
    # Healthy Meals Focus - Core Principle
    prompt_parts.append("""
═══════════════════════════════════════════════════════════════
🥗 HEALTHY MEALS FOCUS - CORE PRINCIPLE
═══════════════════════════════════════════════════════════════

If a USER'S DAY 1 FEEDBACK or REVISION REQUEST was given above, it takes PRIORITY over these healthy meal guidelines where they conflict—follow the user's request first.

ALL MEALS (Breakfast, Mid-Morning Snack, Lunch, Evening Snack, Dinner) MUST BE:

✅ HEALTHY OPTIONS:
• Whole, unprocessed foods (fresh vegetables, fruits, whole grains, legumes, lean proteins)
• Home-cooked or simple preparations (steamed, boiled, lightly sautéed, baked)
• Balanced nutrition: protein + fiber + healthy fats + vitamins/minerals
• Indian-friendly ingredients: dal, roti, rice, vegetables, curd, fruits, nuts, seeds
• Simple, easy-to-understand meal names (e.g. "Dal Rice with Vegetables", "Roti with Sabzi", "Curd Rice")
• Practical portions that are easy to measure (e.g. "1 cup", "2 rotis", "1 bowl")
• Clear, simple preparation methods that Indian households can easily follow

❌ CLEARLY AVOID UNHEALTHY OPTIONS:
• NO processed/packaged foods (biscuits, chips, instant noodles, ready-made meals)
• NO deep-fried items (pakoras, samosas, vadas, fried snacks)
• NO high-sugar items (sweets, desserts, sugary drinks, packaged juices)
• NO high-salt items (pickles in excess, papad, namkeen, salted snacks)
• NO refined/white flour items (white bread, maida-based items - use whole wheat instead)
• NO artificial additives (colored foods, preservatives, artificial flavors)
• NO heavy, greasy curries (excessive oil/ghee, rich gravies)
• NO street food or restaurant-style heavy dishes

SIMPLICITY FOR INDIAN AUDIENCES:
• Use familiar Indian meal names and combinations
• Keep ingredient lists short and simple (3-5 main items per meal)
• Use common Indian cooking methods (pressure cooking, steaming, simple tempering)
• Include staple Indian foods: dal, rice, roti, sabzi, curd, buttermilk
• Portions should be clear and practical (cups, bowls, pieces - not grams unless necessary)
• Preparation should be straightforward (no complex multi-step recipes)
• Meal descriptions should be easy to read and understand at a glance

EXAMPLE OF GOOD MEAL:
🌅 *BREAKFAST:*
Dal Poha with Vegetables
- 1 cup poha (flattened rice) cooked with dal, onions, and peas (protein + fiber)
- 1 small bowl of curd (probiotic)
- 1 small apple (vitamins)

EXAMPLE OF WHAT TO AVOID:
❌ "Fried Poha with Noodles" (fried + processed)
❌ "Bread with Jam and Butter" (refined flour + high sugar)
❌ "Packaged Upma Mix" (processed food)
""")
    
    # Day 1 structure instructions (for Days 2-7)
    if day_number > 1 and day1_plan:
        prompt_parts.append(get_day1_structure_instructions(day1_plan))
    
    # Variety requirement for Days 2-7
    if day_number > 1 and previous_meals:
        prompt_parts.append(f"""
VARIETY REQUIREMENT - DO NOT REPEAT THESE MEALS:
- Previous breakfasts: {', '.join(previous_meals.get('breakfasts', [])) or 'None yet'}
- Previous lunches: {', '.join(previous_meals.get('lunches', [])) or 'None yet'}
- Previous dinners: {', '.join(previous_meals.get('dinners', [])) or 'None yet'}

Create COMPLETELY DIFFERENT meals for Day {day_number}.
""")
    
    # THE EXACT FORMAT INSTRUCTIONS (MOST IMPORTANT)
    prompt_parts.append(get_exact_format_instructions())
    
    # Final generation instruction
    required_sections = ["🍎 *MID-MORNING SNACK*", "🥜 *EVENING SNACK*"] # Snacks are now standard
    if has_supplements:
        required_sections.append("💊 *SUPPLEMENT SCHEDULE*")
    if has_gut_issues:
        required_sections.append("🌿 *GUT HEALTH BOOST*")
    
    required_text = ", ".join(required_sections)
    
    prompt_parts.append(f"""
═══════════════════════════════════════════════════════════════
NOW GENERATE Day {day_number}: {day_theme}
═══════════════════════════════════════════════════════════════

CHECKLIST BEFORE OUTPUTTING:
✓ Format matches template EXACTLY
✓ Using *asterisks* not **double asterisks**
✓ Emojis are BEFORE the asterisks (e.g., 🌅 *BREAKFAST*)
✓ Required sections included: {required_text}
✓ No disclaimers in output
✓ No "MANDATORY" warnings in output
✓ Warm, supportive tone
✓ Same detail level as Day 1 (if Day 2-7)

Generate the complete meal plan for *Day {day_number}: {day_theme}* now:
""")

    # RE-INFORCE REVISION REQUEST (HIGHEST PRIORITY)
    if is_revision and change_request:
        prompt_parts.append(f"""
═══════════════════════════════════════════════════════════════
🔴 FINAL CONFIRMATION - REVISION REQUEST
═══════════════════════════════════════════════════════════════
The user has explicitly requested: "{change_request}"

CRITICAL INSTRUCTION:
1. You MUST apply this change.
2. If the user asks to REMOVE something (like dairy, curd, specific veggies), you MUST REMOVE IT, even if the "Healthy Meals Focus" or "Gut Health" sections above recommended it.
3. The user's request overrides ALL standard guidelines.
""")
    elif change_request and not is_revision:
         prompt_parts.append(f"""
═══════════════════════════════════════════════════════════════
🔴 FINAL CONFIRMATION - USER FEEDBACK
═══════════════════════════════════════════════════════════════
The user explicitly requested: "{change_request}"

CRITICAL INSTRUCTION:
1. You MUST apply this change to this day's plan.
2. This overrides any conflicting standard guidelines above.
""")
    
    return "\n".join(prompt_parts)


def build_disclaimers(state: dict) -> str:
    """
    Builds the disclaimer text to be appended AFTER the meal plan.
    This is separate from the plan itself.
    """
    health_conditions = (state.get('health_conditions') or 'None').strip().lower()
    has_health_issues = health_conditions not in ['none', 'nil', 'no', 'nothing', '']
    
    supplements = (state.get('supplements') or 'None').strip()
    has_supplements = supplements.lower() not in ['none', 'nil', 'no', 'nothing', '']
    
    gut_health = (state.get('gut_health') or 'No issues reported').strip().lower()
    has_gut_issues = gut_health not in ['no issues reported', 'none', 'nil', 'no', 'nothing', 'good', 'healthy', '']
    
    disclaimers = []
    
    if has_health_issues:
        disclaimers.append(
            f"⚠️ *Health Condition Notice:* Since you mentioned *{health_conditions}*, "
            f"this meal plan is for informational purposes only. Please consult your healthcare provider "
            f"or a registered dietitian before making any dietary changes."
        )
    
    if has_supplements:
        disclaimers.append(
            f"💊 *Supplement Disclaimer:* The supplement timing suggestions are general guidelines. "
            f"Always follow your healthcare provider's specific instructions for your supplements, "
            f"especially if you're taking medications."
        )
    
    if has_gut_issues:
        disclaimers.append(
            f"🌿 *Gut Health Note:* While this plan includes gut-friendly recommendations, "
            f"if you have persistent digestive issues, please consult a gastroenterologist "
            f"or registered dietitian for personalized care."
        )
    
    if disclaimers:
        return "\n\n" + "\n\n".join(disclaimers)
    return ""


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _remove_llm_disclaimers(plan_text: str) -> str:
    """
    Remove any disclaimers and template markers that the LLM might have generated.
    We add our own standardized disclaimers separately.
    """
    # First, remove template markers that should not appear in output
    template_markers = [
        r'---BEGIN EXACT TEMPLATE---\s*',
        r'\s*---END EXACT TEMPLATE---',
        r'═══════════════════════════════════════════════════════════════\s*',
        r'📋 MANDATORY OUTPUT FORMAT - FOLLOW THIS EXACTLY\s*',
        r'CRITICAL FORMATTING RULES:.*?(?=\*Day|\Z)',
        r'CHECKLIST BEFORE OUTPUTTING:.*?(?=\*Day|\Z)',
        r'🔴 CRITICAL:.*?(?=\*Day|\Z)',
    ]
    
    for pattern in template_markers:
        plan_text = re.sub(pattern, '', plan_text, flags=re.DOTALL | re.IGNORECASE)
    
    # Patterns that match ONLY disclaimer sections (not content sections)
    disclaimer_patterns = [
        # Health Condition Notice disclaimers
        r'⚠️\s*\*?Health Condition Notice\*?:.*?(?=\n\n[⚠️💊🌿]|\n\n---|\Z)',
        # Supplement Disclaimer (NOT Supplement Schedule)
        r'💊\s*\*?Supplement Disclaimer\*?:.*?(?=\n\n[⚠️💊🌿]|\n\n---|\Z)',
        # Gut Health Note (NOT Gut Health Boost)
        r'🌿\s*\*?Gut Health Note\*?:.*?(?=\n\n[⚠️💊🌿]|\n\n---|\Z)',
    ]
    
    for pattern in disclaimer_patterns:
        plan_text = re.sub(pattern, '', plan_text, flags=re.DOTALL | re.IGNORECASE)
    
    return plan_text.strip()


def _extract_meals_from_plan(plan_text: str, previous_meals: dict) -> None:
    """
    Extract meal names from a plan to track for variety in subsequent days.
    Updates the previous_meals dict in place.
    """
    # Patterns to extract meal names
    patterns = {
        'breakfasts': r'BREAKFAST[^:]*:\s*\*?\s*\n\s*([^\n-*]+)',
        'lunches': r'LUNCH[^:]*:\s*\*?\s*\n\s*([^\n-*]+)',
        'dinners': r'DINNER[^:]*:\s*\*?\s*\n\s*([^\n-*]+)',
    }
    
    for meal_type, pattern in patterns.items():
        match = re.search(pattern, plan_text, re.IGNORECASE)
        if match:
            meal_name = match.group(1).strip()
            # Clean up the meal name
            meal_name = meal_name.split('(')[0].strip()  # Remove portion info
            meal_name = meal_name.split(':')[0].strip()  # Remove any trailing info
            if meal_name and len(meal_name) > 3:  # Avoid empty or too short matches
                previous_meals[meal_type].append(meal_name)