from fastapi import APIRouter, HTTPException, Request
from datetime import datetime

from semanticstore import process_dataset
from embeddingclient import BedrockEmbeddingClient

router = APIRouter()

# Global tracker for active dataset
ACTIVE_DATASET = None

@router.post("/upload-json")
async def upload_json(request: Request):

    global ACTIVE_DATASET

    try:
        db = request.app.state.mongo.db
        mongo_client = request.app.state.mongo

        body = await request.json()

        file_name = body.get("file_name")
        data = body.get("data")

        if not file_name:
            raise HTTPException(status_code=400, detail="File name is required")

        if not data or not isinstance(data, list):
            raise HTTPException(status_code=400, detail="Invalid data format")

        # ✅ SAVE ACTIVE DATASET - EVERYWHERE
        ACTIVE_DATASET = file_name
        request.app.state.ACTIVE_DATASET = file_name
        
        # ✅ ALSO SAVE TO MONGODB AS METADATA
        db["metadata"].update_one(
            {"_id": "active_dataset"},
            {"$set": {"value": file_name, "timestamp": __import__('datetime').datetime.utcnow()}},
            upsert=True
        )
        
        print(f"\n{'='*70}")
        print(f"🎯 SET ACTIVE DATASET: {file_name}")
        print(f"   Module var: {ACTIVE_DATASET}")
        print(f"   App state: {request.app.state.ACTIVE_DATASET}")
        print(f"   MongoDB metadata: {file_name}")
        print(f"{'='*70}\n")

        cleaned_data = []
        for row in data:
            cleaned_row = {
                str(k).strip().lower().replace(" ", "_"): v
                for k, v in row.items() if k
            }
            cleaned_data.append(cleaned_row)

        columns = list(cleaned_data[0].keys()) if cleaned_data else []

        db["documents"].delete_many({"file_name": file_name})

        document = {
            "type": "dataset",
            "file_name": file_name,
            "columns": columns,
            "data": cleaned_data,
            "rows": len(cleaned_data),
            "uploaded_at": datetime.utcnow()
        }

        db["documents"].insert_one(document)

        embedding_client = BedrockEmbeddingClient()

        process_dataset(
            data=cleaned_data,
            file_name=file_name,
            embedding_client=embedding_client,
            mongo_client=mongo_client
        )

        return {
            "status": "success",
            "message": "File uploaded successfully ✅",
            "file_name": file_name,
            "rows": len(cleaned_data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))