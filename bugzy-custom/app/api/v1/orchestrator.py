import logging
import time
from typing import Dict, Optional

from app.config.product_registry import detect_product_from_order, get_agent_from_product_value, BugzyProduct
from app.services.crm.sessions import fetch_order_details, extract_order_details

# Import product-specific API handlers
from app.api.v1 import ams_api
from app.api.v1 import gut_cleanse_api
from app.api.v1 import free_form_api

logger = logging.getLogger(__name__)

# Cache for user product type to avoid API calls on every message chunk
# user_id -> BugzyProduct
USER_PRODUCT_CACHE = {}

def get_product_module(user_id: str):
    """
    Determine which product module to use for a given user.
    Uses a multi-tier detection strategy:
    1. In-memory cache
    2. Persisted session in MongoDB (user_order field)
    3. CRM API fallback
    """
    if user_id in USER_PRODUCT_CACHE:
        product = USER_PRODUCT_CACHE[user_id]
        # logging.info(f"Using cached product {product.value} for user {user_id}")
    else:
        # Step 1: Check MongoDB for existing session; use stored product for routing (no re-detect)
        try:
            from app.services.crm.sessions import load_user_session
            session = load_user_session(user_id)
            if session:
                stored_product = session.get("product")
                if stored_product:
                    product = get_agent_from_product_value(stored_product)
                    USER_PRODUCT_CACHE[user_id] = product
                    return _get_module_by_product(product)
                if session.get("user_order"):
                    order_name = session.get("user_order")
                    product = detect_product_from_order(order_name)
                    logger.info(f"Detected product {product.value} for user {user_id} from DB session")
                    USER_PRODUCT_CACHE[user_id] = product
                    return _get_module_by_product(product)
        except Exception as e:
            logger.warning(f"Error checking DB session for {user_id}: {str(e)}")

        # Step 2: Fetch order from CRM and detect
        try:
            # We need phone number, assuming user_id IS phone number
            response = fetch_order_details(user_id)
            info = extract_order_details(response)
            order_name = info.get("latest_order_name")
            product = detect_product_from_order(order_name)
            logger.info(f"Detected product {product.value} for user {user_id} based on CRM order: {order_name}")
        except Exception as e:
            logger.warning(f"Could not fetch order for {user_id}: {str(e)}. Defaulting to FREE_FORM.")
            product = BugzyProduct.FREE_FORM  # Fallback
        
        USER_PRODUCT_CACHE[user_id] = product
    
    return _get_module_by_product(product)

def _get_module_by_product(product: BugzyProduct):
    """Helper to return the correct module based on product enum"""
    if product == BugzyProduct.AMS:
        return ams_api
    elif product == BugzyProduct.GUT_CLEANSE:
        return gut_cleanse_api
    else:
        # Default to free_form for all other products
        return free_form_api


# --- Proxy Functions ---

async def process_batched_message(user_id: str, text: str):
    """Proxy for process_batched_message"""
    module = get_product_module(user_id)
    await module.process_batched_message(user_id, text)

def schedule_batch_flush(user_id: str):
    """Proxy for schedule_batch_flush"""
    module = get_product_module(user_id)
    return module.schedule_batch_flush(user_id)

def get_button_text_from_id(button_id: str, button_title: str = None) -> str:
    """
    Proxy for get_button_text_from_id.
    Note: This function doesn't take user_id, so we can't easily route based on user.
    However, button IDs should be unique enough or we iterate through modules.
    
    Strategy: Try AMS and Gut Cleanse first (specific), then Free Form.
    """
    # Try AMS first
    text = ams_api.get_button_text_from_id(button_id, button_title)
    # If AMS returned something different from default (button_title or button_id), use it
    if text != (button_title or button_id):
        return text
        
    # Try Gut Cleanse
    text = gut_cleanse_api.get_button_text_from_id(button_id, button_title)
    # Gut Cleanse may return button_id itself (e.g., "age_eligible_no") for router matching
    # Check if it's a known gut_cleanse profiling button ID - if so, always use gut_cleanse result
    gut_cleanse_profiling_buttons = [
        "age_eligible_yes", "age_eligible_no",
        "gender_male", "gender_female", "gender_prefer_not_to_say",
        "pregnancy_no", "pregnancy_yes_pregnant", "pregnancy_yes_breastfeeding"
    ]
    if button_id in gut_cleanse_profiling_buttons:
        # Always return gut_cleanse result for profiling buttons (even if it equals button_id)
        # This ensures "age_eligible_no" is returned instead of falling through to Free Form
        return text
    # For other buttons, check if gut_cleanse returned something different from default
    # (i.e., it actually handled the button, not just returned button_title)
    default_text = button_title if button_title else button_id
    if text != default_text:
        return text

    # Fallback to Free Form (handles all other products)
    return free_form_api.get_button_text_from_id(button_id, button_title)

async def process_node_reaction(state: Dict, user_id: str, message_id: str):
    """Proxy for process_node_reaction"""
    module = get_product_module(user_id)
    await module.process_node_reaction(state, user_id, message_id)

async def handle_resume_flow(user_id: str, state: Dict, current_question: str):
    """Proxy for handle_resume_flow"""
    module = get_product_module(user_id)
    await module.handle_resume_flow(user_id, state, current_question)

def get_batched_message(user_id: str) -> Optional[str]:
    """Proxy for get_batched_message"""
    module = get_product_module(user_id)
    return module.get_batched_message(user_id)

# --- New Orchestration Helper ---

def handle_incoming_text_message(user_id: str, text: str, last_question: str):
    """
    Handles buffering/batching of text messages by delegating to the correct product module.
    Replaces the manual dict manipulation in api.py.
    """
    module = get_product_module(user_id)
    
    # Access the module's PENDING_MESSAGES
    pending_messages = module.PENDING_MESSAGES
    
    if user_id not in pending_messages:
        pending_messages[user_id] = {
            "messages": [],
            "timer": 0, # Will be set below
            "last_question": last_question,
            "flusher_running": False
        }

    # Add current message to batch
    pending_messages[user_id]["messages"].append(text)
    pending_messages[user_id]["timer"] = time.time()
    pending_messages[user_id]["last_question"] = last_question

    logger.info("📦 [Orchestrator] Added message to batch for user %s (Product: %s): '%s'", 
                user_id, USER_PRODUCT_CACHE[user_id].value, text)
    
    # Schedule batch flush
    module.schedule_batch_flush(user_id)

async def handle_resume_button(user_id: str, text: str):
    """
    Handle resume button explicitly bypassing batch
    """
    module = get_product_module(user_id)
    
    # Clear pending messages
    if user_id in module.PENDING_MESSAGES:
        module.PENDING_MESSAGES.pop(user_id, None)
        
    # Process immediately
    await module.process_batched_message(user_id, text)
