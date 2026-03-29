"""
CRM Sessions Module

This module handles all session management functionality including:
- MongoDB connection and initialization
- Loading and saving user sessions
- Session CRUD operations
- Product-specific data handling (AMS, Gut Cleanse)

Database Structure:
- user_info: Master user registry & Profile State (one doc per phone)
    - user_profile: Object containing Q&A answers, state variables, and counters
- conversation_history: Conversation History ONLY (one doc per user+product)
- meal_plans: Meal plan storage (one doc per user+product)
- exercise_plans: Exercise plan storage (one doc per user+product)
- snap_history: Food image analysis history (one doc per user+product)
"""

import os
import re
import pytz
import requests
from datetime import datetime
from typing import Optional, Literal
from pymongo import MongoClient, ASCENDING, DESCENDING
import logging

logger = logging.getLogger(__name__)

# --- Type Definitions ---
ProductType = Literal["ams", "gut_cleanse", "free_form"]

# --- CRM Config ---
CRM_BASE_URL = os.getenv("CRM_BASE_URL")
if not CRM_BASE_URL:
    logger.warning("CRM_BASE_URL is not set in environment variables!")

CRM_API_TOKEN = os.getenv("CRM_API_TOKEN")
CRM_HEADERS = {
    "Authorization": f"Bearer {CRM_API_TOKEN}",
    "Content-Type": "application/json"
}

# --- Session Persistence (MongoDB) ---
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB collections
_mongo_client: Optional[MongoClient] = None
_mongo_db = None
_users_collection = None           # user_info collection: Master user registry + Profile
_sessions_collection = None        # conversation_history collection: History ONLY
_meal_plans_collection = None
_exercise_plans_collection = None
_snap_history_collection = None

# Global in-memory session cache
SESSIONS = {}

# --- Product Detection Keywords ---
AMS_KEYWORDS = [
    "metabolically lean",
    "weight management support",
    "active metabolic support",
    "ams"
]

GUT_CLEANSE_KEYWORDS = [
    "gut cleanse",
    "detox shots",
    "colon detox"
]


def detect_product_from_order(order_name: str) -> ProductType:
    """
    Detect product type from order name string.

    Args:
        order_name: The order name from CRM

    Returns:
        "ams" or "gut_cleanse"
    """
    if not order_name:
        return "ams"  # Default to AMS

    order_lower = order_name.lower()

    # Check for AMS keywords first (to handle overlap like "Probiotics" in name)
    for keyword in AMS_KEYWORDS:
        if keyword in order_lower:
            return "ams"

    # Check for Gut Cleanse keywords
    for keyword in GUT_CLEANSE_KEYWORDS:
        if keyword in order_lower:
            return "gut_cleanse"

    # Default to AMS
    return "ams"


def _init_mongo_if_needed():
    """Initialize MongoDB connection and collections if not already done."""
    global _mongo_client, _mongo_db
    global _users_collection, _sessions_collection
    global _meal_plans_collection, _exercise_plans_collection, _snap_history_collection

    if _mongo_client is not None:
        return

    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")

    # Configure connection pooling with robust network settings
    _mongo_client = MongoClient(
        mongo_uri,
        maxPoolSize=500,
        minPoolSize=10,
        maxIdleTimeMS=30000,
        waitQueueTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
        serverSelectionTimeoutMS=10000,
        retryWrites=True
    )

    _mongo_db = _mongo_client["bugzy_ams"]

    # Initialize collections
    _users_collection = _mongo_db["user_info"]
    _sessions_collection = _mongo_db["conversation_history"]
    _meal_plans_collection = _mongo_db["meal_plans"]
    _exercise_plans_collection = _mongo_db["exercise_plans"]
    _snap_history_collection = _mongo_db["snap_history"]

    # Create optimized indexes
    _create_indexes()

    logger.info("MongoDB initialization complete.")


