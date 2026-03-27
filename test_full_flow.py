"""
TEST: Simulate full flow - Upload → Query → Save
"""
from mongo_client import MongoDBClient
from routes import upload
import datetime

print("\n" + "="*70)
print("🧪 TEST: Simulating Full Flow")
print("="*70 + "\n")

mongo = MongoDBClient()

print("STEP 1: Simulate file upload")
print("   Setting active dataset in MongoDB...")

mongo.db["metadata"].update_one(
    {"_id": "active_dataset"},
    {"$set": {"value": "zoho_crm_sample_data.csv", "timestamp": datetime.datetime.utcnow()}},
    upsert=True
)

# Also set module global for this test
upload.ACTIVE_DATASET = "zoho_crm_sample_data.csv"

print(f"   ✅ Set to: zoho_crm_sample_data.csv\n")

print("STEP 2: Check if data is accessible")
doc = mongo.collection.find_one({
    "type": "dataset",
    "file_name": "zoho_crm_sample_data.csv"
})

if doc:
    print(f"   ✅ Found dataset with {doc.get('rows')} rows\n")
else:
    print(f"   ❌ Dataset not found\n")

print("STEP 3: Simulate saving a result")
test_result = {
    "file_name": "zoho_crm_sample_data.csv",
    "query": "what is the total deal value of amit",
    "answer": "Amit currently has a total deal value of 1,782,258...",
    "kpis": [{"title": "Total Deal Value for Amit", "value": 1782258}],
    "charts": [{"type": "pie", "data": [{"label": "Stage", "value": 10}]}]
}

result = mongo.save_result(test_result)
print(f"   Save returned: {result}\n")

print("STEP 4: Check if result was saved")
saved = mongo.results_collection.find_one({
    "file_name": "zoho_crm_sample_data.csv",
    "query": "what is the total deal value of amit"
})

if saved:
    print(f"   ✅ Result found in collection!")
    print(f"      File: {saved.get('file_name')}")
    print(f"      Query: {saved.get('query')}")
    print(f"      KPIs: {len(saved.get('kpis', []))}")
else:
    print(f"   ❌ Result NOT found\n")

print("\n" + "="*70)
print("✅ Test complete!")
print("="*70 + "\n")
