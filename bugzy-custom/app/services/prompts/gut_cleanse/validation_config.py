# ==============================================================================
# GUT CLEANSE VALIDATION CONFIGURATION
# ==============================================================================
#
# This file contains validation rules for ONLY the Gut Cleanse flow:
# - Required profiling questions (5 questions)
# - New 11-question meal plan
#
# NOTE: Legacy fields (age, height, weight) are removed as they're not used
# in the Gut Cleanse flow.
# ==============================================================================

VALIDATION_RULES = {
    # ==============================================================================
    # REQUIRED PROFILING QUESTIONS (5 questions before meal plan)
    # ==============================================================================
    "health_safety_screening": {
        "question": "💚 This helps ensure the cleanse is safe for you\n\nSelect the option that applies",
        "valid_options": [
            "healthy",
            "health_safe_healthy",
            "health_block_under_18", "health_block_pregnant", "health_block_ulcers", "health_block_diarrhea", "health_block_ibs_ibd",
            "health_consult_diabetes_bp", "health_consult_kidney", "health_consult_constipation", "health_consult_surgery", "health_consult_hypothyroid"
        ],
        # WhatsApp sends button IDs, titles, and descriptions - we need to match all variations
        "typo_variations": {
            "healthy": ["healthy", "none", "fit", "health_safe_healthy", "none of these"],
            "gut_condition": [
                # Button IDs from "Not Recommended" section
                "health_block_under_18", "health_block_pregnant", "health_block_ulcers", "health_block_diarrhea", "health_block_ibs_ibd",
                # Display text and variations
                "gut condition", "stomach issues", "under 18", "below 18", "pregnant", "breastfeeding", "nursing",
                "ulcers", "ulcer", "stomach ulcers", "gastric ulcers",
                "diarrhea", "chronic diarrhea", "loose motions",
                "ibs", "ibd", "bowel", "bowel diseases", "irritable bowel", "inflammatory bowel"
            ],
            "medical_condition": [
                # Button IDs from "Consult Doctor" section
                "health_consult_diabetes_bp", "health_consult_kidney", "health_consult_constipation", "health_consult_surgery", "health_consult_hypothyroid",
                # Display text and variations for all conditions
                "medical condition",
                # Diabetes/BP variations
                "diabetes", "bp", "blood pressure", "blood sugar", "pressure", "hypertension",
                # Kidney variations
                "kidney", "kidney disease", "kidney conditions", "chronic kidney",
                # Constipation variations (IMPORTANT: needed for button clicks sending "Constipation")
                "constipation", "chronic constipation", "constipated",
                # Surgery variations
                "surgery", "recent surgery", "3 months",
                # Thyroid variations
                "hypothyroid", "thyroid", "thyroid imbalance", "underactive thyroid"
            ]
        },
        "validation_prompt": """
You are validating health safety status for a gut cleanse screening. User must select one of:
- Healthy/None of these
- Not Recommended: Under 18, Pregnant, Ulcers, Chronic Diarrhea, IBS/IBD
- Consult Doctor: Diabetes/BP, Kidney Disease, Constipation, Recent Surgery, Hypothyroid

VALID: Any of the above categories (including button IDs, display names, and variations)
INVALID: Completely unrelated text, greetings only, empty responses

User input: "{input}"
Is this valid health status response?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    
    "detox_experience": {
        "question": "🌿 Experience check\n\nHave you done a gut cleanse or detox before?",
        "valid_options": ["detox_exp_no", "detox_exp_recent", "detox_exp_long_ago"],
        "typo_variations": {
            "no": [
                "detox_exp_no",  # Button ID
                "no", "no, first time", "never", "first time", "haven't", "not yet",
                "this is my first", "i haven't done one before"
            ],
            "recent": [
                "detox_exp_recent",  # Button ID
                "yes", "recently", "yes, recently", "recent", "last month", "6 months",
                "less than 6 months", "in the last 6 months", "< 6 months"
            ],
            "long_ago": [
                "detox_exp_long_ago",  # Button ID
                "long ago", "years ago", "before", "yes but long ago", "long time ago",
                "more than 6 months", "> 6 months", "ages ago"
            ]
        },
        "validation_prompt": """
You are validating detox experience. User must select one of:
- No/First time
- Yes, recently (< 6 months)
- Yes, but long ago (> 6 months)

VALID: Any of the above categories (including button IDs and variations)
INVALID: Completely unrelated text, greetings only, empty responses

User input: "{input}"
Is this valid detox experience response?
        Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    
    "detox_recent_reason": {
        "question": "Why are you doing another cleanse so soon?",
        "valid_options": ["detox_reason_incomplete", "detox_reason_no_results", "detox_reason_symptoms_back", "detox_reason_maintenance"],
        "typo_variations": {
            "incomplete": [
                "detox_reason_incomplete",
                "didn't finish", "didnt finish", "incomplete", "left in middle", "stopped halfway",
                "couldn't complete", "could not finish"
            ],
            "no_results": [
                "detox_reason_no_results",
                "no results", "didn't work", "didnt work", "no changes", "didn't see changes",
                "no effect", "did nothing"
            ],
            "symptoms_back": [
                "detox_reason_symptoms_back",
                "symptoms back", "symptoms came back", "feeling bad again", "bloated again",
                "issues returned", "problems came back", "symptoms returned"
            ],
            "maintenance": [
                "detox_reason_maintenance",
                "maintenance", "routine", "stay healthy", "regular cleanse", "just maintaining",
                "keeping gut healthy", "regular detox"
            ]
        },
        "validation_prompt": """
You are validating the reason for a recent detox. User must select one of:
- Didn't finish
- No results
- Symptoms back
- Maintenance

VALID: Any of the above categories (including button IDs and variations)
INVALID: Completely unrelated text, greetings only, empty responses

User input: "{input}"
Is this valid reason response?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },


    # ==============================================================================
    # GUT CLEANSE MEAL PLAN (11-QUESTION FLOW)
    # ==============================================================================
    # Q1: Dietary Preference
    "dietary_preference": {
        "question": "🥗 What's your dietary preference?",
        "valid_options": [
            "non_vegetarian",
            "pure_vegetarian",
            "eggitarian",
            "vegan",
            "pescatarian",
            "flexitarian",
            "keto",
        ],
        "typo_variations": {
            "non_vegetarian": ["diet_non_veg", "non vegetarian", "non-vegetarian", "nonveg", "non veg", "eat everything", "meat", "chicken", "mutton", "fish"],
            "pure_vegetarian": ["diet_pure_veg", "pure vegetarian", "pure veg", "vegetarian", "veg", "no meat", "no nonveg", "lacto vegetarian"],
            "eggitarian": ["diet_eggitarian", "eggitarian", "eggetarian", "veg + eggs", "vegetarian with eggs", "eat eggs"],
            "vegan": ["diet_vegan", "vegan", "no animal products", "plant based", "plant-based"],
            "pescatarian": ["diet_pescatarian", "pescatarian", "veg + fish", "fish only", "seafood"],
            "flexitarian": ["diet_flexitarian", "flexitarian", "mostly veg", "mostly plant based", "occasionally meat", "sometimes non veg"],
            "keto": ["diet_keto", "keto", "low carb", "low-carb", "high fat", "high-fat"],
        },
        "validation_prompt": """
You are validating dietary preference for a gut cleanse meal plan. The user was asked: "What's your dietary preference?"

VALID responses include:
- Any of these diet types (even with typos): non-vegetarian, vegetarian/pure veg, eggitarian, vegan, pescatarian, flexitarian, keto
- Natural language equivalents: "I eat everything", "no meat", "veg but eggs", "mostly plant based", "low carb", "fish only"
- Button/list selections, including internal button IDs like: diet_non_veg, diet_pure_veg, diet_eggitarian, diet_vegan, diet_pescatarian, diet_flexitarian, diet_keto

INVALID responses:
- Completely unrelated topics, greetings only, random text with no diet meaning
- Empty/blank responses

User input: "{input}"
Is this input relevant and valid for dietary preference?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "cuisine_preference": {
        "question": "🍛 Do you have any cuisine preferences?",
        "valid_options": [
            "north_indian",
            "south_indian",
            "gujarati",
            "bengali",
            "chinese",
            "italian",
            "mexican",
            "all_cuisines",
        ],
        "typo_variations": {
            "north_indian": ["cuisine_north_indian", "north indian", "punjabi", "roti", "paneer", "curry"],
            "south_indian": ["cuisine_south_indian", "south indian", "dosa", "idli", "sambar", "rasam"],
            "gujarati": ["cuisine_gujarati", "gujarati", "dhokla", "thepla", "khandvi"],
            "bengali": ["cuisine_bengali", "bengali", "fish curry", "mishti doi", "rasgulla"],
            "chinese": ["cuisine_chinese", "chinese", "noodles", "stir fry", "stir-fry", "dim sum", "dimsum"],
            "italian": ["cuisine_italian", "italian", "pasta", "pizza", "risotto"],
            "mexican": ["cuisine_mexican", "mexican", "tacos", "burrito", "guacamole"],
            "all_cuisines": ["cuisine_all", "all cuisines", "all", "anything", "no preference", "mixed"],
        },
        "validation_prompt": """
You are validating cuisine preference for a gut cleanse meal plan. The user was asked: "Do you have any cuisine preferences?"

VALID responses include:
- Any cuisine selection from the list (North Indian, South Indian, Gujarati, Bengali, Chinese, Italian, Mexican, All cuisines)
- "No preference", "anything", "all cuisines"
- Button/list selections, including internal IDs like: cuisine_north_indian, cuisine_south_indian, cuisine_gujarati, cuisine_bengali, cuisine_chinese, cuisine_italian, cuisine_mexican, cuisine_all

INVALID responses: completely unrelated topics or empty/blank responses.

User input: "{input}"
Is this input relevant and valid for cuisine preference?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "food_allergies_intolerances": {
        "question": "🚫 Do you have any food allergies or intolerances?",
        "valid_options": [
            "no_allergies",
            "dairy_allergy",
            "gluten_allergy",
            "nut_allergy",
            "egg_allergy",
            "multiple_allergies",
            "lactose_intolerant",
            "gluten_sensitive",
            "spice_intolerant",
            "multiple_intolerances",
        ],
        "typo_variations": {
            "no_allergies": ["allergy_none", "no allergies", "none", "no", "nothing", "no allergy"],
            "dairy_allergy": ["allergy_dairy", "dairy allergy", "milk allergy", "casein allergy"],
            "gluten_allergy": ["allergy_gluten", "gluten allergy", "celiac", "coeliac"],
            "nut_allergy": ["allergy_nuts", "nut allergy", "peanut allergy", "nuts allergy"],
            "egg_allergy": ["allergy_eggs", "egg allergy", "eggs allergy"],
            "multiple_allergies": ["allergy_multiple", "multiple allergies", "many allergies", "several allergies"],
            "lactose_intolerant": ["intolerance_lactose", "lactose intolerant", "lactose intolerance", "cannot digest milk"],
            "gluten_sensitive": ["intolerance_gluten", "gluten sensitive", "gluten sensitivity"],
            "spice_intolerant": ["intolerance_spicy", "spice intolerant", "spicy intolerant", "can't handle spicy", "cant handle spicy"],
            "multiple_intolerances": ["intolerance_multiple", "multiple intolerances", "many intolerances", "several intolerances"],
        },
        "validation_prompt": """
You are validating allergies/intolerances for a gut cleanse meal plan. The user was asked: "Do you have any food allergies or intolerances?"

VALID responses include:
- Any of these selections (single or multiple): No allergies, Dairy allergy, Gluten allergy, Nut allergy, Egg allergy, Multiple allergies, Lactose intolerant, Gluten sensitive, Spice intolerant, Multiple intolerances
- Free text listing allergens/intolerances (e.g., "dairy", "milk", "gluten", "nuts", "eggs", "lactose intolerant", "spice intolerant")
- Multi-select style responses separated by commas/new lines
- Button/list selections, including internal IDs like: allergy_none, allergy_dairy, allergy_gluten, allergy_nuts, allergy_eggs, allergy_multiple, intolerance_lactose, intolerance_gluten, intolerance_spicy, intolerance_multiple

INVALID responses:
- Completely unrelated topics or empty/blank responses

User input: "{input}"
Is this input relevant and valid for allergies/intolerances?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "daily_eating_pattern": {
        "question": "🍽️ What do you usually eat throughout the day? (Share any 3 dishes)",
        "validation_prompt": """
You are validating a daily eating pattern response. The user was asked: "What do you usually eat throughout the day? (Share any 3 dishes)"

VALID responses include:
- Dish names or meal descriptions: "idli, dal rice, veg curry", "oats and fruit", "roti sabzi", "egg sandwich", "chicken curry"
- Rough lists (comma-separated), short sentences, or typical day description
- If the user says "I don't know" / "not sure" / "varies" -> still VALID

INVALID responses:
- Empty/blank responses
- Completely unrelated topics (greetings only, product questions, random text)

User input: "{input}"
Is this input relevant and valid for daily eating pattern?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "foods_avoid": {
        "question": "🚨 Any foods you absolutely avoid or dislike?",
        "validation_prompt": """
You are validating foods to avoid/dislike. The user was asked: "Any foods you absolutely avoid or dislike?"

VALID responses include:
- "None" / "No restrictions" / "no" / "nothing"
- Lists of foods/ingredients: "broccoli", "paneer", "mushrooms", "spicy food", "milk", "gluten"
- Short sentences describing dislikes/avoidances

INVALID responses:
- Empty/blank responses
- Completely unrelated topics

User input: "{input}"
Is this input relevant and valid for foods to avoid/dislike?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "supplements": {
        "question": "💊 Are you currently taking any supplements?",
        "validation_prompt": """
You are validating a supplements response. The user was asked: "Are you currently taking any supplements?"

Valid responses include:
- Specific supplements: "vitamin D", "multivitamin", "protein powder", "omega-3", "fish oil", "calcium", "magnesium", "B12", "zinc"
- Multiple supplements: "vitamin D and omega-3", "multivitamin + protein powder", "several vitamins"
- General descriptions: "some vitamins", "protein supplement", "just vitamins", "a few supplements"
- Statements indicating no supplements: "none", "no", "not taking any", "no supplements", "nothing", "don't take any"
- Uncertain or privacy-based replies: "not sure", "prefer not to say", "don't want to share", "maybe", "sometimes"

Be flexible with typos, brand names, and casual descriptions. Accept responses that clearly indicate supplements or confirm none are being taken.

Invalid responses: completely unrelated topics, random text, greetings, or off-topic questions not about supplements.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the supplements question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "digestive_issues": {
        "question": "🤍 Quick digestion check-in — do you experience any digestive issues?",
        "valid_options": [
            "bloating",
            "constipation",
            "acidity_or_heartburn",
            "gas",
            "irregular_bowel_movements",
            "heavy_or_slow_digestion",
            "sugar_cravings",
            "none_currently",
        ],
        "typo_variations": {
            "bloating": ["digestive_bloating", "bloating", "bloated", "gas bloating"],
            "constipation": ["digestive_constipation", "constipation", "constipated"],
            "acidity_or_heartburn": ["digestive_acidity", "acidity", "heartburn", "acid reflux", "reflux"],
            "gas": ["digestive_gas", "gas", "gassy", "flatulence"],
            "irregular_bowel_movements": ["digestive_irregular", "irregular bowel", "irregular bowel movements", "irregular motions", "inconsistent stools"],
            "heavy_or_slow_digestion": ["digestive_heavy", "heavy digestion", "slow digestion", "sluggish digestion"],
            "sugar_cravings": ["digestive_sugar", "sugar cravings", "crave sugar", "sweet cravings"],
            "none_currently": ["digestive_none", "none currently", "none", "no issues", "all good", "fine"],
        },
        "validation_prompt": """
You are validating digestive issues for a gut cleanse meal plan. The user was asked to choose any digestive issues they experience (multi-select).

VALID responses include:
- Any of these (single or multiple): bloating, constipation, acidity/heartburn, gas, irregular bowel movements, heavy/slow digestion, sugar cravings, none currently
- Multi-select style responses separated by commas/new lines
- Button/list selections, including internal IDs like: digestive_bloating, digestive_constipation, digestive_acidity, digestive_gas, digestive_irregular, digestive_heavy, digestive_sugar, digestive_none

INVALID responses: completely unrelated topics or empty/blank responses.

User input: "{input}"
Is this input relevant and valid for digestive issues?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "hydration": {
        "question": "💧 Hydration check — how much water do you drink per day?",
        "valid_options": ["less_than_1_liter", "one_to_two_liters", "two_to_three_liters", "more_than_3_liters"],
        "typo_variations": {
            "less_than_1_liter": ["hydration_less_1l", "less than 1 liter", "less than 1 litre", "<1l", "below 1l", "very less", "hardly"],
            "one_to_two_liters": ["hydration_1_2l", "1-2 liters", "1–2 liters", "1 to 2 liters", "1-2 litre", "1.5l", "about 2l"],
            "two_to_three_liters": ["hydration_2_3l", "2-3 liters", "2–3 liters", "2 to 3 liters", "2.5l", "about 3l"],
            "more_than_3_liters": ["hydration_more_3l", "more than 3 liters", ">3l", "above 3l", "3+ liters", "4 liters"],
        },
        "validation_prompt": """
You are validating hydration for a gut cleanse meal plan. The user was asked: "How much water do you drink per day?"

VALID responses include:
- Any of the listed options (Less than 1 liter / 1–2 liters / 2–3 liters / More than 3 liters)
- Approximate numeric answers: "2L", "2 liters", "8 glasses", "3+ liters"
- Button/list selections, including internal IDs like: hydration_less_1l, hydration_1_2l, hydration_2_3l, hydration_more_3l

INVALID responses: completely unrelated topics or empty/blank responses.

User input: "{input}"
Is this input relevant and valid for hydration?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "other_beverages": {
        "question": "☕ Other beverages — how many cups daily?",
        "valid_options": ["none", "one_to_two", "three_to_four", "five_plus"],
        "typo_variations": {
            "none": ["beverages_none", "none", "no beverages", "no other drinks", "just water", "nothing else"],
            "one_to_two": ["beverages_1_2", "1-2 cups", "1–2 cups", "one to two", "1 or 2", "2 cups"],
            "three_to_four": ["beverages_3_4", "3-4 cups", "3–4 cups", "three to four", "4 cups"],
            "five_plus": ["beverages_5_plus", "5+ cups", "5 cups", "more than 4", "many cups", "a lot"],
        },
        "validation_prompt": """
You are validating other beverages intake for a gut cleanse plan. The user was asked how many cups daily of other beverages they have.

VALID responses include:
- Any of the listed options: None / 1–2 cups daily / 3–4 cups daily / 5+ cups daily
- Numeric answers like "2 cups", "3 cups", "5 cups", "0"
- Button/list selections, including internal IDs like: beverages_none, beverages_1_2, beverages_3_4, beverages_5_plus

INVALID responses: completely unrelated topics or empty/blank responses.

User input: "{input}"
Is this input relevant and valid for other beverages?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "gut_sensitivity": {
        "question": "🌿 How sensitive is your stomach?",
        "valid_options": ["very_sensitive", "moderately_sensitive", "not_sensitive"],
        "typo_variations": {
            "very_sensitive": ["sensitivity_very", "very sensitive", "highly sensitive", "very", "too sensitive"],
            "moderately_sensitive": ["sensitivity_moderate", "moderately sensitive", "moderate", "sometimes sensitive", "somewhat sensitive"],
            "not_sensitive": ["sensitivity_not", "not sensitive", "no sensitivity", "fine", "strong stomach"],
        },
        "validation_prompt": """
You are validating gut sensitivity. The user was asked: "How sensitive is your stomach?"

VALID responses include:
- Very sensitive / Moderately sensitive / Not sensitive
- Natural language equivalents (even with typos): "my stomach is very sensitive", "moderate", "not sensitive"
- Button/list selections, including internal IDs like: sensitivity_very, sensitivity_moderate, sensitivity_not

INVALID responses: completely unrelated topics or empty/blank responses.

User input: "{input}"
Is this input relevant and valid for gut sensitivity?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
}