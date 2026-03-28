"""
FastAPI Application Factory
Initializes and configures the BHI Backend API
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    """
    app = FastAPI(
        title="BHI Backend API",
        description="Business Health Intelligence Analytics Engine",
        version="1.0.0"
    )
    
    # ===========================
    # CORS Middleware
    # ===========================
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ===========================
    # Initialize MongoDB
    # ===========================
    try:
        from mongo_client import mongo_client
        
        # Initialize MongoDB connection
        db_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        # mongo_client.connect(db_uri)  # May already be connected
        
        # Store in app state
        app.state.mongo = mongo_client
        
        logger.info("✅ MongoDB connected successfully")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise
    
    # ===========================
    # Initialize Upload Routes State
    # ===========================
    try:
        from routes.upload import ACTIVE_DATASET, ACTIVE_DATASETS
        
        app.state.ACTIVE_DATASET = ACTIVE_DATASET
        app.state.ACTIVE_DATASETS = ACTIVE_DATASETS
        
        logger.info("✅ Upload state initialized")
    except Exception as e:
        logger.error(f"❌ Upload state initialization failed: {e}")
        raise
    
    # ===========================
    # Register Routes
    # ===========================
    try:
        from routes.chat_routes import router as chat_router
        from routes.upload import router as upload_router
        
        app.include_router(chat_router, prefix="/api", tags=["chat"])
        app.include_router(upload_router, prefix="/api", tags=["upload"])
        
        logger.info("✅ Routes registered successfully")
    except Exception as e:
        logger.error(f"❌ Route registration failed: {e}")
        raise
    
    # ===========================
    # Health Check Endpoint
    # ===========================
    @app.get("/health")
    async def health_check():
        """
        Health check endpoint
        """
        return {
            "status": "healthy",
            "service": "BHI Backend API",
            "version": "1.0.0"
        }
    
    logger.info("✅ FastAPI application created successfully")
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )

