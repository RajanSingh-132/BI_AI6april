from mongo_client import MongoDBClient


def test_collections():

    try:
        # ✅ Connect to MongoDB
        mongo = MongoDBClient()
        db = mongo.db

        print("✅ Connected to DB")

        # 🔥 Get all collections
        collections = db.list_collection_names()

        print("\n📂 Collections in DB:")
        for col in collections:
            print(f"- {col}")

        # 🔢 Count
        print("\n🔢 Total Collections:", len(collections))

        # 🔍 Check specific collections
        print("\n🔍 Checking required collections:")

        required = ["documents", "results"]

        for col in required:
            if col in collections:
                print(f"✅ {col} exists")
            else:
                print(f"❌ {col} NOT found")

    except Exception as e:
        print("❌ Error:", str(e))


# 🚀 Run test
if __name__ == "__main__":
    test_collections()