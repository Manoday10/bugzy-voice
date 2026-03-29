"""
REST API routes for chat query endpoint.

This module defines the /v1/chat/query endpoint for Node.js backend integration.
"""

from fastapi import APIRouter, HTTPException
from app.api.v1.models import (
    ChatbotPayload,
    ChatbotResponse,
    ChatMessageResponse,
    ImageAnalysisRequest,
    ImageAnalysisResponse,
    ImageAnalysisMetadata,
    ChatHistoryRequest,
    ChatHistoryResponse,
    FoodTrackerRequest,
    FoodTrackerResponse,
    MessagesSinceRequest,
    MessagesSinceResponse
)
from app.api.v1.chat_handler import (
    process_chat_message,
    estimate_tokens,
    process_image_analysis,
    get_chat_history_by_phone,
    process_food_tracker_request,
    get_messages_since
)

router = APIRouter()


@router.post("/v1/chat/query", response_model=ChatbotResponse)
async def chat_query(payload: ChatbotPayload) -> ChatbotResponse:
    """
    Process a chat message and return the AI response.
    
    This endpoint is designed for integration with the Node.js backend.
    It accepts a message with optional context and returns the chatbot's response.
    
    Args:
        payload: ChatbotPayload containing user_id, message, conversation_id, and context
    
    Returns:
        ChatbotResponse with the AI's response and metadata
    
    Raises:
        HTTPException: If there's an error processing the message
    """
    try:
        # Extract context if provided
        context_dict = None
        if payload.context:
            context_dict = {
                "recent_messages": [
                    msg.model_dump() for msg in payload.context.recent_messages
                ]
            }

        # Process the message through the chatbot
        # Returns dict with 'messages' array and 'joined_response' string
        result = process_chat_message(
            user_id=payload.user_id,
            message=payload.message,
            conversation_id=payload.conversation_id,
            context=context_dict
        )

        # Estimate tokens used
        tokens = estimate_tokens(payload.message + result["joined_response"])

        # Build structured messages from result
        structured_messages = [
            ChatMessageResponse(**msg) for msg in result["messages"]
        ]

        # Return the response with both structured messages and joined string
        return ChatbotResponse(
            messages=structured_messages,
            response=result["joined_response"],  # Backward compatibility
            sources=[],
            confidence=None,
            intent=None,
            tokens_used=tokens
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat message: {str(e)}"
        )


@router.post("/v1/chat/image-analysis", response_model=ImageAnalysisResponse)
async def image_analysis(payload: ImageAnalysisRequest) -> ImageAnalysisResponse:
    """
    Analyze an image using vision AI.

    Stateless endpoint - no session management.

    Returns:
        ImageAnalysisResponse with analysis and metadata

    Raises:
        HTTPException: 400 (validation), 404 (image not found),
                      500 (internal), 503 (AI service unavailable)
    """
    try:
        # Validate required fields (Pydantic allows empty strings)
        if not payload.image_url or not payload.image_url.strip():
            raise HTTPException(
                status_code=400,
                detail="image_url is required and cannot be empty"
            )

        if not payload.message or not payload.message.strip():
            raise HTTPException(
                status_code=400,
                detail="message is required and cannot be empty"
            )

        # Extract context if provided
        context_dict = None
        if payload.context:
            context_dict = {
                "recent_messages": [
                    msg.model_dump() for msg in payload.context.recent_messages
                ]
            }

        # Process image analysis
        result = process_image_analysis(
            user_id=payload.user_id,
            image_url=payload.image_url,
            message=payload.message,
            conversation_id=payload.conversation_id,
            context=context_dict,
            auth_token=None
        )

        # Handle errors
        if not result["success"]:
            error_msg = result.get("error", "Unknown error")

            # Map to appropriate HTTP status
            if "download" in error_msg.lower() or "not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            elif "timeout" in error_msg.lower():
                raise HTTPException(status_code=503, detail=error_msg)
            elif "invalid" in error_msg.lower() or "size" in error_msg.lower():
                raise HTTPException(status_code=400, detail=error_msg)
            else:
                raise HTTPException(status_code=500, detail=error_msg)

        # Build metadata with SNAP-specific fields
        raw_metadata = result.get("metadata", {})
        metadata = ImageAnalysisMetadata(
            analysis_type=raw_metadata.get("analysis_type"),
            category=raw_metadata.get("category"),  # SNAP category: "A", "B", or "C"
            image_dimensions=raw_metadata.get("image_dimensions"),
            image_format=raw_metadata.get("image_format"),
            image_size_bytes=raw_metadata.get("image_size_bytes"),
            processing_time_ms=raw_metadata.get("processing_time_ms"),
            model_used=raw_metadata.get("model_used"),
            validation_details=raw_metadata.get("validation_details"),  # SNAP validation steps
            raw_output=raw_metadata.get("raw_output"),  # SNAP raw LLM output
            reasoning=raw_metadata.get("reasoning")  # CoT reasoning from SNAP
        )

        # Return response
        return ImageAnalysisResponse(
            response=result["response"],
            confidence=result.get("confidence"),
            intent=result.get("intent"),
            metadata=metadata,
            sources=None
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing image analysis: {str(e)}"
        )


