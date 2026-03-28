"""
Pydantic Models for Request/Response Validation
Defines API contracts for the AI Shine Tutor chatbot.
"""

from typing import List, Literal, Optional, Any, Dict
from pydantic import BaseModel, Field, validator


# -----------------------------
# Chat Message Model
# -----------------------------
class Message(BaseModel):
    """
    Represents one chat message in the conversation.
    """

    role: Literal["human", "ai"] = Field(
        ...,
        description="Sender of the message"
    )

    content: str = Field(
        ...,
        description="Message text"
    )

    type: Optional[str] = Field(
        default="text",
        description="Message rendering type"
    )

    @validator("content")
    def validate_content(cls, v):

        if not v or not v.strip():
            raise ValueError("Content cannot be empty")

        return v


# --------- -------------------------
# Chat Request Model
# -----------------------------
class ChatRequest(BaseModel):
    """
    Request payload for the chatbot API.
    """

    chat_history: List[Message] = Field(
        ...,
        description="Full conversation history"
    )
    
    active_datasets: Optional[List[str]] = Field(
        default=None,
        description="List of active dataset file names for multi-dataset support"
    )
    
    comparison_mode: Optional[bool] = Field(
        default=False,
        description="If True, enable comparison mode between multiple datasets"
    )

    @validator("chat_history")
    def validate_history(cls, v):

        if not v:
            raise ValueError("chat_history cannot be empty")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "chat_history": [
                    {
                        "role": "ai",
                        "content": "Hello! I'm AI Shine. Ask me anything.",
                        "type": "text"
                    },
                    {
                        "role": "human",
                        "content": "What is machine learning?",
                        "type": "text"
                    }
                ]
            }
        }


# -----------------------------
# Chat Response Model
# -----------------------------
class ChatResponse(BaseModel):
    """
    Response returned by chatbot API.
    """

    answer: str = Field(
        ...,
        description="AI generated response"
    )

    type: Literal["greeting", "text", "structured", "decline"] = Field(
        default="text",
        description="Frontend rendering type"
    )

    @validator("answer")
    def validate_answer(cls, v):

        if not v or not v.strip():
            raise ValueError("Answer cannot be empty")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "**Answer:** Machine learning allows systems to learn from data.\n\n**Key Points:**\n• Learns patterns\n• Improves over time",
                "type": "structured"
            }
        }


# -----------------------------
# Health Check Model
# --------- -------- --------
class HealthResponse(BaseModel):
    """
    Health check response.
    """

    api: str = Field(..., description="API status")

    rag_engine: str = Field(..., description="RAG engine status")

    components: Dict[str, str] = Field(
        default_factory=dict,
        description="Component status"
    )


# --------- -------- --------
# Retrieval Context
# --------- -------- --------
class RetrievalContext(BaseModel):
    """
    Internal retrieval result structure.
    """

    query: str = Field(..., description="Original query")

    documents: List[str] = Field(..., description="Retrieved documents")

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Retrieval metadata"
    )
