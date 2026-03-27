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
            print("\n" + "🟣"*30)
            print("MONGO SAVE: Checkpoint 1 - Function called")
            print(f"   Data keys: {list(result_data.keys())}")
            
            # Validate required fields
            if not result_data.get("answer"):
                logger.warning("🟣 [MONGO] Empty answer, skipping save")
                print("🟣 [MONGO] Empty answer, skipping save")
                return False
            
            if not result_data.get("kpis"):
                logger.warning(f"🟣 [MONGO] No KPIs for query: {result_data.get('query')}")
                print(f"🟣 [MONGO] Warning: No KPIs for query: {result_data.get('query')}")
            
            if not result_data.get("charts"):
                logger.warning(f"🟣 [MONGO] No Charts for query: {result_data.get('query')}")
                print(f"🟣 [MONGO] Warning: No Charts for query: {result_data.get('query')}")
            
            print("\n🟣 MONGO SAVE: Checkpoint 2 - Preparing data")
            result_data["query"] = result_data["query"].strip().lower()
            result_data["timestamp"] = __import__('datetime').datetime.utcnow()

            print(f"   file_name: {result_data.get('file_name')}")
            print(f"   query: {result_data.get('query')}")
            print(f"   answer_length: {len(result_data.get('answer', ''))}")
            print(f"   kpis_count: {len(result_data.get('kpis', []))}")
            print(f"   charts_count: {len(result_data.get('charts', []))}")

            print("\n🟣 MONGO SAVE: Checkpoint 3 - Inserting to collection")
            print(f"   Collection name: {self.results_collection.name}")
            print(f"   Collection object: {self.results_collection}")

            insert_result = self.results_collection.insert_one(result_data)
            
            print(f"\n🟣 MONGO SAVE: Checkpoint 4 - Insert completed")
            print(f"   Inserted ID: {insert_result.inserted_id}")
            
            if insert_result.inserted_id:
                logger.info(f"✅ [MONGO] Result saved with ID: {insert_result.inserted_id}")
                print(f"✅ [MONGO] Result saved with ID: {insert_result.inserted_id}")
                print("🟣"*30 + "\n")
                return True
            else:
                logger.error("🟣 [MONGO] Insert failed - no ID returned")
                print("🟣 [MONGO] Insert failed - no ID returned")
                print("🟣"*30 + "\n")
                return False

        except Exception as e:
            logger.error(f"🟣 [MONGO] Save result error: {e}")
            print(f"🟣 [MONGO] SAVE ERROR: {e}")
            import traceback
            traceback.print_exc()
            print("🟣"*30 + "\n")
            return False

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