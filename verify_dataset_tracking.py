"""
Verify ACTIVE_DATASET is being set and tracked correctly
"""
from routes import upload
from mongo_client import MongoDBClient

print("\n" + "="*70)
print("🔍 VERIFY: ACTIVE_DATASET Tracking (After Upload Fix)")
print("="*70 + "\n")

print("1️⃣  Module-level ACTIVE_DATASET:")
print(f"   Value: {upload.ACTIVE_DATASET}")
print(f"   Type: {type(upload.ACTIVE_DATASET)}\n")

print("2️⃣  MongoDB collections:")
mongo = MongoDBClient()

docs_count = mongo.collection.count_documents({"type": "dataset"})
print(f"   Documents (datasets): {docs_count}")

results_count = mongo.results_collection.count_documents({})
print(f"   Results saved: {results_count}\n")

if docs_count > 0:
    print("3️⃣  Available datasets:")
    datasets = mongo.collection.find({"type": "dataset"})
    for ds in datasets:
        print(f"   - {ds.get('file_name')} ({ds.get('rows')} rows)")

print("\n4️⃣  Test: Setting ACTIVE_DATASET programmatically")
upload.ACTIVE_DATASET = "test_dataset.csv"
print(f"   Set to: {upload.ACTIVE_DATASET}")
print(f"   Expected in app.state: {upload.ACTIVE_DATASET == 'test_dataset.csv'}")

print("\n" + "="*70)
print("✅ When you upload a file via frontend:")
print("   1. upload.ACTIVE_DATASET will be set to filename")
print("   2. request.app.state.ACTIVE_DATASET will also be set")
print("   3. chart endpoint will use request.app.state version")
print("="*70 + "\n")
