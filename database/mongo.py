from pymongo import MongoClient
from config import MONGO_URL, DB_NAME

client = MongoClient(MONGO_URL)

db = client[DB_NAME]

# Chat history collection
chat_collection = db["conversations"]

# Vector database collection
documents_collection = db["documents"]

# Upload file collection
results_collection = db["results"]