def _create_indexes():
    """Create optimized indexes for all collections."""
    logger.info("Ensuring MongoDB Indexes...")

    # ===== USERS COLLECTION (Master Registry + Profile) =====
    _users_collection.create_index("user_id", unique=True)
    _users_collection.create_index("phone_number")
    _users_collection.create_index([("active_product", ASCENDING), ("last_active", DESCENDING)])
    logger.info("   Indexes created for user_info collection")

    # ===== SESSIONS COLLECTION (History Only) =====
    _sessions_collection.create_index(
        [("user_id", ASCENDING), ("product", ASCENDING)],
        unique=True
    )
    _sessions_collection.create_index([("product", ASCENDING), ("last_updated", DESCENDING)])
    # Removed indexes on last_question/current_agent as they are moved to user_info
    logger.info("   Indexes created for conversation_history collection")

    # ===== MEAL PLANS COLLECTION =====
    _meal_plans_collection.create_index(
        [("user_id", ASCENDING), ("product", ASCENDING)],
        unique=True
    )
    _meal_plans_collection.create_index([("product", ASCENDING), ("status", ASCENDING)])
    _meal_plans_collection.create_index([("last_updated", DESCENDING)])
    logger.info("   Indexes created for meal_plans collection")

    # ===== EXERCISE PLANS COLLECTION =====
    _exercise_plans_collection.create_index(
        [("user_id", ASCENDING), ("product", ASCENDING)],
        unique=True
    )
    _exercise_plans_collection.create_index([("product", ASCENDING), ("status", ASCENDING)])
    _exercise_plans_collection.create_index([("last_updated", DESCENDING)])
    logger.info("   Indexes created for exercise_plans collection")

    # ===== SNAP HISTORY COLLECTION =====
    _snap_history_collection.create_index(
        [("user_id", ASCENDING), ("product", ASCENDING)],
        unique=True
    )
    _snap_history_collection.create_index([("product", ASCENDING), ("last_snap_at", DESCENDING)])
    _snap_history_collection.create_index([("last_snap_at", DESCENDING)])
    logger.info("   Indexes created for snap_history collection")


# ==========================================================
# USERS COLLECTION (Master Registry)
# ==========================================================
def get_or_create_user(user_id: str, phone_number: str = None, user_name: str = None) -> dict:
    """
    Get or create a user in the master registry.

    Args:
        user_id: WhatsApp user ID (e.g., "whatsapp:+919876543210")
        phone_number: Optional phone number
        user_name: Optional user name

    Returns:
        User document
    """
    try:
        _init_mongo_if_needed()
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist).isoformat()

        # Try to find existing user
        user = _users_collection.find_one({"user_id": user_id}, {"_id": 0})

        if user:
            # Update last_active
            _users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"last_active": now}}
            )
            return user

        # Create new user
        new_user = {
            "user_id": user_id,
            "product": None, # Agent key
            "phone_number": phone_number,
            "user_name": user_name,
            "products_accessed": [],
            "active_product": None,
            "crm_user_data": None,
            # "crm_cached_at": None, # Removed as per new schema
            "created_at": now,
            "last_active": now,
            "user_profile": {}  # New field for profile data
        }

        _users_collection.insert_one(new_user)
        logger.debug("Created new user: %s", user_id)

        return new_user

    except Exception as e:
        logger.error("Error in get_or_create_user: %s", e)
        return {}


def _get_canonical_product_names_for_order(order_str: Optional[str]) -> list[str]:
    """
    Return canonical main product names from order string (for products_accessed).
    Uses product_validator aliases so only known main products are stored.
    """
    if not order_str or not isinstance(order_str, str):
        return []
    from app.services.rag.product_validator import get_canonical_product_names_from_order
    return get_canonical_product_names_from_order(order_str)


def update_user_product(user_id: str, product: ProductType, order_name: Optional[str] = None):
    """
    Update user's active product and add to products_accessed list.

    - active_product: stores agent key (ams, gut_cleanse, free_form) for routing.
    - products_accessed: stores actual product names from order (e.g. "Bye Bye Bloat", "Bugsy"),
      not agent keys.

    Args:
        user_id: WhatsApp user ID
        product: Product/agent type ("ams", "gut_cleanse", "free_form")
        order_name: Optional CRM order string; when provided, parsed product names are
                    added to products_accessed instead of the agent key.
    """
    try:
        _init_mongo_if_needed()
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist).isoformat()

        update_doc = {
            "$set": {
                "active_product": product,
                "product": product,  # Sync active_product to product for schema consistency
                "last_active": now,
            },
        }
        # products_accessed stores display names only (e.g. "Metabolically Lean AMS", "Gut Cleanse"), never agent keys ("ams", "gut_cleanse")
        _DISPLAY_NAME_BY_PRODUCT = {"ams": "Metabolically Lean AMS", "gut_cleanse": "Gut Cleanse"}
        if order_name:
            product_names = _get_canonical_product_names_for_order(order_name)
            if product_names:
                update_doc["$addToSet"] = {"products_accessed": {"$each": product_names}}
            else:
                display = _DISPLAY_NAME_BY_PRODUCT.get(product)
                if display:
                    update_doc["$addToSet"] = {"products_accessed": display}
                else:
                    update_doc["$addToSet"] = {"products_accessed": product}
        else:
            display = _DISPLAY_NAME_BY_PRODUCT.get(product)
            if display:
                update_doc["$addToSet"] = {"products_accessed": display}
            else:
                update_doc["$addToSet"] = {"products_accessed": product}

        _users_collection.update_one(
            {"user_id": user_id},
            update_doc,
            upsert=True,
        )

        logger.debug("Updated user %s active_product=%s products_accessed+=%s", user_id, product, order_name or product)

    except Exception as e:
        logger.error("Error updating user product: %s", e)


