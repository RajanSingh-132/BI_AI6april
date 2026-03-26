from pymongo import MongoClient
import os
from dotenv import load_dotenv

# ----------------------------
# Load env variables
# ----------------------------

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

if not MONGO_URI:
    raise ValueError("MONGO_URI missing")

if not DB_NAME:
    raise ValueError("DB_NAME missing")

# ----------------------------
# Connect Mongo
# ----------------------------

client = MongoClient(MONGO_URI)

db = client[DB_NAME]

documents_collection = db["documents"]

print("\nConnected to DB:", db.name)
print("Collection:", documents_collection.name)

# ----------------------------
# Show collections
# ----------------------------

print("\nCollections in DB:")
print(db.list_collection_names())

# ----------------------------
# Document count
# ----------------------------

count = documents_collection.count_documents({})
print("\nTotal documents:", count)

if count == 0:
    print("❌ No documents in collection")
    exit()

# ----------------------------
# Inspect sample document
# ----------------------------

doc = documents_collection.find_one()

print("\nSample document keys:", list(doc.keys()))

# ----------------------------
# Check embedding
# ----------------------------

if "embedding" not in doc:

    print("❌ embedding field missing")

else:

    embedding = doc["embedding"]

    print("\nEmbedding length:", len(embedding))
    print("Embedding type:", type(embedding))

    if isinstance(embedding, list):
        print("✅ Embedding stored correctly as list")
    else:
        print("❌ Embedding should be a list")

# ----------------------------
# Normal Mongo indexes
# ----------------------------

print("\nStandard Mongo indexes:")
print(documents_collection.index_information())

# ----------------------------
# Search indexes (VECTOR INDEX)
# ----------------------------

print("\nSearch indexes:")

try:

    search_indexes = list(documents_collection.list_search_indexes())

    print(search_indexes)

    if not search_indexes:
        print("❌ No search index found on this collection")

except Exception as e:

    print("Search index check failed:", e)

# ----------------------------
# Vector search test
# ----------------------------

print("\nRunning vector search test...")

pipeline = [
    {
        "$vectorSearch": {
            "index": "default",
            "path": "embedding",
            "queryVector": [0.1] * 1024,
            "numCandidates": 100,
            "limit": 3
        }
    },
    {
        "$project": {
            "topic": 1,
            "score": {"$meta": "vectorSearchScore"}
        }
    }
]

try:

    results = list(documents_collection.aggregate(pipeline))

    print("\nVector results:", len(results))

    for r in results:
        print("Topic:", r.get("topic"), "| Score:", r.get("score"))

except Exception as e:

    print("❌ Vector search failed:", str(e))