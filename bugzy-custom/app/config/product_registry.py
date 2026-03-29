"""
Product Registry
Maps order string keywords to Bugzy product types.
"""
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BugzyProduct(Enum):
    """Supported Bugzy product types"""
    AMS = "ams"
    GUT_CLEANSE = "gut_cleanse"
    FREE_FORM = "free_form"  # QnA-only agent for users without AMS/Gut Cleanse purchase


# Product detection rules (priority order: check most specific first)
PRODUCT_KEYWORDS = [
    {
        "product": BugzyProduct.AMS,
        "keywords": [
            "12 week guided program",
            "12-week guided program",
            "12 week guided",
            "12-week guided",
            "12 week program",
            "12-week program",
            "metabolically lean",
            "weight management support",
            "active metabolic support",
            "supercharged",  # Metabolically Lean Supercharged
            "metabolic fiber boost",  # Metabolic Fiber Boost - associated with AMS
            "metabolic fiber",  # Metabolic Fiber Boost - associated with AMS
            "ams"
        ],
        "priority": 1
    },
    {
        "product": BugzyProduct.GUT_CLEANSE,
        "keywords": [
            "gut cleanse",
            "detox shots",
            "colon detox",
            "cleanse",
            "detox"
        ],
        "priority": 2
    },
    {
        "product": BugzyProduct.FREE_FORM,
        "keywords": [
            # Bye Bye Bloat
            "bye bye bloat",
            "bloat",
            # Gut Balance
            "gut balance",
            # Smooth Move
            "smooth move",
            "constipation",
            # IBS Rescue
            "ibs rescue",
            "ibs c",
            "ibs constipation",
            # IBS DnM
            "ibs dnm",
            "ibs d&m",
            "ibs d",
            "ibs m",
            "ibs diarrhea",
            "ibs mixed",
            # PCOS Balance
            "pcos balance",
            "pcos",
            "pcod",
            # First Defense
            "first defense",
            "first defence",
            "immunity",
            # Sleep and Calm
            "sleep and calm",
            "sleep",
            # Good Down There
            "good down there",
            "uti",
            "vaginal health",
            # Good to Glow
            "good to glow",
            "skin",
            "glow",
            # Happy Tummies
            "happy tummies",
            "kids",
            # Acidity Aid
            "acidity aid",
            "acidity",
            "heartburn",
            # Fiber products (non-AMS)
            "smooth move fiber boost",
            "smooth move fiber",
            "smooth fiber",
            "prebiotic fiber boost",
            "prebiotic fiber",
            "fiber boost",
            # Fermented drinks
            "water kefir",
            "kefir",
            "kombucha",
            # New Products
            "post meal digestive mints",
            "digestive mints",
            "digestive enzymes",
            "mints",
            "acv with garcinia cambogia",
            "acv",
            "apple cider vinegar",
            "garcinia",
            "gluta glow",
            "gluta",
            "glutathione"
        ],
        "priority": 3
    }
]


def detect_product_from_order(order_name: str) -> BugzyProduct:
    """
    Detect product type from order string.
    
    Args:
        order_name: Order string from CRM (e.g., "Metabolically lean | Weight Management...")
    
    Returns:
        BugzyProduct enum
    
    Examples:
        >>> detect_product_from_order("Metabolically lean | Weight Management Support")
        BugzyProduct.AMS
        
        >>> detect_product_from_order("Gut Cleanse - Probiotics + Fiber")
        BugzyProduct.GUT_CLEANSE
    """
    if not order_name or not str(order_name).strip():
        logger.info("No order string provided, using FREE_FORM")
        return BugzyProduct.FREE_FORM

    order_lower = order_name.lower().strip()

    # Check keywords in priority order
    for rule in sorted(PRODUCT_KEYWORDS, key=lambda x: x['priority']):
        keywords = rule['keywords']

        if not keywords:  # FREE_FORM / GENERAL have no keywords (default)
            continue

        if any(keyword in order_lower for keyword in keywords):
            logger.debug("Detected product: %s from order: %s...", rule['product'].value, order_name[:50] if order_name else "")
            return rule['product']

    logger.debug("Order has no matching product keywords, using FREE_FORM as default")
    return BugzyProduct.FREE_FORM


def get_agent_from_product_value(product_value: str) -> BugzyProduct:
    """
    Map stored product value (agent key or canonical name) to BugzyProduct for routing.
    - "ams" | "gut_cleanse" | "free_form" -> enum
    - Canonical names (e.g. "Bye Bye Bloat", "Water Kefir") -> FREE_FORM
    """
    if not product_value:
        return BugzyProduct.FREE_FORM
    p = (product_value or "").strip().lower()
    if p == "ams":
        return BugzyProduct.AMS
    if p == "gut_cleanse":
        return BugzyProduct.GUT_CLEANSE
    if p == "free_form":
        return BugzyProduct.FREE_FORM
    return BugzyProduct.FREE_FORM