def cache_crm_data(user_id: str, crm_data: dict):
    """Cache CRM data for a user to avoid repeated API calls."""
    try:
        _init_mongo_if_needed()
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist).isoformat()

        _users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "crm_user_data": crm_data
            }}
        )

    except Exception as e:
        logger.error("Error caching CRM data: %s", e)


# ==========================================================
# CONVERSATION_HISTORY COLLECTION (History Only) + USER INFO (State)
# ==========================================================
def save_session(user_id: str, product: ProductType, session_data: dict):
    """
    Save or update a user session.
    
    Refactored Logic:
    1. Splits `session_data` into:
       - History (`conversation_history`) -> `conversation_history` collection
       - State (`last_question`, `current_agent`, Q&A answers, etc.) -> `user_info.user_profile`
    
    2. Increments counters in `user_profile` if detected in updates.
    """
    try:
        _init_mongo_if_needed()

        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist).isoformat()

        # 1. Extract History for conversation_history collection
        # "full_chat_history" -> complete history (if present in session_data, move to conversation_history)
        # "conversation_history" -> short-term memory (last 20)
        
        sessions_update = {
            "user_id": user_id,
            "product": product,
            "last_updated": now,
            "resume_intervals_sent": {}  # Reset reminder intervals when user responds (last_updated changes)
        }

        if "conversation_history" in session_data:
            conv_hist = session_data["conversation_history"]
            if isinstance(conv_hist, list):
                sessions_update["conversation_history"] = conv_hist[-20:]
        
        if "full_chat_history" in session_data:
             sessions_update["full_chat_history"] = session_data["full_chat_history"]

        # 2. Extract State for User Info Collection
        user_profile_update = {}
        
        # Keys to EXCLUDE from user_profile (bulk content, history, or system meta)
        exclude_keys = {
            "conversation_history", "full_chat_history", "user_id", "product", 
            "last_resume_template_sent_for", "resume_intervals_sent", "created_at",
            # Exclude Bulk Plan Content (stored in dedicated collections)
            "meal_plan", "exercise_plan", "snap_analysis_result",
            # Exclude Day-wise plans if they are just the strings (we keep them in meal/exercise_plans)
            # We use regex below to catch meal_dayX_plan / dayX_plan
        }
        
        # Regex patterns to exclude
        exclude_patterns = [
            r"meal_day\d+_plan", 
            r"day\d+_plan", 
            r"snap_analysis_result",
            # Exclude change requests and old plans (temporary state for loops)
            r"meal_day\d+_change_request",
            r"day\d+_change_request",
            r"old_meal_day\d+_plans",
            r"old_day\d+_plans",
            r"user_context"
        ]

        for key, value in session_data.items():
            if key in exclude_keys:
                continue
            
            # Check patterns
            # Note: "meal_day1_change_request" is OK to keep in profile as it's state for the loop
            skip = False
            for pattern in exclude_patterns:
                if re.match(pattern, key):
                    skip = True
                    break
            if skip:
                continue
                
            if isinstance(value, (str, int, float, bool, dict, list)) or value is None:
                 user_profile_update[f"user_profile.{key}"] = value

        # Prepare User Info Update
        ui_update_query = {
            "$set": {
                **user_profile_update,
                "last_active": now
            }
        }
        
        # Execute updates
        
        # A. Update Sessions (History)
        # Clean up orphan free_form sessions logic preserved
        if product in ("ams", "gut_cleanse"):
            _sessions_collection.delete_one({"user_id": user_id, "product": "free_form"})
        elif product not in ("free_form",):
            _sessions_collection.delete_one({"user_id": user_id, "product": "free_form"})

        _sessions_collection.update_one(
            {"user_id": user_id, "product": product},
            {
                "$set": sessions_update,
                "$setOnInsert": {"created_at": now}
            },
            upsert=True
        )

        # B. Update User Info (Profile State)
        _users_collection.update_one(
            {"user_id": user_id},
            ui_update_query,
            upsert=True
        )

        # Update user's active product
        order_name = session_data.get("user_order") if isinstance(session_data.get("user_order"), str) else None
        update_user_product(user_id, product, order_name=order_name)

        logger.debug("Session saved for user %s (product: %s) [Split: History->Sessions, State->UserInfo]",
                     user_id, product)

    except Exception as e:
        logger.error("Error saving session: %s", e)


