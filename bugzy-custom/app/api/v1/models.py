"""
Pydantic models for REST API integration with Node.js backend.

This module defines request and response models that match the TypeScript
interfaces used by the Node.js backend application.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel


class ChatbotContextMessage(BaseModel):
    """
    Message in conversation history context.
    Matches the TypeScript ChatbotContextMessage interface.
    """
    role: str  # "user" or "assistant"
    content: str
    timestamp: str  # ISO-8601 date string


class ChatbotContext(BaseModel):
    """
    Context object containing recent conversation history.
    """
    recent_messages: List[ChatbotContextMessage] = []


class ChatbotPayload(BaseModel):
    """
    Request payload for chat query endpoint.
    Matches the TypeScript ChatbotPayload interface.
    """
    user_id: str
    message: str
    conversation_id: Optional[str] = None
    context: Optional[ChatbotContext] = None


class ChatMessageResponse(BaseModel):
    """
    Individual message in the AI response.
    Supports multi-message responses from the chatbot.
    """
    role: Literal["assistant"] = "assistant"
    content: str
    timestamp: str  # ISO-8601 date string
    metadata: Optional[Dict[str, Any]] = None


class ChatbotResponse(BaseModel):
    """
    Response from chat query endpoint.
    Matches the TypeScript ChatbotResponse interface.
    Now includes structured messages array for multi-message support.
    """
    messages: List[ChatMessageResponse] = []  # Array of structured messages
    response: str  # Kept for backward compatibility (joined version)
    sources: Optional[List[Any]] = None
    confidence: Optional[float] = None
    intent: Optional[str] = None
    tokens_used: Optional[int] = None

    class Config:
        # Allow additional fields that might be added in the future
        extra = "allow"


# Image Analysis Models
class ImageAnalysisContextMessage(BaseModel):
    """
    Message in image analysis conversation history.
    """
    role: str  # "user" or "assistant"
    content: str
    timestamp: str  # ISO-8601 format


class ImageAnalysisContext(BaseModel):
    """
    Context object containing recent conversation history for image analysis.
    """
    recent_messages: List[ImageAnalysisContextMessage] = []


class ImageAnalysisRequest(BaseModel):
    """
    Request payload for image analysis endpoint.
    """
    user_id: str
    image_url: str
    message: str
    conversation_id: Optional[str] = None
    context: Optional[ImageAnalysisContext] = None


class ImageAnalysisMetadata(BaseModel):
    """
    Structured metadata for image analysis results with SNAP fields.
    """
    analysis_type: Optional[str] = None
    category: Optional[str] = None  # SNAP category: "A", "B", or "C"
    image_dimensions: Optional[Dict[str, int]] = None
    image_format: Optional[str] = None
    image_size_bytes: Optional[int] = None
    processing_time_ms: Optional[float] = None
    model_used: Optional[str] = None
    validation_details: Optional[List[str]] = None  # SNAP validation steps
    raw_output: Optional[str] = None  # SNAP raw LLM output
    reasoning: Optional[str] = None  # CoT reasoning from SNAP

    class Config:
        extra = "allow"


class ImageAnalysisResponse(BaseModel):
    """
    Response from image analysis endpoint.
    """
    response: str
    confidence: Optional[float] = None
    intent: Optional[str] = None
    metadata: Optional[ImageAnalysisMetadata] = None
    sources: Optional[List[Any]] = None

    class Config:
        extra = "allow"


# Chat History Models
class ChatHistoryRequest(BaseModel):
    """
    Request payload for chat history endpoint.
    """
    phone_number: str
    conversation_id: Optional[str] = None  # Optional: filter by conversation_id
    source: Optional[str] = None  # Optional: filter by source ("whatsapp" or "app")
    limit: Optional[int] = None  # Optional: limit number of messages returned
    offset: Optional[int] = 0  # Optional: pagination offset



class ChatHistoryResponse(BaseModel):
    """
    Response from chat history endpoint containing full chat history.
    """
    full_chat_history: List[Dict[str, Any]] = []
    total_messages: int = 0  # Total messages before filtering/pagination
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    phone_number: Optional[str] = None
    last_updated: Optional[str] = None
    
    class Config:
        extra = "allow"


# Food Tracker Models


class FoodTrackerRequest(BaseModel):
    """
    Request payload for food tracker endpoint.
    Matches ImageAnalysisRequest structure.
    """
    user_id: Optional[str] = None
    image_url: str
    conversation_id: Optional[str] = None
    context: Optional[ImageAnalysisContext] = None
    auth_token: Optional[str] = None






class FoodContent(BaseModel):
    """
    Structured food nutritional content.
    """
    food_name: Optional[str] = None
    calories: Optional[float] = None
    protein: Optional[float] = None
    fiber: Optional[float] = None
    fat: Optional[float] = None

class FoodTrackerResponse(BaseModel):
    """
    Response from food tracker endpoint.
    Matches attributes of ImageAnalysisResponse but with structured response data.
    """
    response: Optional[FoodContent] = None

    class Config:
        extra = "allow"


class MessagesSinceRequest(BaseModel):
    """
    Request payload for messages-since endpoint.
    Used to fetch assistant messages generated after a specific timestamp.
    """
    user_id: str  # Phone number (with country code, e.g., "919876543210")
    since_timestamp: str  # ISO-8601 timestamp to filter messages after
    source: Optional[str] = "app"  # Optional: filter by source ("whatsapp" or "app")


class MessagesSinceResponse(BaseModel):
    """
    Response from messages-since endpoint.
    Returns assistant messages logged after the given timestamp.
    """
    messages: List[Dict[str, Any]] = []  # List of message dicts with role, content, timestamp, metadata
    total_count: int = 0

    class Config:
        extra = "allow"
