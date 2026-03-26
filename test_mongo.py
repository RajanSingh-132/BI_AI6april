from database.mongo import documents_collection

count = documents_collection.count_documents({})

print("Total documents:", count)

doc = documents_collection.find_one()

print("\nSample document:\n")
print(doc)

if doc and "embedding" in doc:
    print("\nEmbedding length:", len(doc["embedding"]))
else:
    print("\n⚠ No embedding found")