@router.post("/v1/chat/history", response_model=ChatHistoryResponse)
async def chat_history(payload: ChatHistoryRequest) -> ChatHistoryResponse:
    """
    Get chat history for a user by their phone number.
    
    This endpoint retrieves conversation history for a user identified by their phone number.
    Supports optional filtering by conversation_id, source, and pagination.
    
    Args:
        payload: ChatHistoryRequest containing:
            - phone_number: Required - user's phone number
            - conversation_id: Optional - filter by conversation ID
            - source: Optional - filter by source ("whatsapp" or "app")
            - limit: Optional - limit number of messages
            - offset: Optional - pagination offset (default: 0)
    
    Returns:
        ChatHistoryResponse with user info and chat history
    
    Raises:
        HTTPException: If user not found (404) or server error (500)
    """
    try:
        # Validate phone number
        if not payload.phone_number or not payload.phone_number.strip():
            raise HTTPException(
                status_code=400,
                detail="phone_number is required and cannot be empty"
            )
        
        # Validate source filter if provided
        if payload.source and payload.source not in ["whatsapp", "app"]:
            raise HTTPException(
                status_code=400,
                detail="source must be 'whatsapp' or 'app'"
            )
        phone_number = f"91{payload.phone_number}"
        # Get chat history with filters
        result = get_chat_history_by_phone(
            phone_number=phone_number,
            conversation_id=payload.conversation_id,
            source=payload.source,
            limit=payload.limit,
            offset=payload.offset or 0
        )
        
        # Check if user was found
        if not result.get("success"):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "User not found")
            )
        
        # Return response with enhanced metadata
        return ChatHistoryResponse(
            full_chat_history=result.get("full_chat_history", []),
            total_messages=result.get("total_messages", 0),
            user_id=result.get("user_id"),
            user_name=result.get("user_name"),
            phone_number=result.get("phone_number"),
            last_updated=result.get("last_updated")
        )
    
    except HTTPException:
        raise
    

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching chat history: {str(e)}"
        )


@router.post("/v1/chat/food-tracker", response_model=FoodTrackerResponse)
async def food_tracker(payload: FoodTrackerRequest) -> FoodTrackerResponse:
    """
    Analyze food image for tracking macros (Food Tracker feature).
    
    Returns strict structured JSON with macros, micros, and benefits.
    """
    try:
        result = process_food_tracker_request(
            image_url=payload.image_url,
            user_id=payload.user_id,
            auth_token=payload.auth_token
        )

        # Build Response
        from app.api.v1.models import FoodContent
        
        data = result.get("data", {})
        response_content = FoodContent(
            food_name=data.get("food_name"),
            calories=data.get("calories"),
            protein=data.get("protein"),
            fiber=data.get("fiber"),
            fat=data.get("fat")
        )

        return FoodTrackerResponse(
            response=response_content
        )

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Food tracker endpoint error: %s", e, exc_info=True)
        
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing food tracker analysis: {str(e)}"
        )


@router.post("/v1/chat/messages-since", response_model=MessagesSinceResponse)
async def messages_since(payload: MessagesSinceRequest) -> MessagesSinceResponse:
    """
    Get assistant messages generated after a specific timestamp.
    
    Args:
        payload: MessagesSinceRequest containing:
            - user_id: User's phone number (with country code)
            - since_timestamp: ISO-8601 timestamp to filter after
            - source: Optional source filter (default: "app")
    
    Returns:
        MessagesSinceResponse with messages and count
    
    Raises:
        HTTPException: If validation fails (400) or server error (500)
    """
    try:
        # Validate user_id
        if not payload.user_id or not payload.user_id.strip():
            raise HTTPException(
                status_code=400,
                detail="user_id is required and cannot be empty"
            )
        
        # Validate timestamp
        if not payload.since_timestamp or not payload.since_timestamp.strip():
            raise HTTPException(
                status_code=400,
                detail="since_timestamp is required and cannot be empty"
            )
        
        # Validate source filter if provided
        if payload.source and payload.source not in ["whatsapp", "app"]:
            raise HTTPException(
                status_code=400,
                detail="source must be 'whatsapp' or 'app'"
            )
        
        # Get messages since timestamp
        result = get_messages_since(
            user_id=payload.user_id,
            since_timestamp=payload.since_timestamp,
            source=payload.source
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to fetch messages")
            )
        
        return MessagesSinceResponse(
            messages=result.get("messages", []),
            total_count=result.get("total_count", 0)
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching messages: {str(e)}"
        )