def load_session(user_id: str, product: ProductType) -> dict:
    """
    Load a user's session.
    
    Refactored Logic:
    1. Fetches `user_profile` from `user_info`.
    2. Fetches `conversation_history` from `conversation_history`.
    3. Merges them into a single State dictionary.
    """
    try:
        _init_mongo_if_needed()

        # 1. Fetch User Profile
        user_doc = _users_collection.find_one({"user_id": user_id}, {"user_profile": 1, "_id": 0})
        user_profile = user_doc.get("user_profile", {}) if user_doc else {}

        # 2. Fetch History
        session_doc = _sessions_collection.find_one(
            {"user_id": user_id, "product": product},
            {"conversation_history": 1, "full_chat_history": 1, "_id": 0}
        )
        history = session_doc.get("conversation_history", []) if session_doc else []
        full_history = session_doc.get("full_chat_history", []) if session_doc else []

        # 3. Merge
        # Start with profile data
        session_data = user_profile.copy()
        
        # Add history and context keys
        session_data["conversation_history"] = history
        if full_history:
            session_data["full_chat_history"] = full_history
            
        session_data["user_id"] = user_id
        session_data["product"] = product

        logger.debug("Loaded split session for %s (product: %s)", user_id, product)
        return session_data

    except Exception as e:
        logger.error("Error loading session: %s", e)
        return {}


def delete_session(user_id: str, product: ProductType):
    """Delete a user's session for a specific product."""
    try:
        _init_mongo_if_needed()
        _sessions_collection.delete_one({"user_id": user_id, "product": product})
        logger.info("Deleted session for user %s (product: %s)", user_id, product)
    except Exception as e:
        logger.error("Error deleting session: %s", e)


# ==========================================================
# BACKWARD COMPATIBILITY ALIASES
# ==========================================================
def save_session_to_file(user_id: str, session_data: dict):
    """
    Legacy function for backward compatibility.
    Uses session_data.product if set. Else detects agent from user_order.
    
    CRITICAL: If product cannot be determined and user has no order, 
    this function will skip the save to prevent creating orphan free_form sessions.
    
    MIGRATED USERS: If user already has a free_form session in DB, preserve it
    (don't auto-switch to ams/gut_cleanse based on order).
    """
    product = session_data.get("product")
    
    # If product is already set (and not free_form), use it directly
    if product and product != "free_form":
        save_session(user_id, product, session_data)
        return
    
    # CRITICAL: Check if user already has a free_form session (migrated users)
    # This MUST come BEFORE order detection to preserve free_form status
    _init_mongo_if_needed()
    existing_free_form = _sessions_collection.find_one(
        {"user_id": user_id, "product": "free_form"},
        {"product": 1}
    )
    if existing_free_form:
        # User is on free_form flow (likely migrated from completed journey)
        # Preserve free_form even if order suggests ams/gut_cleanse
        logger.info(
            "👤 Preserving free_form for user %s (migrated user, not switching based on order)",
            user_id
        )
        save_session(user_id, "free_form", session_data)
        return
    
    # Try to detect product from order (only for NEW users without existing session)
    order_name = session_data.get("user_order") or ""
    if order_name and isinstance(order_name, str) and order_name.strip():
        from app.config.product_registry import detect_product_from_order as detect_from_registry, BugzyProduct
        product_agent = detect_from_registry(order_name)
        if product_agent == BugzyProduct.FREE_FORM:
            # For genuine free_form products, store canonical product name
            from app.services.rag.product_validator import get_canonical_product_names_from_order
            names = get_canonical_product_names_from_order(order_name)
            product = names[0] if names else "free_form"
        else:
            product = product_agent.value
        save_session(user_id, product, session_data)
        return
    
    # No product and no order - check if this is a deliberate free_form save
    if product == "free_form":
        # Only save free_form if explicitly set (not by default)
        save_session(user_id, product, session_data)
        return
    
    # Before skipping, check if user already has a session with product in MongoDB
    # This handles the case where stale session_data is passed without product/order
    existing = _sessions_collection.find_one(
        {"user_id": user_id, "product": {"$in": ["ams", "gut_cleanse"]}},
        {"product": 1}
    )
    if existing and existing.get("product"):
        # User already has a proper session, save to that product
        product = existing["product"]
        save_session(user_id, product, session_data)
        return
    
    # CRITICAL: No product, no order, no existing session - skip save
    # The session will be properly saved later once product is detected from CRM
    logger.debug(
        "Skipping session save for user %s - no product set and no order data.",
        user_id
    )
    # Don't save - return without calling save_session


def load_user_session(user_id: str, product: ProductType = None) -> dict:
    """
    Legacy function for backward compatibility.
    If product is not specified, tries to detect from user_info collection.
    """
    try:
        _init_mongo_if_needed()

        if product:
            return load_session(user_id, product)

        # Try to get active product from user_info collection
        user = _users_collection.find_one({"user_id": user_id}, {"active_product": 1})
        if user and user.get("active_product"):
            return load_session(user_id, user["active_product"])

        # Fallback: Check if any session actually exists in DB
        # We must check existence first, otherwise load_session returns a constructed object
        # which causes orchestrator to skip CRM order detection
        
        existing_ams = _sessions_collection.find_one({"user_id": user_id, "product": "ams"}, {"_id": 1})
        if existing_ams:
            return load_session(user_id, "ams")
            
        existing_gc = _sessions_collection.find_one({"user_id": user_id, "product": "gut_cleanse"}, {"_id": 1})
        if existing_gc:
            return load_session(user_id, "gut_cleanse")
            
        existing_free = _sessions_collection.find_one({"user_id": user_id, "product": "free_form"}, {"_id": 1})
        if existing_free:
            return load_session(user_id, "free_form")

        # No session exists for any product -> Return None
        # This allows Orchestrator to proceed to Step 2 (Fetch CRM Order)
        return None

    except Exception as e:
        logger.error("Error in load_user_session: %s", e)
        return {}


