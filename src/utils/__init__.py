"""
Utils module - Compatibility wrapper
Re-exports utilities to maintain backward compatibility
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Re-export original modules
from request_tracker import tracker
from semanticstore import process_dataset, split_fields
from data_ingestion import *

__all__ = [
    "tracker",
    "process_dataset",
    "split_fields",
]