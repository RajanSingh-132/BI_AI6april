import logging
import certifi
import os
import numpy as np
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MongoDBClient:

    def __init__(self, uri: str = None, db_name: str = None):

        self.uri = uri or os.getenv("MONGO_URI")
        self.db_name = db_name or os.getenv("DB_NAME")

        self.client = None
        self.db = None

        self.collection = None          # documents
        self.results_collection = None  # results

        self.connect()

    # ----------------------------
    # Connect
    # ----------------------------
    def connect(self):

        try:
            logger.info("[MONGO] Connecting to MongoDB...")

            self.client = MongoClient(
                self.uri,
                tls=True,
                tlsCAFile=certifi.where(),
                retryWrites=True,
                retryReads=True,
                serverSelectionTimeoutMS=20000
            )

            self.client.admin.command("ping")

            self.db = self.client[self.db_name]

            self.collection = self.db["documents"]
            self.results_collection = self.db["results"]  # ✅ your collection

            logger.info("[MONGO] Connected successfully ✅")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"[MONGO] Connection failed: {e}")
            raise

    # ----------------------------
    # Insert Documents
    # ----------------------------
    def insert_documents(self, documents):

        try:
            if not documents:
                logger.warning("[MONGO] No documents to insert")
                return False

            result = self.collection.insert_many(documents)

            logger.info(f"[MONGO] Inserted {len(result.inserted_ids)} documents")
            return True

        except Exception as e:
            logger.error(f"[MONGO] Insert error: {e}")
            return False

    # ----------------------------
    # Save Result
    # ----------------------------
    def save_result(self, result_data):

        try:
            result_data["query"] = result_data["query"].strip().lower()

            print("📦 Saving to collection:", self.results_collection.name)

            self.results_collection.insert_one(result_data)

            logger.info("[MONGO] Result saved ✅")

        except Exception as e:
            logger.error(f"[MONGO] Save result error: {e}")

    # ----------------------------
    # Get Cached Result
    # ----------------------------
    def get_cached_result(self, file_name, query):

        try:
            result = self.results_collection.find_one({
                "file_name": file_name,
                "query": query.strip().lower()
            })
            return result
        except Exception as e:
            logger.error(f"[MONGO] Fetch result error: {e}")
            return None

    # ----------------------------
    # Vector Search
    # ----------------------------
    def vector_search(
        self,
        query_embedding,
        limit=5,
        similarity_threshold=0.65,
        metadata_filters=None
    ):

        try:
            logger.info("[MONGO] Running manual vector search")

            docs = list(self.collection.find(metadata_filters or {}))

            query_vec = np.array(query_embedding)
            results = []

            for doc in docs:
                embedding = doc.get("embedding")
                if not embedding:
                    continue

                doc_vec = np.array(embedding)

                similarity = np.dot(query_vec, doc_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
                )

                if similarity >= similarity_threshold:
                    doc["score"] = float(similarity)
                    results.append(doc)

            results.sort(key=lambda x: x["score"], reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"[MONGO] Vector search error: {e}")
            return []

    # ----------------------------
    # Close
    # ----------------------------
    def close(self):

        if self.client:
            self.client.close()
            logger.info("[MONGO] Connection closed 🔌")


# 🔥 SINGLE INSTANCE
mongo_client = MongoDBClient()