def get_user_session_by_phone(phone_number: str) -> Optional[dict]:
    """
    Look up a user session by phone number.
    
    Searches for the user in MongoDB's user_info collection by phone_number,
    then loads their session. Also checks the in-memory SESSIONS cache
    (keyed by phone number from app chat flow).
    
    Args:
        phone_number: The user's phone number (with or without country code)
        
    Returns:
        Session dict with full_chat_history, or None if not found
    """
    try:
        if phone_number in SESSIONS:
            return SESSIONS[phone_number]
        
        _init_mongo_if_needed()
        
        user = _users_collection.find_one(
            {"phone_number": phone_number},
            {"user_id": 1, "user_name": 1, "_id": 0}
        )
        
        if not user:
            if not phone_number.startswith("+"):
                user = _users_collection.find_one(
                    {"phone_number": f"+91{phone_number}"},
                    {"user_id": 1, "user_name": 1, "_id": 0}
                )
            if not user and phone_number.startswith("+"):
                stripped = phone_number.lstrip("+")
                if stripped.startswith("91") and len(stripped) > 10:
                    stripped = stripped[2:]
                user = _users_collection.find_one(
                    {"phone_number": stripped},
                    {"user_id": 1, "user_name": 1, "_id": 0}
                )
        
        if not user:
            user = _users_collection.find_one(
                {"user_id": phone_number},
                {"user_id": 1, "user_name": 1, "_id": 0}
            )
        
        if not user:
            logger.debug("No user found for phone number: %s", phone_number)
            return None
        
        user_id = user.get("user_id")
        if not user_id:
            return None
        
        session = load_user_session(user_id)
        
        if session:
            session["user_name"] = user.get("user_name")
            session["phone_number"] = phone_number
            
        return session
        
    except Exception as e:
        logger.error("Error in get_user_session_by_phone: %s", e)
        return None


def delete_user_session(user_id: str, product: ProductType = None):
    """Legacy function for backward compatibility."""
    if product:
        delete_session(user_id, product)
    else:
        # Delete session for user's active_product (may be canonical name e.g. "Bye Bye Bloat")
        try:
            _init_mongo_if_needed()
            user = _users_collection.find_one({"user_id": user_id}, {"active_product": 1})
            if user and user.get("active_product"):
                delete_session(user_id, user["active_product"])
        except Exception:
            pass
        delete_session(user_id, "ams")
        delete_session(user_id, "gut_cleanse")
        delete_session(user_id, "free_form")


def get_all_active_users(product: ProductType = None):
    """
    Yields all user sessions from MongoDB one by one.

    Args:
        product: Optional filter by product type
    """
    try:
        _init_mongo_if_needed()

        query = {}
        if product:
            query["product"] = product

        cursor = _users_collection.find(query, {"user_id": 1, "active_product": 1})
        
        users_list = list(cursor)

        count = 0
        for doc in users_list:
            user_id = doc.get("user_id")
            active_prod = doc.get("active_product")
            if not user_id:
                continue
                
            # Load full session using the helper
            if active_prod:
                yield load_session(user_id, active_prod)
            else:
                 # Fallback if no active product set
                 yield load_session(user_id, "ams")
            count += 1

        logger.info("Streamed %d sessions from MongoDB", count)

    except Exception as e:
        logger.error("Error streaming users: %s", e)
        return


# ==========================================================
# MEAL PLAN STORAGE
# ==========================================================
def save_meal_plan(user_id: str, meal_plan_data: dict, product: ProductType = None, increment_change_count: bool = False):
    """
    Save or update a user's meal plan.

    Args:
        user_id: WhatsApp user ID
        meal_plan_data: Meal plan data including survey and days
        product: Product type (auto-detected if not provided)
        increment_change_count: Whether to increment the change counter (default: False)
    """
    try:
        _init_mongo_if_needed()

        # Auto-detect product if not provided
        if not product:
            product = detect_product_from_order(meal_plan_data.get("user_order", ""))

        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist).isoformat()

        # Ensure consistent field ordering
        ordered_data = {
            "user_id": user_id,
            "product": product,
            "last_updated": now
        }
        
        # Add user_context if present (should be near top)
        if "user_context" in meal_plan_data:
            ordered_data["user_context"] = meal_plan_data.pop("user_context")
            
        # Add remaining fields
        ordered_data.update(meal_plan_data)

        # Set created_at only on insert
        _meal_plans_collection.update_one(
            {"user_id": user_id, "product": product},
            {
                "$set": ordered_data,
                "$setOnInsert": {"created_at": now}
            },
            upsert=True
        )
        
        # Increment change counter in user_profile ONLY if requested
        if increment_change_count:
            _users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"user_profile.meal_plan_changes_count": 1}}
            )

        logger.debug("Meal plan saved for user %s (product: %s, increment_count: %s)", 
                     user_id, product, increment_change_count)

    except Exception as e:
        logger.error("Error saving meal plan: %s", e)


