# ==============================================================================
# NODE CONFIGURATION & MAPPING (minimal for free_form)
# ==============================================================================

QUESTION_TO_NODE = {
    "verified": "post_plan_qna",
    "post_plan_qna": "post_plan_qna",
    "transitioning_to_snap": "snap_image_analysis",
}

TRANSITION_MESSAGES = [
    "All set! You can ask me anything about your products or general health.",
    "Ready when you are! Ask me anything about your products or general wellness.",
]

# ---------------------------------------------------------------------------
# Product / QnA routing constants
# ---------------------------------------------------------------------------

PRODUCT_SPECIFIC_KEYWORDS = [
    "stick", "sticks", "shots", "bottles", "jar", "scoop", "serving",
    "variants", "flavors", "kala khatta", "strawberry lemonade",
    "coconut water", "ginger ale", "lemongrass basil", "apple cinnamon",
    "pineapple basil", "kimchi", "sauerkraut",
    "15 days", "1 month", "2 months", "3 months", "subscription",
    "regular price", "sale price", "\u20b9", "rupees", "cost", "pricing",
    "how to take", "when to take", "dosage instructions", "mix with water",
    "good bug", "the good bug", "your product", "this product", "your company",
    "buy", "purchase", "order", "shipping", "delivery", "refund", "return",
    "certification", "gmp", "fda", "peta", "iso", "haccp",
    "ingredients in", "contains", "formulation", "bacterial strains in",
    "probiotics", "prebiotics", "products", "product",
    "12 week guided program", "12-week guided program",
    "12 week guided", "12-week guided",
    "12 week program", "12-week program",
]

COMPANY_KEYWORDS = [
    "privacy policy", "terms", "cancellation", "tracking", "dispatch",
    "international shipping", "domestic shipping", "money back guarantee",
    "exchange", "quality assurance", "seven turns",
]

GENERAL_HEALTH_PATTERNS = [
    "meal plan", "diet plan", "nutrition plan", "eating plan",
    "weight loss", "weight gain", "fitness", "exercise", "workout",
    "health advice", "nutrition advice", "diet advice", "lifestyle advice",
    "general health", "overall health", "wellness", "healthy lifestyle",
    "ingredients", "my meals", "my meal", "for my meals", "for my meal",
    "grocery", "shopping list", "recipe", "recipes",
    "to order for", "what to buy", "what to order",
    "ingredients for", "ingredients to", "food items", "grocery list",
    "meal prep", "meal preparation", "cooking", "prepare",
    "make my meals", "cook my meals",
]

FOLLOW_UP_PATTERNS = [
    "how to take", "how to consume", "how to use",
    "when to take", "can i take", "can i mix", "can i use", "can i consume",
    "with other", "with drinks", "with food", "with milk", "with water",
    "side effects", "dosage", "timing",
    "take it", "use it", "consume it", "mix it",
    "how much", "how often", "is it safe", "best time",
    "empty stomach", "with meals", "before eating", "after eating",
    "how do i", "how should i", "when should i",
    "instructions", "direction", "how many",
    "benefits", "effect", "work", "does it", "is it", "can it",
    "price", "cost", "where", "buy", "purchase", "order",
    "precaustions", "precautions",
    "what about", "how about", "tell me about", "explain", "describe",
    "is this", "is that", "are these", "are those",
    "will it", "would it", "can i use", "should i use",
    "when can i", "how can i", "why should i",
    "how long", "how long should", "how long does", "how long to",
    "how long will", "when will", "when should",
    "how soon", "how quickly", "how fast",
    "time to", "wait to", "see results", "take effect", "start working",
]

# Order-tracking keywords — always route to product QnA
ORDER_TRACKING_KEYWORDS = [
    "track", "tracking",
    "where is my order", "where is my package",
    "order status", "order id",
    "delivery status", "delivery update",
    "shipped", "shipment",
    "dispatch", "dispatched",
    "in transit",
    "when will", "when will i receive", "when will it arrive",
    "not delivered", "out for delivery", "expected delivery",
    "return my order", "refund my order", "cancel my order",
    "exchange my order", "wrong order", "damaged order",
]

