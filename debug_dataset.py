"""
Debug script to verify ACTIVE_DATASET is working
"""
from routes import upload
from mongo_client import MongoDBClient

print("\n" + "="*60)
print("🔍 DEBUG: ACTIVE_DATASET Tracking")
print("="*60 + "\n")

# Check current ACTIVE_DATASET
print(f"Current ACTIVE_DATASET: {upload.ACTIVE_DATASET}")

# Check MongoDB for documents
mongo = MongoDBClient()
docs = list(mongo.collection.find({"type": "dataset"}))

print(f"\n📚 Datasets in MongoDB: {len(docs)}")
for doc in docs:
    print(f"   - {doc.get('file_name')} ({doc.get('rows')} rows)")

# Simulate what happens when we query
print("\n" + "="*60)
print("Simulating: Accessing upload.ACTIVE_DATASET from ai_services")
print("="*60)

# This mimics how ai_services.py will access it
dataset = upload.ACTIVE_DATASET
print(f"Got dataset: {dataset}")
print(f"Type: {type(dataset)}")

# If a dataset is set, try to fetch it
if dataset:
    db_docs = list(mongo.collection.find({"type": "dataset", "file_name": dataset}))
    if db_docs:
        print(f"✅ Found dataset in DB: {db_docs[0].get('rows')} rows")
    else:
        print(f"❌ Dataset '{dataset}' not found in DB")
else:
    print("❌ No ACTIVE_DATASET set - will fall back to RAG")

print("\n" + "="*60 + "\n")