def load_meal_plan(user_id: str, product: ProductType = None) -> dict:
    """
    Load a user's meal plan.

    Args:
        user_id: WhatsApp user ID
        product: Product type (uses active product if not provided)
    """
    try:
        _init_mongo_if_needed()

        if not product:
            # Get active product from user_info collection
            user = _users_collection.find_one({"user_id": user_id}, {"active_product": 1})
            product = user.get("active_product", "ams") if user else "ams"

        doc = _meal_plans_collection.find_one(
            {"user_id": user_id, "product": product},
            {"_id": 0}
        )

        if not doc:
            return {}

        logger.debug("Loaded meal plan for %s (product: %s)", user_id, product)
        return dict(doc)

    except Exception as e:
        logger.error("Error loading meal plan: %s", e)
        return {}


# ==========================================================
# EXERCISE PLAN STORAGE
# ==========================================================
def save_exercise_plan(user_id: str, exercise_plan_data: dict, product: ProductType = None, increment_change_count: bool = False):
    """
    Save or update a user's exercise plan.

    Args:
        user_id: WhatsApp user ID
        exercise_plan_data: Exercise plan data including survey and days
        product: Product type (auto-detected if not provided)
        increment_change_count: Whether to increment the change counter (default: False)
    """
    try:
        _init_mongo_if_needed()

        if not product:
            product = detect_product_from_order(exercise_plan_data.get("user_order", ""))

        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist).isoformat()

        # Ensure consistent field ordering
        ordered_data = {
            "user_id": user_id,
            "product": product,
            "last_updated": now
        }
        
        # Add user_context if present (should be near top)
        if "user_context" in exercise_plan_data:
            ordered_data["user_context"] = exercise_plan_data.pop("user_context")
            
        # Add remaining fields
        ordered_data.update(exercise_plan_data)

        _exercise_plans_collection.update_one(
            {"user_id": user_id, "product": product},
            {
                "$set": ordered_data,
                "$setOnInsert": {"created_at": now}
            },
            upsert=True
        )
        
        # Increment change counter in user_profile ONLY if requested
        if increment_change_count:
            _users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"user_profile.exercise_plan_changes_count": 1}}
            )

        logger.debug("Exercise plan saved for user %s (product: %s, increment_count: %s)", 
                     user_id, product, increment_change_count)

    except Exception as e:
        logger.error("Error saving exercise plan: %s", e)


def load_exercise_plan(user_id: str, product: ProductType = None) -> dict:
    """Load a user's exercise plan."""
    try:
        _init_mongo_if_needed()

        if not product:
            user = _users_collection.find_one({"user_id": user_id}, {"active_product": 1})
            product = user.get("active_product", "ams") if user else "ams"

        doc = _exercise_plans_collection.find_one(
            {"user_id": user_id, "product": product},
            {"_id": 0}
        )

        if not doc:
            return {}

        logger.debug("Loaded exercise plan for %s (product: %s)", user_id, product)
        return dict(doc)

    except Exception as e:
        logger.error("Error loading exercise plan: %s", e)
        return {}


# ==========================================================
# SNAP HISTORY STORAGE
# ==========================================================
def save_snap_analysis(user_id: str, snap_data: dict, product: ProductType = None):
    """
    Save a snap analysis to the snap_history collection.
    Uses $slice to cap at 50 snaps per user per product.

    Args:
        user_id: WhatsApp user ID
        snap_data: Snap analysis data
        product: Product type
    """
    try:
        _init_mongo_if_needed()

        if not product:
            # Get active product
            user = _users_collection.find_one({"user_id": user_id}, {"active_product": 1})
            product = user.get("active_product", "ams") if user else "ams"

        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist).isoformat()

        # Add timestamp to snap (Renamed from ts)
        snap_data["timestamp"] = now

        # Upsert with capped array (max 50 snaps)
        # Ensure consistent field ordering for the set operation
        update_set_fields = {
            "user_id": user_id,
            "product": product,
            "last_snap_at": now
        }

        _snap_history_collection.update_one(
            {"user_id": user_id, "product": product},
            {
                "$push": {
                    "snaps": {
                        "$each": [snap_data],
                        "$slice": -50  # Keep only last 50 snaps
                    }
                },
                "$set": update_set_fields,
                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )
        
        # Increment snap_count in user_profile
        _users_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"user_profile.snap_count": 1}}
        )

        logger.debug("Snap analysis saved for user %s (product: %s)", user_id, product)

    except Exception as e:
        logger.error("Error saving snap analysis: %s", e)


