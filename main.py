"""
BHI Backend - Main Entry Point
Imports from restructured src package
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ===========================
# Import restructured app
# ===========================
from src.app import app

# ===========================
# Entry point for uvicorn
# ===========================
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
