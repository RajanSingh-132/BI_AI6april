"""
Routes module - Compatibility wrapper
Re-exports routes to maintain backward compatibility
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

__all__ = ["chat_routes", "upload"]