def load_snap_history(user_id: str, limit: int = 10, product: ProductType = None) -> list:
    """Load recent snap analyses for a user."""
    try:
        _init_mongo_if_needed()

        if not product:
            user = _users_collection.find_one({"user_id": user_id}, {"active_product": 1})
            product = user.get("active_product", "ams") if user else "ams"

        doc = _snap_history_collection.find_one(
            {"user_id": user_id, "product": product},
            {"_id": 0, "snaps": 1}
        )

        if not doc or "snaps" not in doc:
            return []

        snaps = doc.get("snaps", [])

        # Sort by timestamp descending (newest first)
        # Note: 'timestamp' replaces 'ts'
        snaps.sort(key=lambda x: x.get("timestamp", x.get("ts", "")), reverse=True)

        result = snaps[:limit]

        if result:
            logger.debug("Loaded %d snap(s) for %s", len(result), user_id)

        return result

    except Exception as e:
        logger.error("Error loading snap history: %s", e)
        return []


def get_snap_count(user_id: str, product: ProductType = None) -> int:
    """Get total number of snaps for a user from user_profile."""
    try:
        _init_mongo_if_needed()
        
        user_doc = _users_collection.find_one(
            {"user_id": user_id}, 
            {"user_profile.snap_count": 1, "_id": 0}
        )
        
        if user_doc and "user_profile" in user_doc:
            return user_doc["user_profile"].get("snap_count", 0)
            
        return 0

        if not product:
            user = _users_collection.find_one({"user_id": user_id}, {"active_product": 1})
            product = user.get("active_product", "ams") if user else "ams"

        doc = _snap_history_collection.find_one(
            {"user_id": user_id, "product": product},
            {"_id": 0, "snap_count": 1}
        )

        if not doc:
            return 0

        return doc.get("snap_count", 0)

    except Exception as e:
        logger.error("Error counting snaps: %s", e)
        return 0


# ==========================================================
# USER CONTEXT EXTRACTION HELPERS
# ==========================================================
def extract_ams_meal_user_context(state: dict) -> dict:
    """Extract AMS-specific user context for meal plan storage."""
    return {
        "age": state.get("age"),
        "weight_kg": state.get("weight"),
        "height_cm": state.get("height"),
        "bmi": state.get("bmi"),
        "health_conditions_overview": state.get("health_conditions_overview"),
    }


def extract_gut_cleanse_meal_user_context(state: dict) -> dict:
    """Extract Gut Cleanse-specific user context for meal plan storage."""
    return {
        "age_eligible": state.get("age_eligible"),
        "gender": state.get("gender"),
        "is_pregnant": state.get("is_pregnant"),
        "is_breastfeeding": state.get("is_breastfeeding"),
        "health_safety_status": state.get("health_safety_status"),
        "specific_health_condition": state.get("specific_health_condition"),
        "detox_experience": state.get("detox_experience"),
    }


def extract_ams_meal_survey(state: dict) -> dict:
    """Extract AMS-specific meal survey data."""
    return {
        "diet_preference": state.get("diet_preference"),
        "cuisine_preference": state.get("cuisine_preference"),
        "current_dishes": state.get("current_dishes"),
        "allergies": state.get("allergies"),
        "water_intake": state.get("water_intake"),
        "beverages": state.get("beverages"),
        "supplements": state.get("supplements"),
        "gut_health": state.get("gut_health"),
        "meal_goals": state.get("meal_goals"),
    }


def extract_gut_cleanse_meal_survey(state: dict) -> dict:
    """Extract Gut Cleanse-specific meal survey data."""
    return {
        "dietary_preference": state.get("dietary_preference"),
        "food_allergies_intolerances": state.get("food_allergies_intolerances"),
        "daily_eating_pattern": state.get("daily_eating_pattern"),
        "foods_avoid": state.get("foods_avoid"),
        "digestive_issues": state.get("digestive_issues"),
        "hydration": state.get("hydration"),
        "other_beverages": state.get("other_beverages"),
        "daily_eating_pattern": state.get("daily_eating_pattern"),
        "foods_avoid": state.get("foods_avoid"),
        "digestive_issues": state.get("digestive_issues"),
        "hydration": state.get("hydration"),
        "other_beverages": state.get("other_beverages"),
        "gut_sensitivity": state.get("gut_sensitivity"),
    }


def extract_exercise_plan_user_context(state: dict) -> dict:
    """Extract relevant user context for exercise plan storage."""
    return {
        "age": state.get("age"),
        "weight_kg": state.get("weight"),
        "height_cm": state.get("height"),
        "bmi": state.get("bmi"),
        "fitness_level": state.get("fitness_level"),
    }