# Regex patterns for personal meal/diet/exercise references
PERSONAL_MEAL_PLAN_PATTERNS = [
    r"\bmy meal\b", r"\bmy meals\b", r"\bmy meal plan\b",
    r"\bmy diet\b", r"\bmy diet plan\b", r"\bmy food\b",
    r"\bmy breakfast\b", r"\bmy lunch\b", r"\bmy dinner\b",
    r"\bmy snack\b", r"\bmy snacks\b", r"\bmy eating\b",
    r"\bmy nutrition\b", r"\bmy nutrition plan\b",
    r"\bmy daily meal\b", r"\bmy daily meals\b",
    r"\bmy weekly meal\b", r"\bmy weekly meals\b",
    r"\bmy menu\b", r"\bmy food plan\b", r"\bmy eating plan\b",
    r"\bingredients.*for.*my meal", r"\bingredients.*for.*my diet",
    r"\bingredients.*to order.*for.*my", r"\bwhat to eat.*in.*my",
    r"\bmy exercise\b", r"\bmy exercise plan\b",
    r"\bmy workout\b", r"\bmy workout plan\b",
    r"\bmy fitness\b", r"\bmy fitness plan\b",
]

# Question/inquiry indicators used in is_product_question
QUESTION_INDICATORS = [
    "?", "how", "what", "should", "can", "why", "when", "is it", "could", "would",
    "do you", "give me", "any tips", "advice", "advise", "suggest", "help", "recommend",
    "tell me", "show me", "explain", "guide", "ways to",
    "need to know", "want to know", "looking for",
    "please", "pls", "plz", "share", "provide", "assist",
    "which", "does", "is there", "are there", "will",
    "difference between", "compare", "vs", "versus", "or", "better", "best",
    "where can i", "how do i", "where to", "when to",
    "price", "cost", "buy", "purchase", "order", "shipping", "delivery", "refund", "return",
]

# Statement patterns that suggest message is NOT a question
STATEMENT_PATTERNS = [
    " works well", " helped me", " is good", " is great", " is amazing",
    " is effective", " is useful", " is helpful",
    " helped", " worked", " like", " love", " prefer", " enjoy",
    " helps me", " helps", " works",
]

# Strong question indicators — override statement pattern exclusion
STRONG_QUESTION_INDICATORS = [
    "?", "how", "what", "should", "can", "why", "when", "tell me", "explain",
]

# Support contact fallback messages used in product QnA error/empty paths
QNA_FALLBACK_GENERAL = (
    "\U0001f49a I'd be happy to help with more specific product information! "
    "Please contact our support team at [nutritionist@seventurns.in](mailto:nutritionist@seventurns.in) "
    "or call/WhatsApp 8369744934 for detailed guidance."
)
QNA_FALLBACK_EXCEPTION = (
    "\U0001f49a I'd love to help with product information! "
    "Please contact our support team at [nutritionist@seventurns.in](mailto:nutritionist@seventurns.in) "
    "or call/WhatsApp 8369744934 for detailed product guidance."
)
QNA_FALLBACK_CONTEXTUAL = (
    "\U0001f49a For specific usage questions like this, I'd recommend contacting our support team at "
    "[nutritionist@seventurns.in](mailto:nutritionist@seventurns.in) or call/WhatsApp 8369744934. "
    "They can provide detailed guidance based on your individual needs!"
)

# Phrases that indicate the user is asking about their own product/order
MY_PRODUCT_QUERY_PHRASES = ["my product", "my products", "my order", "my purchase"]

# Profile keys used for debug logging in post_plan_qna_node
PROFILE_DEBUG_KEYS = [
    "age", "height", "weight", "bmi",
    "diet_preference", "cuisine_preference",
    "fitness_level", "activity_types",
    "meal_plan_sent", "exercise_plan_sent",
]

# QnA response category → emoji options dict (replaces if-elif chain)
CATEGORY_EMOJI_MAP = {
    "product":  ["\U0001f9a0", "\U0001f9ec", "\U0001f9ea", "\U0001f52c"],
    "shipping": ["\U0001f4e6", "\U0001f69a", "\U0001f6a2", "\u2708\ufe0f"],
    "refund":   ["\U0001f4b0", "\U0001f4b3", "\U0001f9fe", "\U0001f504"],
    "policy":   ["\U0001f4cb", "\U0001f4dc", "\U0001f4d6", "\u2696\ufe0f"],
}
CATEGORY_EMOJI_DEFAULT = ["\U0001f49a", "\u2764\ufe0f", "\U0001f499", "\U0001f49c"]
