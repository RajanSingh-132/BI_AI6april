import os
from dotenv import load_dotenv
from mongo_client import MongoDBClient

# Load environment variables
load_dotenv()

uri = os.getenv("MONGO_URI")
db_name = os.getenv("DB_NAME")

mongo = MongoDBClient(uri, db_name)

mongo.connect_with_retry()

print("✅ MongoDB Connected Successfully")

mongo.close()