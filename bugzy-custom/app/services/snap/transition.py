import logging
import time
from app.services.crm.sessions import SESSIONS, save_session_to_file
from app.config.product_registry import detect_product_from_order
from app.api.v1.constants import KEY_USER_MSG, KEY_LAST_QUESTION, STATE_SNAP_COMPLETE

logger = logging.getLogger(__name__)

def continue_snap_flow_after_image(user_id: str, state: dict) -> None:
    """
    Handles the continuation of the flow after a SNAP image has been processed.
    Determines the correct product graph to load and invokes it with a synthetic message.
    """
    logger.info("User %s is at transitioning_to_snap, triggering graph to continue flow", user_id)
    
    # We need to detect which product the user is on to load the correct product graph
    # Try to get from session first
    product = state.get("product")
    user_order = state.get("user_order")
    
    if not product and user_order:
        try:
            product_enum = detect_product_from_order(user_order)
            product = product_enum.value
            logger.info("Detected product for %s from order: %s", user_id, product)
        except Exception as e:
            logger.warning("Error detecting product from order for %s: %s", user_id, e)
    
    # Default to AMS if still unknown (shouldn't happen at this stage ideally)
    if not product:
        logger.warning("Product not found in session for %s during SNAP transition, defaulting to ama_muscle_science", user_id)
        product = "ama_muscle_science"
    
    # Load the appropriate graph based on product
    # Note: Dynamic imports to avoid circular dependencies if any, and because this is a specific flow helper
    try:
        if product in ["ams", "ama_muscle_science"]:
            from app.services.chatbot.bugzy_ams.agent import graph
            logger.info("Loaded AMS graph for user %s", user_id)
        elif product == "gut_cleanse":
            from app.services.chatbot.bugzy_gut_cleanse.agent import graph
            logger.info("Loaded Gut Cleanse graph for user %s", user_id)
        else:
            # Fallback to free form (though unlikely for SNAP flow)
            from app.services.chatbot.bugzy_free_form.agent import graph
            logger.info("Loaded Free Form graph for user %s", user_id)
        
        # Manually inject a "continue" message to trigger the graph
        # The graph state should have "last_question" set to "snap_complete" or handled by the node
        state[KEY_USER_MSG] = "[IMAGE_RECEIVED]"
        
        # Invoke graph
        # Note: graph.stream yields events which are dicts like {node_name: {state_updates}}
        for event in graph.stream(state):
            for v in event.values():
                state.update(v)
                
        # Ensure user_id is preserved
        if "user_id" not in state:
            state["user_id"] = user_id
        
        # Update global SESSIONS - this helper modifies the state dict in place, 
        # but we ensure it's saved back to SESSIONS and file
        SESSIONS[user_id] = state
        save_session_to_file(user_id, state)
        logger.info("Successfully continued SNAP flow for user %s", user_id)
        
    except Exception as e:
        logger.exception("Error continuing SNAP flow for user %s: %s", user_id, e)
