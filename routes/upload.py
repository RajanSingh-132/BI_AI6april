from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from typing import List

from semanticstore import process_dataset
from embeddingclient import BedrockEmbeddingClient
from data_relationships import relationship_manager

router = APIRouter()

# Global tracker for active datasets (now supports multiple)
ACTIVE_DATASET = None
ACTIVE_DATASETS = []  # List of all active datasets

@router.post("/upload-json")
async def upload_json(request: Request):

    global ACTIVE_DATASET, ACTIVE_DATASETS

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

        # ✅ CHECK FOR DUPLICATE DATASET
        existing_doc = db["documents"].find_one({
            "type": "dataset",
            "file_name": file_name
        })
        
        if existing_doc:
            print(f"\n{'='*70}")
            print(f"⚠️  DATASET ALREADY EXISTS: {file_name}")
            print(f"   Skipping re-embedding and returning existing dataset")
            print(f"{'='*70}\n")
            
            # Add to active datasets list
            if file_name not in ACTIVE_DATASETS:
                ACTIVE_DATASETS.append(file_name)
            
            ACTIVE_DATASET = file_name
            request.app.state.ACTIVE_DATASET = file_name
            request.app.state.ACTIVE_DATASETS = ACTIVE_DATASETS
            
            return {
                "status": "success",
                "message": "LOOKS LIKE YOU ALREADY HAVE THIS DATASET UPLOADED AND WE HAVE FETCHED IT FOR YOU IN THIS CHAT! ✅",
                "file_name": file_name,
                "rows": existing_doc.get("rows", 0),
                "from_cache": True
            }

        # ✅ SET ACTIVE DATASET - EVERYWHERE
        ACTIVE_DATASET = file_name
        if file_name not in ACTIVE_DATASETS:
            ACTIVE_DATASETS.append(file_name)
            
        request.app.state.ACTIVE_DATASET = file_name
        request.app.state.ACTIVE_DATASETS = ACTIVE_DATASETS
        
        # ✅ ALSO SAVE TO MONGODB AS METADATA
        db["metadata"].update_one(
            {"_id": "active_dataset"},
            {"$set": {"value": file_name, "timestamp": __import__('datetime').datetime.utcnow()}},
            upsert=True
        )
        
        db["metadata"].update_one(
            {"_id": "active_datasets"},
            {"$set": {"value": ACTIVE_DATASETS, "timestamp": __import__('datetime').datetime.utcnow()}},
            upsert=True
        )
        
        print(f"\n{'='*70}")
        print(f"🎯 SET ACTIVE DATASET: {file_name}")
        print(f"   Module var: {ACTIVE_DATASET}")
        print(f"   Active Datasets List: {ACTIVE_DATASETS}")
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

        # ✅ DO NOT DELETE - for multiple datasets, we preserve existing data
        # db["documents"].delete_many({"file_name": file_name})

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
            "rows": len(cleaned_data),
            "active_datasets": ACTIVE_DATASETS,
            "from_cache": False
        }

    except Exception as e:
        raise HTTPException(status_code=5000, detail=str(e))


@router.post("/upload-multiple-json")
async def upload_multiple_json(request: Request):
    """Handle multiple file uploads in one request"""
    
    global ACTIVE_DATASET, ACTIVE_DATASETS

    try:
        db = request.app.state.mongo.db
        mongo_client = request.app.state.mongo

        body = await request.json()
        files = body.get("files", [])
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        results = []
        
        for file_data in files:
            file_name = file_data.get("file_name")
            data = file_data.get("data")
            
            if not file_name or not data:
                results.append({
                    "file_name": file_name or "unknown",
                    "status": "error",
                    "message": "Missing file_name or data"
                })
                continue
            
            # Check for duplicate
            existing_doc = db["documents"].find_one({
                "type": "dataset",
                "file_name": file_name
            })
            
            if existing_doc:
                if file_name not in ACTIVE_DATASETS:
                    ACTIVE_DATASETS.append(file_name)
                results.append({
                    "file_name": file_name,
                    "status": "success",
                    "message": "Dataset already exists - fetched from cache",
                    "rows": existing_doc.get("rows", 0),
                    "from_cache": True
                })
                continue
            
            # Process new file
            cleaned_data = []
            for row in data:
                cleaned_row = {
                    str(k).strip().lower().replace(" ", "_"): v
                    for k, v in row.items() if k
                }
                cleaned_data.append(cleaned_row)

            columns = list(cleaned_data[0].keys()) if cleaned_data else []
            
            document = {
                "type": "dataset",
                "file_name": file_name,
                "columns": columns,
                "data": cleaned_data,
                "rows": len(cleaned_data),
                "uploaded_at": datetime.utcnow()
            }
            
            db["documents"].insert_one(document)
            
            if file_name not in ACTIVE_DATASETS:
                ACTIVE_DATASETS.append(file_name)
            
            embedding_client = BedrockEmbeddingClient()
            process_dataset(
                data=cleaned_data,
                file_name=file_name,
                embedding_client=embedding_client,
                mongo_client=mongo_client
            )
            
            results.append({
                "file_name": file_name,
                "status": "success",
                "message": "File uploaded successfully",
                "rows": len(cleaned_data),
                "from_cache": False
            })
        
        # Update global state
        ACTIVE_DATASET = ACTIVE_DATASETS[-1] if ACTIVE_DATASETS else None
        request.app.state.ACTIVE_DATASETS = ACTIVE_DATASETS
        request.app.state.ACTIVE_DATASET = ACTIVE_DATASET
        
        # Save to MongoDB
        if ACTIVE_DATASETS:
            db["metadata"].update_one(
                {"_id": "active_datasets"},
                {"$set": {"value": ACTIVE_DATASETS, "timestamp": __import__('datetime').datetime.utcnow()}},
                upsert=True
            )
        
        print(f"\n{'='*70}")
        print(f"✅ MULTIPLE FILES PROCESSED")
        print(f"   Total datasets: {len(ACTIVE_DATASETS)}")
        print(f"   Active datasets: {ACTIVE_DATASETS}")
        
        # 🔥 BUILD RELATIONSHIP GRAPH FOR MULTI-FILE ANALYSIS
        if len(ACTIVE_DATASETS) > 1:
            print(f"\n🔗 DISCOVERING RELATIONSHIPS BETWEEN FILES...")
            relationships = relationship_manager.build_relationship_graph(ACTIVE_DATASETS)
            print(f"   Shared columns: {relationships.get('shared_columns', {})}")
            print(f"   Relationship graph built successfully!")
        
        print(f"{'='*70}\n")
        
        return {
            "status": "success",
            "message": "Multiple files processed successfully ✅",
            "results": results,
            "active_datasets": ACTIVE_DATASETS,
            "relationships": relationship_manager.get_relationships() if len(ACTIVE_DATASETS) > 1 else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))