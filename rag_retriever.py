import logging
from typing import List
from langchain_core.documents import Document
from embeddingclient import BedrockEmbeddingClient
from mongo_client import MongoDBClient
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGRetriever:

    def __init__(self):

        self.embedding_client = BedrockEmbeddingClient()
        self.mongo_client = MongoDBClient()
        self.collection = self.mongo_client.collection

        self.similarity_threshold = 0.65 
        self.max_results = 100

        logger.info("[RAG] Retriever Initialized")

    # ---------------------------------------------------------
    # 🔥 MAIN FUNCTION
    # ---------------------------------------------------------
    def get_relevant_documents(self, query: str) -> List[Document]:

        try:
            logger.info(f"[QUERY] {query}")

            # 🔥 FIX 1: correct embedding method
            query_embedding = self.embedding_client.generate_embedding(query)
            if not query_embedding:
                return []

            # 🔥 FIX 2: remove strict filter
            docs = list(self.collection.find({}))  # no type filter

            results = []

            query_vec = np.array(query_embedding)

            for doc in docs:

                embedding = doc.get("embedding")

                if not embedding:
                    continue

                doc_vec = np.array(embedding)

                # 🔥 FIX 3: safe cosine similarity
                denom = (np.linalg.norm(query_vec) * np.linalg.norm(doc_vec))

                if denom == 0:
                    continue

                similarity = np.dot(query_vec, doc_vec) / denom

                doc["score"] = float(similarity)
                results.append(doc)

            # 🔥 Sort ALL first
            results.sort(key=lambda x: x["score"], reverse=True)

            # 🔥 FIX 4: apply threshold AFTER sorting
            filtered = [r for r in results if r["score"] >= self.similarity_threshold]

            if not filtered:
                logger.warning("[RAG] No docs above threshold, returning top results")
                filtered = results[:self.max_results]

            else:
                filtered = filtered[:self.max_results]

            logger.info(f"[RESULTS] {len(filtered)} documents retrieved")

            # 🔥 Convert to LangChain Documents
            documents = []

            for doc in filtered:
                content = doc.get("content", "")
                metadata = doc.get("data", {})

                documents.append(
                    Document(
                        page_content=content,
                        metadata=metadata
                    )
                )

            return documents

        except Exception as e:
            logger.error(f"[ERR] {e}")
            return []

    # ---------------------------------------------------------
    async def aget_relevant_documents(self, query: str) -> List[Document]:
        return self.get_relevant_documents(query)