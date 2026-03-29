# ------------------ AMS VALIDATION CONFIGURATION ------------------ #
VALIDATION_RULES = {
    "age": {
        "question": "🎂 What's your age?",
        "validation_prompt": """
You are validating an age input. The user was asked: "What's your age?"

ACCEPT any response that indicates an age, including:
- Simple numbers: "25", "30", "45"
- Numbers with text: "I'm 28 years old", "28 years", "28 yrs"
- Age ranges that are reasonable: "mid-20s", "around 30", "late thirties"
- Any number between 15-120 that could realistically be someone's age

Be extremely flexible with formats and natural language expressions of age.

ONLY REJECT responses that are:
- Completely unrelated to age: product questions, random text, technical topics
- Unrealistic ages: numbers above 120 (e.g. 150, 200, 999 are INVALID) or below 10 (e.g. 2, 5, 8, 9 are INVALID)
- Inappropriate content: offensive language, explicit content

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the age question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "height": {
        "question": "📏 What's your height?",
        "validation_prompt": """
You are validating a height input. The user was asked: "What's your height?"

ACCEPT any response that indicates height, including:
- Centimeters: "170 cm", "175", "5'8" in cm", "180cm"
- Feet and inches: "5'8"", "5 feet 8 inches", "5'8", "6 ft"
- Meters: "1.75m", "1.8 meters", "1.70"
- Approximate descriptions: "around 5'8"", "about 170cm", "tall", "average height"
- Any realistic adult height between 120-250 cm or 4'0"-8'0"

Be extremely flexible with units, formats, and natural language expressions.
If the user provides a single digit like "5" or "6", assume they mean feet and ACCEPT it.
If the user provides a number between 10 and 119 with no units (e.g. "20", "50", "100"), REJECT it.

ONLY REJECT responses that are:
- Completely unrelated to height: product questions, random text, technical topics
- Unrealistic heights: extremely short (e.g. 10, 20, 30, 40, 50, 60, 100 cm are INVALID) or tall measurements outside human range (e.g. 300 cm, 500 feet, 10 meters are INVALID)
- Inappropriate content: offensive language, explicit content

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the height question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "weight": {
        "question": "⚖️ What's your weight?",
        "validation_prompt": """
You are validating a weight input. The user was asked: "What's your weight?"

ACCEPT any response that indicates weight, including:
- Kilograms: "70 kg", "75", "80kg", "65 kgs"
- Pounds: "150 lbs", "160 pounds", "170lb"
- Approximate descriptions: "around 70kg", "about 150 lbs", "average weight"
- Any realistic adult weight between 35-250 kg or 75-550 lbs

Be extremely flexible with units, formats, and natural language expressions.
If the user provides a number between 1 and 34 with no units (e.g. "10", "20", "30"), REJECT it.

ONLY REJECT responses that are:
- Completely unrelated to weight: product questions, random text, technical topics
- Unrealistic weights: extremely light (e.g. 5, 10, 20, 30 are INVALID) or heavy measurements outside human range (e.g. 500 kg, 1000 lbs, 2000 lbs are INVALID)
- Inappropriate content: offensive language, explicit content
- Evasive responses: "don't want to tell", "private", "not sharing" (weight is important for health planning)

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the weight question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "health_conditions": {
        "question": "🩺 Do you have any health conditions I should know about?",
        "valid_options": ["none", "diabetes", "ibs", "hypertension", "thyroid", "other"],
        "typo_variations": {
            "none": ["✅ none", "none", "no", "nothing", "nil", "all good", "no conditions"],
            "diabetes": ["🍬 diabetes", "diabetes", "diabetic", "sugar"],
            "ibs": ["💩 ibs/gut issues", "ibs", "gut issues", "digestion issues", "constipation", "bloating"],
            "hypertension": ["💓 hypertension", "hypertension", "high bp", "blood pressure", "high blood pressure"],
            "thyroid": ["🧬 thyroid issues", "thyroid", "hypothyroid", "hyperthyroid"],
            "other": ["⚠️ other", "other", "others", "something else"]
        },
        "validation_prompt": """
You are validating a response about health conditions for meal planning. The user was asked: "Do you have any health conditions I should know about?"

VALID responses include:
- Specific health conditions: "diabetes", "IBS", "hypertension", "thyroid issues", "PCOS", "heart disease", "kidney disease", "celiac disease", "Crohn's disease"
- Statements indicating no conditions: "none", "no", "nothing", "no conditions", "all good", "healthy", "no health issues"
- Medical terms or conditions: "high blood pressure", "high cholesterol", "asthma", "arthritis", "autoimmune disease"
- Vague but relevant: "some digestive issues", "minor health problems", "doctor said I have...", "diagnosed with..."

INVALID responses - REJECT these:
- Food items or meals: "rice", "chicken", "eggs", "bread", "vegetables", "meat", "fish", "dal", "roti", "pasta", "salad"
- Meal descriptions: "rice and chicken", "eggs and toast", "dal chawal", "chicken curry", "vegetable soup"
- Dinner/lunch/breakfast items: Any description that sounds like a meal or food combination

- Completely unrelated topics: greetings, random text, product questions
- Empty or unclear responses: just "yes", "yeah", "ok" without specifying a condition

CRITICAL RULE: If the response mentions ANY food items, ingredients, or meal descriptions (like "rice", "chicken", "vegetables", "dal", "roti", "eggs", "bread", "pasta", etc.), it is INVALID. The user is likely confusing this with a meal question.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of "anti depression",
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no "nice", "cool", "great").
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the health conditions question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "medications": {
        "question": "💊 Just to help us understand better, could you tell me if you're on any medications? Feel free to say 'none' if not.",
        "validation_prompt": """
    You are validating a response about medications. The user was asked: "Just to help us understand better, could you tell me if you're on any medications? Feel free to say 'none' if not."

    Valid responses include:
    - Specific medication names: "metformin", "insulin", "levothyroxine", "lisinopril", "omeprazole", "aspirin"
    - General medication descriptions: "diabetes medication", "blood pressure pills", "thyroid medicine", "antacid"
    - Multiple medications: "metformin and atorvastatin", "insulin + blood pressure meds", "metformin, levothyroxine"
    - Statements indicating no medications: "none", "no", "not taking any", "no medications", "nothing", "none at all", "nope", "nah", "n/a", "na"
    - Simple affirmatives (user confirming without listing): "yes", "yeah", "yep", "yup" — ACCEPT these; user is confirming they take something without describing.
    - Uncertain or privacy-based replies: "not sure", "prefer not to say", "don't want to share", "rather not share", "idk", "I don't know", "unsure", "can't remember"
    - Casual/informal responses: "just vitamins", "some pills", "nothing regular", "only when needed", "supplements only"
    - The Good Bug products (treat as supplements/medications, NOT as product questions):
    * "Metabolically Lean AMS", "AMS", "Advanced Metabolic System"
    * "Metabolically Lean Supercharged", "Supercharged"
    * "PCOS Balance", "PCOD Balance"
    * "Gut Balance"
    * "Bye Bye Bloat"
    * "Smooth Move"
    * "IBS Rescue", "IBS C", "IBS Constipation"
    * "IBS DnM", "IBS D&M", "IBS D", "IBS M", "IBS Diarrhea", "IBS Mixed"
    * "First Defense", "First Defence"
    * "Sleep and Calm"
    * "Good Down There"
    * "Good to Glow"
    * "Happy Tummies"
    * "Acidity Aid"
    * "Gut Cleanse"
    * "Metabolic Fiber Boost", "Metabolic Fiber"
    * "Smooth Move Fiber Boost", "Smooth Fiber"
    * "Prebiotic Fiber Boost", "Fiber Boost"
    * "Water Kefir", "Kefir"
    * "Kombucha"

    IMPORTANT: If the user mentions any of The Good Bug products, accept it as a VALID medication response. Do NOT treat it as a product question. They are sharing what they currently consume as part of their health regimen.

    Be extremely flexible with typos, brand names, generic names, and casual descriptions.
    Accept responses that clearly indicate medications or confirm none are being taken.
    Be friendly and empathetic - users may be hesitant about sharing medications.

    Invalid responses: 
    - Empty or blank responses (no text provided)
    - Completely unrelated topics (e.g., "good morning", "how are you", "thanks")
    - Random text or greetings
    - Questions asking about products (e.g., "what is AMS?", "how does PCOS Balance work?", "tell me about X")

    CRITICAL RULES:
    1. Empty/blank input = INVALID (no information provided)
    2. "yes"/"yeah"/"yep"/"yup" alone = VALID (user confirming without listing)
    3. "n/a" or "na" = VALID
    4. "idk"/"I don't know" = VALID (valid uncertain response)
    5. "AMS" alone = VALID (it's a Good Bug product they're taking)
    6. "what is AMS?" = INVALID (it's a question, not an answer)
    7. "just vitamins" = VALID (valid casual response about supplements)

    User input: "{input}"

    Is this input relevant and valid for the medications question?
    Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
    """
    },
    
    # ------------------ AMS SPECIFIC VALIDATIONS ------------------ #
    
    "diet_preference": {
        "question": "🥗 What's your dietary preference?",
        "validation_prompt": """
You are validating a dietary preference. The user was asked: "What's your dietary preference?"

Valid responses include:
- Diet types: "vegetarian", "non-veg", "vegan", "keto", "eggitarian", "pescatarian", "palio", "halal", "kosher", "jain"
- Descriptions: "I eat everything", "no meat", "mostly plants", "low carb", "pure veg", "only chicken", "no beef"
- Combinations: "veg but eat eggs", "chicken only", "fish only"

Be flexible with typos ("vegitarian", "nonveg").
Accept simple confirmations like "veg", "non veg", "vegan".

Invalid responses: completely unrelated topics or random text.

User input: "{input}"

Is this input relevant and valid for dietary preference?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "cuisine_preference": {
        "question": "🍛 Now, Do you have any cuisine preferences?",
        "validation_prompt": """
You are validating a cuisine preference. The user was asked: "Do you have any cuisine preferences?"

Valid responses include:
- Specific cuisines: "Indian", "Chinese", "Italian", "Mexican", "Continental", "Thai", "Japanese", "South Indian", "North Indian"
- Flavors/types: "spicy", "bland", "home cooked", "simple food", "less oil", "ghar ka khana"
- No preference: "anything", "all types", "no preference", "whatever is healthy", "mixed"
- "None", "No" -> implies no specific preference (VALID)

Be flexible with typos.

Invalid responses: completely unrelated topics.

User input: "{input}"

Is this input relevant and valid for cuisine preference?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "current_dishes": {
        "question": "🍛 What are some of your favorite dishes or meals that you eat regularly?",
        "validation_prompt": """
You are validating a response about current meals. The user was asked: "What are some of your favorite dishes..."

VALID responses include:
- Dish names: "dal chawal", "roti sabzi", "pasta", "salad", "chicken curry"
- Meal descriptions: "oats for breakfast", "soup for dinner"
- General descriptions: "typical indian food", "home food"

INVALID responses: generic unrelated text.

User input: "{input}"
Is this input relevant and valid?
Respond with only "VALID" or "INVALID".
"""
    },
    "allergies": {
        "question": "🚫 Do you have any food allergies or intolerances?",
        "validation_prompt": """
You are validating an allergy/intolerance response. The user was asked: "Do you have any food allergies or intolerances?"

Valid responses include:
- Specific allergens: "peanuts", "dairy", "gluten", "soy", "shellfish", "eggs", "mushrooms", "brinjal"
- Intolerances: "lactose intolerant", "gluten sensitivity", "cannot digest milk"
- Confirmation of none: "no", "none", "nothing", "all good", "no allergies", "nope"
- Dietary restrictions stated as allergies: "no beef", "no pork" (Treat as VALID context)

Be flexible with typos.

Invalid responses: completely unrelated topics.

User input: "{input}"

Is this input relevant and valid for allergies?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "water_intake": {
        "question": "💧 Hydration check! Roughly how much *water* do you drink in a day?\nYou can answer in glasses or liters 💦",
        "validation_prompt": """
You are validating water intake. The user was asked: "Roughly how much water do you drink in a day?"

Valid responses include:
- Volume: "2 liters", "3-4 liters", "1.5L", "500ml", "one gallon"
- Glasses/Bottles: "8 glasses", "2 bottles", "10 cups", "plenty"
- Qualitative: "a lot", "not enough", "too little", "average", "good amount"
- Frequency: "sip all day"

Be flexible with units and estimations.

Invalid responses: completely unrelated topics.

User input: "{input}"

Is this input relevant and valid for water intake?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "beverages": {
        "question": "☕ Any other beverages you regularly have? (Tea, Coffee, Soft drinks, None) If yes, how many cups/glasses per day?",
        "validation_prompt": """
You are validating beverages intake. The user was asked: "Any other beverages you regularly have? (Tea, Coffee, Soft drinks, None)..."

Valid responses include:
- Drink types: "coffee", "tea", "chai", "green tea", "alcohol", "beer", "wine", "cola", "juice", "milk"
- Confirmation of none: "none", "no other drinks", "just water", "nothing else"
- Combinations with quantities: "2 cups coffee", "morning tea", "occasional beer"

Be flexible with typos.

Invalid responses: completely unrelated topics.

User input: "{input}"

Is this input relevant and valid for beverages?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "supplements": {
        "question": "💊 Are you currently taking any supplements? (Vitamins, Minerals, Protein powder, etc.)",
        "validation_prompt": """
You are validating a supplements response. The user was asked: "Are you currently taking any supplements? (Vitamins, Minerals, Protein powder, etc.)"

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
    "gut_health": {
        "question": "💩 How's your gut health? Do you experience any of these digestive issues?",
        "validation_prompt": """
You are validating a gut health response. The user was asked: "How's your gut health? Do you experience any of these digestive issues?"

Valid responses include:
- Specific digestive issues: "constipation", "gas", "bloating", "acidity", "heartburn", "irregular bowel movements", "diarrhea", "IBS"
- Multiple issues: "constipation and bloating", "gas + acidity", "several issues", "all of them"
- Statements indicating no issues: "none", "no", "all good", "no issues", "everything's fine", "healthy", "no problems"
- General descriptions: "sometimes constipated", "occasional bloating", "rarely", "not much", "mild issues"
- Privacy or uncertain replies: "prefer not to say", "don't want to tell", "rather not share", "not sure", "maybe"

Be empathetic and flexible — gut health can be a sensitive topic. Accept casual descriptions, typos, and vague responses.

Invalid responses: completely unrelated topics, random text, greetings, or off-topic content not about digestion.

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the gut health question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "meal_goals": {
        "question": "🎯 Finally, what are your main nutrition goals?",
        "validation_prompt": """
You are validating a nutrition goals response. The user was asked: "Finally, what are your main nutrition goals?"

Valid responses include:
- Common goals: "weight loss", "weight gain", "maintain weight", "better energy", "gut healing", "improve immunity", "healthy lifestyle", "feel fit", "overall wellness", "loose weight", "stay helthy", "gain muscel"
- Broader intents: "get healthier", "eat clean", "feel energetic", "tone up", "eat better"
- Neutral or uncertain replies: "not sure", "no goals", "just maintaining", "nothing specific"

Be flexible and kind — users may express their goals casually, vaguely, or with typos.
Accept short, natural language replies as valid if they reflect any nutrition, body, or wellness intent.

Invalid responses: completely unrelated topics or meaningless text (e.g., greetings, random words).

IMPORTANT SAFETY CHECK:
If the user message expresses sadness, depression, anxiety, hopelessness, mentions of “anti depression”,
or any mental/emotional distress, you MUST NOT respond casually or positively (e.g., no “nice”, “cool”, “great”).
In such cases, you should still perform the validation task (VALID/INVALID), but the system will override
the conversational reply and send a dedicated, supportive mental-health-safe message instead.

User input: "{input}"

Is this input relevant and valid for the nutrition goals question?
Respond with only "VALID" or "INVALID". If invalid, explain why briefly.
"""
    },
    "fitness_level": {
        "question": "🏃‍♂️ Let's start with where you're at! How would you describe your current fitness level?",
        "valid_options": ["beginner", "intermediate", "advanced"],
        "typo_variations": {
            "beginner": ["🆕 beginner", "beginner", "just starting", "sedentary", "newbie"],
            "intermediate": ["🔥 intermediate", "intermediate", "active", "3-6 months"],
            "advanced": ["💪 advanced", "advanced", "pro", "regular", "athlete", "expert"]
        },
        "validation_prompt": """
        You are validating a fitness level response. The user was asked: "How would you describe your current fitness level?"
        
        Valid responses include:
        - "beginner", "intermediate", "advanced"
        - Descriptions matching these levels (e.g., "just starting out", "been training for years")
        
        Invalid responses: completely unrelated topics.
        
        User input: "{input}"
        Is this input relevant and valid? Respond with only "VALID" or "INVALID".
        """
    },
    "activity_types": {
        "question": "🏃‍♀️ What types of physical activities did you do in the last week?",
        "valid_options": ["walking", "running", "cycling", "yoga", "gym", "sports", "none"],
        "typo_variations": {
            "walking": ["🚶 walking", "walking", "walk"],
            "running": ["🏃 running/jogging", "running", "jogging", "run"],
            "cycling": ["🚴 cycling", "cycling", "bike", "biking"],
            "yoga": ["🧘 yoga/pilates", "yoga", "pilates", "stretching"],
            "gym": ["🏋️ gym/weights", "gym", "weights", "strength", "lifting"],
            "sports": ["⚽ sports", "sports", "football", "cricket", "basketball", "tennis"],
            "none": ["❌ none", "none", "no activity", "nothing"]
        },
        "validation_prompt": """
        You are validating activity types. The user was asked: "What types of physical activities did you do in the last week?"
        
        Valid responses include: any physical activity or "none".
        
        User input: "{input}"
        Is this input relevant and valid? Respond with only "VALID" or "INVALID".
        """
    },
    "exercise_frequency": {
        "question": "📅 How many days per week do you typically exercise?",
        "valid_options": ["0", "1-2", "3-4", "5-6", "7"],
        "typo_variations": {
            "0": ["🛋️ 0 days", "0 days", "0", "zero", "none"],
            "1-2": ["🚶 1-2 days", "1-2 days", "1", "2", "once", "twice"],
            "3-4": ["🏃 3-4 days", "3-4 days", "3", "4", "three", "four"],
            "5-6": ["💪 5-6 days", "5-6 days", "5", "6", "five", "six"],
            "7": ["🔥 7 days", "7 days", "7", "seven", "every day", "daily"]
        },
        "validation_prompt": """
        You are validating exercise frequency. The user was asked: "How many days per week do you typically exercise?"
        
        Valid responses include: number of days or ranges (0-7).
        
        User input: "{input}"
        Is this input relevant and valid? Respond with only "VALID" or "INVALID".
        """
    },
    "exercise_intensity": {
        "question": "💨 When you exercise, how would you describe your effort level?",
        "valid_options": ["light", "moderate", "vigorous"],
        "typo_variations": {
            "light": ["😌 light", "light", "easy", "low"],
            "moderate": ["💬 moderate", "moderate", "medium", "average"],
            "vigorous": ["😤 vigorous", "vigorous", "hard", "intense", "high"]
        },
        "validation_prompt": """
        You are validating exercise intensity. The user was asked: "How would you describe your effort level?"
        
        Valid responses include: intensity levels (light, moderate, vigorous).
        
        User input: "{input}"
        Is this input relevant and valid? Respond with only "VALID" or "INVALID".
        """
    },
    "session_duration": {
        "question": "⏱️ On average, how long are your exercise sessions?",
        "valid_options": ["15", "30", "45", "60", "90"],
        "typo_variations": {
            "15": ["⚡ 15 minutes", "15 minutes", "15 mins", "15"],
            "30": ["🏃 30 minutes", "30 minutes", "30 mins", "half hour"],
            "45": ["💪 45 minutes", "45 minutes", "45 mins"],
            "60": ["🔥 1 hour", "1 hour", "60 mins", "60 minutes", "one hour"],
            "90": ["🏆 90+ minutes", "90+ minutes", "90 mins", "1.5 hours"]
        },
        "validation_prompt": """
        You are validating session duration. The user was asked: "How long are your exercise sessions?"
        
        Valid responses include: time durations (minutes, hours).
        
        User input: "{input}"
        Is this input relevant and valid? Respond with only "VALID" or "INVALID".
        """
    },
    "sedentary_time": {
        "question": "🪑 Roughly how many hours per day do you spend sitting or lying down?",
        "valid_options": ["2-4", "4-6", "6-8", "8-10", "10+"],
        "typo_variations": {
            "2-4": ["🚶 2-4 hours", "2-4 hours", "2-4"],
            "4-6": ["💺 4-6 hours", "4-6 hours", "4-6"],
            "6-8": ["🪑 6-8 hours", "6-8 hours", "6-8"],
            "8-10": ["😴 8-10 hours", "8-10 hours", "8-10"],
            "10+": ["🛋️ 10+ hours", "10+ hours", "10 plus", "more than 10"]
        },
        "validation_prompt": """
        You are validating sedentary time. The user was asked: "How many hours per day do you spend sitting?"
        
        Valid responses include: time ranges for sitting.
        
        User input: "{input}"
        Is this input relevant and valid? Respond with only "VALID" or "INVALID".
        """
    },
    "exercise_goals": {
        "question": "🎯 What are your main fitness goals?",
        "valid_options": ["weight_loss", "muscle_gain", "lean", "flexibility", "wellness"],
        "typo_variations": {
            "weight_loss": ["📉 weight loss", "weight loss", "lose weight", "fat loss"],
            "muscle_gain": ["💪 muscle gain", "muscle gain", "build muscle", "strength"],
            "lean": ["🏃 lean & athletic", "lean & athletic", "lean", "athletic", "tone"],
            "flexibility": ["🧘 flexibility", "flexibility", "mobility", "stretching"],
            "wellness": ["🌟 general wellness", "general wellness", "wellness", "health", "maintenance"]
        },
        "validation_prompt": """
        You are validating exercise goals. The user was asked: "What are your main fitness goals?"
        
        Valid responses include: specific fitness goals.
        
        User input: "{input}"
        Is this input relevant and valid? Respond with only "VALID" or "INVALID".
        """
    }
}