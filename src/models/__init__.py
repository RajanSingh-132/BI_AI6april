"""
Models module - Compatibility wrapper
Re-exports models to maintain backward compatibility
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Re-export from local models file OR original models.py
try:
    from src.models.models import Message, ChatRequest, ChatResponse, HealthResponse, RetrievalContext
except ImportError:
    from models import Message, ChatRequest, ChatResponse, HealthResponse, RetrievalContext

__all__ = [
    "Message",
    "ChatRequest",
    "ChatResponse",
    "HealthResponse",
    "RetrievalContext",
]