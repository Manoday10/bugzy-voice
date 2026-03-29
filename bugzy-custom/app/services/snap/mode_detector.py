"""
Analysis Mode Detection for SNAP Enhanced Features

This module detects the appropriate analysis mode based on user queries/captions.
Supports multiple analysis modes while maintaining backward compatibility.
"""

import re
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


def detect_analysis_mode(user_query: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    """
    Detect the appropriate analysis mode from user query.
    
    This function analyzes the user's caption or question to determine
    which type of analysis would be most appropriate.
    
    Args:
        user_query: User's caption or question (can be None or empty)
        
    Returns:
        Tuple of (mode, metadata)
        - mode: str - One of: AUTO, CAPTION_GUIDED, QUESTION_ANSWERING, 
                PORTION_CHECK, ALLERGEN_CHECK, COMPARISON, FREEFORM
        - metadata: dict - Extracted information about the query
        
    Examples:
        >>> detect_analysis_mode(None)
        ('AUTO', {})
        
        >>> detect_analysis_mode("How much protein?")
        ('QUESTION_ANSWERING', {'question': 'How much protein?'})
        
        >>> detect_analysis_mode("Healthy lunch")
        ('CAPTION_GUIDED', {'caption': 'Healthy lunch'})
        
        >>> detect_analysis_mode("I'm trying to eat healthier, is this a good choice?")
        ('FREEFORM', {'freeform_query': '...'})
    """
    # Handle None or empty queries
    if not user_query or not user_query.strip():
        return "AUTO", {}
    
    query_lower = user_query.lower().strip()
    word_count = len(user_query.split())
    
    # Question patterns (how much, what is, does it contain, etc.)
    question_patterns = [
        r'\bhow (much|many)\b',
        r'\bwhat(\'s| is)\b',
        r'\bdoes (this|it) contain\b',
        r'\bis (this|there)\b',
        r'\bcan (i|you)\b',
        r'\bshould i\b',
        r'\bwill (this|it)\b',
    ]
    
    # Portion patterns (too much, too little, enough, etc.)
    portion_patterns = [
        r'\btoo much\b',
        r'\btoo little\b',
        r'\btoo small\b',
        r'\btoo big\b',
        r'\btoo large\b',
        r'\benough\b',
        r'\bportion\b',
        r'\bserving\b',
        r'\bhow much should\b',
        r'\bappropriate (amount|portion|serving)\b',
    ]
    
    # Allergen patterns (contains nuts, dairy-free, etc.)
    allergen_patterns = [
        r'\b(contain|has|have) (any )?(nuts|dairy|gluten|soy|eggs|shellfish|fish|wheat|peanuts|tree nuts)\b',
        r'\b(nuts|dairy|gluten|soy|eggs|shellfish|fish|wheat|peanuts)(-| )free\b',
        r'\ballergen\b',
        r'\ballergic to\b',
        r'\bsafe for (nut|dairy|gluten|soy|egg|shellfish|fish|wheat) allerg\b',
    ]
    
    # Comparison patterns (which is better, healthier, etc.)
    comparison_patterns = [
        r'\b(which|what) (is )?(better|healthier|more|less)\b',
        r'\bcompare\b',
        r'\bvs\.?\b',
        r'\bversus\b',
        r'\bor\b.*\bor\b',  # "A or B" pattern
    ]
    
    # Check patterns in order of specificity (most specific first)
    
    # 1. Allergen check (highest priority for safety)
    for pattern in allergen_patterns:
        if re.search(pattern, query_lower):
            logger.info("🔍 Detected ALLERGEN_CHECK mode for query: %s", user_query)
            return "ALLERGEN_CHECK", {"allergen_query": user_query}
    
    # 2. Portion check
    for pattern in portion_patterns:
        if re.search(pattern, query_lower):
            logger.info("🔍 Detected PORTION_CHECK mode for query: %s", user_query)
            return "PORTION_CHECK", {"portion_query": user_query}
    
    # 3. Comparison
    for pattern in comparison_patterns:
        if re.search(pattern, query_lower):
            logger.info("🔍 Detected COMPARISON mode for query: %s", user_query)
            return "COMPARISON", {"comparison_query": user_query}
    
    # 4. Question answering (specific questions)
    for pattern in question_patterns:
        if re.search(pattern, query_lower):
            logger.info("🔍 Detected QUESTION_ANSWERING mode for query: %s", user_query)
            return "QUESTION_ANSWERING", {"question": user_query}
    
    # 5. Distinguish between CAPTION_GUIDED and FREEFORM
    # CAPTION_GUIDED: Short contextual labels (1-4 words)
    # FREEFORM: Longer conversational queries (5+ words)
    
    if word_count <= 4:
        # Short caption - likely a contextual label
        logger.info("🔍 Detected CAPTION_GUIDED mode for query: %s", user_query)
        return "CAPTION_GUIDED", {"caption": user_query}
    else:
        # Longer query - treat as freeform conversational input
        logger.info("🔍 Detected FREEFORM mode for query: %s", user_query)
        return "FREEFORM", {"freeform_query": user_query}


def get_mode_description(mode: str) -> str:
    """
    Get a human-readable description of an analysis mode.
    
    Args:
        mode: Analysis mode string
        
    Returns:
        Human-readable description
    """
    descriptions = {
        "AUTO": "Automatic full nutritional analysis",
        "CAPTION_GUIDED": "Context-aware analysis based on user's caption",
        "QUESTION_ANSWERING": "Focused answer to specific question",
        "PORTION_CHECK": "Portion size assessment",
        "ALLERGEN_CHECK": "Allergen detection and safety check",
        "COMPARISON": "Comparative analysis of multiple items",
        "FREEFORM": "Flexible analysis based on user's conversational input"
    }
    return descriptions.get(mode, "Unknown analysis mode")

