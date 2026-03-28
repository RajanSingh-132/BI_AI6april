"""
Core module - Compatibility wrapper
Re-exports original modules to maintain backward compatibility
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Re-export original modules
from prompt import SYSTEM_PROMPT, format_response, REVENUE_PIE_CHART
from embeddingclient import BedrockEmbeddingClient
from rag_engine import RAGEngine
from rag_retriever import RAGRetriever

__all__ = [
    "SYSTEM_PROMPT",
    "format_response",
    "REVENUE_PIE_CHART",
    "BedrockEmbeddingClient",
    "RAGEngine",
    "RAGRetriever",
]