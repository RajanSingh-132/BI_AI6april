from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.chat_routes import router as chat_router
from routes.upload import router as upload_router
from mongo_client import MongoDBClient
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

app = FastAPI(title="AI Chatbot with MongoDB")

# MongoDB Instance
mongo = MongoDBClient()
app.state.mongo = mongo

# Shutdown Event
@app.on_event("shutdown")
def shutdown_db():
    mongo.close()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Routes with prefix (IMPORTANT)
app.include_router(chat_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

# Health Check
@app.get("/")
def home():
    return {"message": "AI Chatbot Running 🚀"}