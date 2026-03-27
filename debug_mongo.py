"""
Quick debug script to verify MongoDB results collection
"""
from mongo_client import MongoDBClient
from pprint import pprint
import json

print("\n" + "="*60)
print("🔍 MONGODB DEBUG - RESULTS COLLECTION")
print("="*60 + "\n")

try:
    # Connect to MongoDB
    mongo = MongoDBClient()
    print("✅ Connected to MongoDB\n")
    
    # Count results
    count = mongo.results_collection.count_documents({})
    print(f"📊 Total results saved: {count}\n")
    
    if count == 0:
        print("⚠️  No results in collection yet. This is expected on first run.\n")
    else:
        print("📋 Latest 5 results:\n")
        results = list(mongo.results_collection.find().sort("_id", -1).limit(5))
        for i, result in enumerate(results, 1):
            print(f"{i}. Query: {result.get('query')}")
            print(f"   File: {result.get('file_name')}")
            print(f"   Answer length: {len(result.get('answer', ''))}")
            print(f"   KPIs: {len(result.get('kpis', []))} items")
            print(f"   Charts: {len(result.get('charts', []))} items")
            print(f"   Timestamp: {result.get('timestamp', 'N/A')}\n")
    
    # Check documents collection
    doc_count = mongo.collection.count_documents({})
    print(f"📚 Documents in collection: {doc_count}\n")
    
    if doc_count > 0:
        print("📋 Sample documents:\n")
        docs = list(mongo.collection.find().limit(2))
        for doc in docs:
            print(f"   File: {doc.get('file_name')}")
            print(f"   Type: {doc.get('type')}")
            print(f"   Data rows: {len(doc.get('data', []))}\n")
    
    print("="*60)
    print("✅ Debug complete")
    print("="*60 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
