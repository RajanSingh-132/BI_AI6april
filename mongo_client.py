import time
import logging
import certifi
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Load .env
load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MongoDBClient:
    def __init__(self, uri: str = None, db_name: str = None, max_retries: int = 5, retry_delay: int = 2):
        """
        Initialize MongoDB client settings
        """
        # Get from ENV if not provided
        self.uri = uri or os.getenv("MONGO_URI")
        self.db_name = db_name or os.getenv("DB_NAME")
        self.collection_name = "conversations"

        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.client = None
        self.db = None
        self.collection = None

    def connect_with_retry(self):
        """
        Establish MongoDB connection with retry logic
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"[MONGO] Connection attempt {attempt}/{self.max_retries}")

                self.client = MongoClient(
                    self.uri,
                    tls=True,
                    tlsCAFile=certifi.where(),
                    retryWrites=True,
                    retryReads=True,
                    serverSelectionTimeoutMS=20000,
                    connectTimeoutMS=20000,
                    socketTimeoutMS=30000,
                    maxPoolSize=10,
                    minPoolSize=2,
                )

                # Test connection
                self.client.admin.command("ping")

                self.db = self.client[self.db_name]

                # Set collection
                self.collection = self.db[self.collection_name]

                logger.info("[MONGO] Connected successfully ✅")
                return

            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"[MONGO] Connection failed: {e}")

                if attempt == self.max_retries:
                    raise Exception("❌ Could not connect to MongoDB after retries")

                time.sleep(self.retry_delay)

    def close(self):
        """
        Close MongoDB connection
        """
        if self.client:
            self.client.close()
            logger.info("[MONGO] Connection closed 🔌")