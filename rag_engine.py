import logging
import json
import os
from typing import List, Dict, Any
from models import Message
from rag_retriever import RAGRetriever
from prompt import SYSTEM_PROMPT
from google import genai
from mongo_client import MongoDBClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGEngine:

    def __init__(self):

        try:
            self.retriever = RAGRetriever()
            self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

            # Mongo for structured queries
            self.mongo_client = MongoDBClient()
            self.collection = self.mongo_client.collection

            logger.info("[RAG_ENGINE] Initialized")

        except Exception as e:
            logger.error(f"[RAG_ENGINE_ERR] Init failed: {e}")
            raise

    # =========================================================
    # 🔥 DYNAMIC DATA FETCH
    # =========================================================
    def fetch_data(self, query: str):

        words = query.lower().split()

        docs = list(self.collection.find())

        for doc in docs:
            data = doc.get("data", {})

            for field, value in data.items():

                if isinstance(value, str):

                    for word in words:

                        if word in value.lower():
                            return [doc.get("data", {}) for doc in docs]

        return []

    # =========================================================
    # 🔥 AUTO NUMERIC DETECTION
    # =========================================================
    def detect_numeric_field(self, data):

        for row in data:
            for k, v in row.items():
                if isinstance(v, (int, float)):
                    return k
        return None

    # =========================================================
    # 🔥 CALCULATION ENGINE
    # =========================================================
    def calculate(self, query, data):

        if not data:
            return None

        query = query.lower()
        field = self.detect_numeric_field(data)

        if not field:
            return None

        if "total" in query or "sum" in query:
            total = sum(d.get(field, 0) for d in data)
            return f"Total {field} is {total}"

        if "average" in query:
            avg = sum(d.get(field, 0) for d in data) / len(data)
            return f"Average {field} is {round(avg, 2)}"

        if "count" in query or "how many" in query:
            return f"Total records are {len(data)}"

        return None

    # =========================================================
    # 🚀 MAIN PIPELINE
    # =========================================================
    def process_query(
        self,
        query: str,
        chat_history: List[Message]
    ) -> Dict[str, Any]:

        try:

            logger.info(f"[RAG_ENGINE] Query: {query}")

            # =========================================================
            # 🔥 STEP 1: TRY STRUCTURED DATA + CALCULATION
            # =========================================================
            data = self.fetch_data(query)

            calc_result = self.calculate(query, data)

            if calc_result:
                return {
                    "answer": calc_result,
                    "type": "calculated"
                }

            # =========================================================
            # 🔥 STEP 2: RAG RETRIEVAL
            # =========================================================
            retrieval_result = self.retriever.retrieve(query)

            chunks = retrieval_result.get("chunks", [])
            structured_data = retrieval_result.get("structured_data", [])

            if not chunks:
                return {
                    "answer": "⚠️ No relevant data found.",
                    "type": "decline"
                }

            # =========================================================
            # 🔥 STEP 3: BUILD PROMPT
            # =========================================================
            context_text = "\n\n".join(chunks)
            structured_json = json.dumps(structured_data[:5000], indent=2)

            prompt = f"""
{SYSTEM_PROMPT}

Context:
{context_text}

Structured Data:
{structured_json}

User Query:
{query}
"""

            # =========================================================
            # 🤖 LLM CALL
            # =========================================================
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            answer = getattr(response, "text", "")

            if not answer:
                return {
                    "answer": "⚠️ Empty response generated.",
                    "type": "error"
                }

            return {
                "answer": answer,
                "type": "text"
            }

        except Exception as e:

            logger.error(f"[RAG_ENGINE_ERR] {e}")

            return {
                "answer": "⚠️ System error occurred.",
                "type": "error"
            }

    # =========================================================
    # 🧹 CLEANUP
    # =========================================================
    def cleanup(self):

        try:
            if hasattr(self.retriever, "mongo_client"):
                self.retriever.mongo_client.close()

        except Exception as e:
            logger.error(f"[RAG_ENGINE_ERR] Cleanup failed: {e}")