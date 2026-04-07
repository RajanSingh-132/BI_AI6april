from mongo_client import MongoDBClient

mongo = MongoDBClient()

# total documents
count = mongo.collection.count_documents({})

print("Total documents:", count)

doc = mongo.collection.find_one()

print("\nSample document:\n")
print(doc)

# check embedding
if doc and "embedding" in doc:

    print("\nEmbedding length:", len(doc["embedding"]))

else:

    print("\n⚠ No embedding found in document")