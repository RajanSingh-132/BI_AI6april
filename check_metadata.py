"""
UPDATED DIAGNOSTIC: Check MongoDB metadata for active dataset
"""
from mongo_client import MongoDBClient
from routes import upload
import json

print("\n" + "="*70)
print("🔍 DIAGNOSTIC - MongoDB Metadata Check")
print("="*70 + "\n")

mongo = MongoDBClient()

print("1️⃣  ACTIVE_DATASET Status:")
print(f"   Module value: {upload.ACTIVE_DATASET}")

print("\n2️⃣  MongoDB Metadata (SOURCE OF TRUTH):")
try:
    metadata = mongo.db["metadata"].find_one({"_id": "active_dataset"})
    if metadata:
        print(f"   ✅ Found in metadata: {metadata.get('value')}")
        print(f"   Timestamp: {metadata.get('timestamp')}")
    else:
        print(f"   ❌ Not found in metadata (will be set on upload)")
except Exception as e:
    print(f"   ❌ Error reading metadata: {e}")

print("\n3️⃣  Available Datasets in MongoDB:")
datasets = list(mongo.collection.find({"type": "dataset"}))
for ds in datasets:
    print(f"   - {ds.get('file_name')} ({ds.get('rows')} rows)")

print("\n4️⃣  Results Collection Status:")
results_count = mongo.results_collection.count_documents({})
print(f"   Total saved: {results_count}")

results_by_file = {}
for result in mongo.results_collection.find():
    file_name = result.get('file_name', 'unknown')
    if file_name not in results_by_file:
        results_by_file[file_name] = 0
    results_by_file[file_name] += 1

print("\n   Breakdown by file_name:")
for file_name, count in results_by_file.items():
    print(f"      {file_name}: {count} results")

print("\n5️⃣  Latest Result:")
latest = mongo.results_collection.find_one(sort=[("_id", -1)])
if latest:
    print(f"   Query: {latest.get('query')}")
    print(f"   File: {latest.get('file_name')}")
    print(f"   KPIs: {len(latest.get('kpis', []))}")
    print(f"   Charts: {len(latest.get('charts', []))}")

print("\n" + "="*70)
print("📌 FLOW:")
print("   1. Upload → Sets MongoDB metadata['active_dataset']")
print("   2. Query → Reads MongoDB metadata (primary source)")
print("   3. Save → Saves with correct file_name")
print("="*70 + "\n")
