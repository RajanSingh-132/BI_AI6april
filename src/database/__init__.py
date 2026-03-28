"""
Database module - Compatibility wrapper
Re-exports MongoDB client to maintain backward compatibility
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Re-export original module
from mongo_client import MongoDBClient, mongo_client

__all__ = ["MongoDBClient", "mongo_client"]