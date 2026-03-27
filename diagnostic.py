"""
DIAGNOSTIC: Full flow check
"""
from mongo_client import MongoDBClient
from routes import upload
import json

print("\n" + "="*70)
print("🔍 FULL DIAGNOSTIC - Results Saving Issue")
print("="*70 + "\n")

mongo = MongoDBClient()

print("1️⃣  ACTIVE_DATASET Status:")
print(f"   Current value: {upload.ACTIVE_DATASET}")
print(f"   Type: {type(upload.ACTIVE_DATASET)}\n")

print("2️⃣  MongoDB Collections Status:")
results_count = mongo.results_collection.count_documents({})
docs_count = mongo.collection.count_documents({"type": "dataset"})
embedding_count = mongo.collection.count_documents({"type": "embedding"})

print(f"   Results collection: {results_count} documents")
print(f"   Documents collection: {docs_count} datasets")
print(f"   Embeddings in collection: {embedding_count}\n")

if results_count > 0:
    print("3️⃣  LATEST SAVED RESULTS (last 3):")
    latest = list(mongo.results_collection.find().sort("_id", -1).limit(3))
    for i, res in enumerate(latest, 1):
        print(f"\n   Result {i}:")
        print(f"   - Query: {res.get('query', 'N/A')[:60]}")
        print(f"   - File: {res.get('file_name', 'N/A')}")
        print(f"   - KPIs: {len(res.get('kpis', []))} items")
        print(f"   - Charts: {len(res.get('charts', []))} items")
        print(f"   - Answer length: {len(res.get('answer', ''))}")

print("\n4️⃣  MongoDB Connect Status:")
try:
    mongo.client.admin.command("ping")
    print("   ✅ Connected to MongoDB")
except Exception as e:
    print(f"   ❌ Connection failed: {e}")

print("\n5️⃣  Next Steps:")
print("   1. Run: python -m uvicorn main:app --reload")
print("   2. Upload CSV file")
print("   3. Ask a question")
print("   4. Look for 🔴 CHECKPOINTS in terminal")
print("   5. Run this script again to verify save")

print("\n" + "="*70 + "\n")