def extract_ams_exercise_survey(state: dict) -> dict:
    """Extract AMS-specific exercise survey data (FITT framework)."""
    return {
        "fitness_level": state.get("fitness_level"),
        "activity_types": state.get("activity_types"),
        "exercise_frequency": state.get("exercise_frequency"),
        "exercise_intensity": state.get("exercise_intensity"),
        "session_duration": state.get("session_duration"),
        "sedentary_time": state.get("sedentary_time"),
        "exercise_goals": state.get("exercise_goals"),
    }


def extract_gut_cleanse_exercise_survey(state: dict) -> dict:
    """Extract Gut Cleanse-specific exercise survey data."""
    return {
        "workout_posture_gut": state.get("workout_posture_gut"),
        "workout_hydration_gut": state.get("workout_hydration_gut"),
        "workout_gut_mobility_gut": state.get("workout_gut_mobility_gut"),
        "workout_relaxation_gut": state.get("workout_relaxation_gut"),
        "workout_gut_awareness_gut": state.get("workout_gut_awareness_gut"),
    }


# ==========================================================
# CRM API FUNCTIONS
# ==========================================================
def fetch_user_details(phone_number: str) -> dict:
    """Fetch user details from CRM by phone number."""
    if not phone_number:
        return {"error": "Please provide phone_number"}
    try:
        url = f"{CRM_BASE_URL}/customer/search"
        payload = {"searchParameter": phone_number}
        response = requests.post(url, headers=CRM_HEADERS, json=payload, timeout=15)
        response.raise_for_status()
        user_data = response.json()
        if isinstance(user_data, list) and len(user_data) > 0:
            first = user_data[0] or {}
            return {
                "phone_number": phone_number,
                "name": (
                    first.get("name", "Name not available").split()[0].capitalize()
                    if first.get("name") and first.get("name").strip()
                    else "Name not available"
                ),
                "full_data": user_data
            }
        return {"message": f"User with phone number {phone_number} not found"}
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def fetch_order_details(phone_number: str) -> dict:
    """
    Fetch order details for a given phone number by directly calling CRM API.
    """
    if not phone_number:
        return {"error": "Please provide phone_number"}

    try:
        search_url = f"{CRM_BASE_URL}/customer/search"
        payload = {"searchParameter": phone_number}

        search_response = requests.post(search_url, headers=CRM_HEADERS, json=payload, timeout=15)
        search_response.raise_for_status()
        user_data_list = search_response.json()

        if not user_data_list or len(user_data_list) == 0:
            return {"error": f"User with phone number {phone_number} not found"}

        user_data = user_data_list[0]
        user_id = user_data.get("_id")
        if not user_id:
            return {"error": "User ID not found in CRM response"}

        orders_url = f"{CRM_BASE_URL}/customer/{user_id}/orders"
        orders_response = requests.get(orders_url, headers=CRM_HEADERS, timeout=15)
        orders_response.raise_for_status()
        orders_data = orders_response.json()

        return {
            "phone_number": phone_number,
            "user_id": user_id,
            "user_name": user_data.get("name", "Name not available"),
            "orders": orders_data
        }
    except requests.exceptions.RequestException as e:
        logger.error("CRM API Error (fetch_order_details): %s", e)
        return {"error": f"API request failed: {str(e)}"}
    except Exception as e:
        logger.error("Unexpected Error (fetch_order_details): %s", e)
        return {"error": str(e)}


def extract_order_details(api_response: dict) -> dict:
    """Extract only the latest order information from the API response."""
    from app.services.whatsapp.parser import parse_date

    orders_data = api_response.get("orders", {})

    if not orders_data or not isinstance(orders_data, dict):
        return {
            "latest_order_name": None,
            "latest_order_date": None,
            "has_orders": False
        }

    order_list = orders_data.get("order", [])
    total_orders = orders_data.get("totalOrders", 0)

    if not order_list or not isinstance(order_list, list) or len(order_list) == 0 or total_orders == 0:
        return {
            "latest_order_name": None,
            "latest_order_date": None,
            "has_orders": False
        }

    latest_order = order_list[0]
    order_info = latest_order.get("info", {})

    line_items = order_info.get("line_items", [])
    item_names = [item.get("name", "Unknown Item") for item in line_items]

    if item_names:
        order_name = ", ".join(item_names)
    else:
        order_name = f"Order #{latest_order.get('displayId', 'N/A')}"

    order_date = parse_date(latest_order.get("createdAt"))

    return {
        "latest_order_name": order_name,
        "latest_order_date": order_date,
        "has_orders": True
    }


# ==========================================================
# DEPRECATED FUNCTIONS
# ==========================================================
def load_sessions_from_file():
    """Deprecated: Use get_all_active_users() instead."""
    logger.warning("load_sessions_from_file is deprecated and returns empty dict")
    return {}
