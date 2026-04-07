from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from typing import List
import logging

from semanticstore import process_dataset

logger = logging.getLogger(__name__)

# Try to import BedrockEmbeddingClient, but don't fail if it's not available
try:
    from embeddingclient import BedrockEmbeddingClient
    BEDROCK_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    BEDROCK_AVAILABLE = False
    BedrockEmbeddingClient = None
    print(f"[WARN] BedrockEmbeddingClient not available: {e}")

from data_relationships import relationship_manager

router = APIRouter()

# Global tracker for active datasets (now supports multiple)
ACTIVE_DATASET = None
ACTIVE_DATASETS = []  # List of all active datasets


def _set_active_datasets(request: Request, db, datasets: List[str]):
    """
    Replace the active working set with the current upload selection.
    Stored datasets remain in MongoDB, but chat defaults to only this batch.
    """
    global ACTIVE_DATASET, ACTIVE_DATASETS

    deduped = []
    for dataset_name in datasets:
        if dataset_name and dataset_name not in deduped:
            deduped.append(dataset_name)

    ACTIVE_DATASETS = deduped
    ACTIVE_DATASET = ACTIVE_DATASETS[-1] if ACTIVE_DATASETS else None

    request.app.state.ACTIVE_DATASET = ACTIVE_DATASET
    request.app.state.ACTIVE_DATASETS = ACTIVE_DATASETS

    timestamp = datetime.utcnow()

    db["metadata"].update_one(
        {"_id": "active_dataset"},
        {"$set": {"value": ACTIVE_DATASET, "timestamp": timestamp}},
        upsert=True
    )

    db["metadata"].update_one(
        {"_id": "active_datasets"},
        {"$set": {"value": ACTIVE_DATASETS, "timestamp": timestamp}},
        upsert=True
    )

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

            _set_active_datasets(request, db, [file_name])
            
            return {
                "status": "success",
                "message": "LOOKS LIKE YOU ALREADY HAVE THIS DATASET UPLOADED AND WE HAVE FETCHED IT FOR YOU IN THIS CHAT! ✅",
                "file_name": file_name,
                "rows": existing_doc.get("rows", 0),
                "active_datasets": ACTIVE_DATASETS,
                "from_cache": True
            }

        # ✅ SET ACTIVE DATASET - EVERYWHERE
        _set_active_datasets(request, db, [file_name])
        
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

        # Only process embeddings if available
        if BEDROCK_AVAILABLE and BedrockEmbeddingClient:
            try:
                embedding_client = BedrockEmbeddingClient()
                process_dataset(
                    data=cleaned_data,
                    file_name=file_name,
                    embedding_client=embedding_client,
                    mongo_client=mongo_client
                )
            except Exception as e:
                print(f"[WARN] Embedding processing failed: {e}")
                # Continue anyway - upload still succeeds
        else:
            print(f"[INFO] Bedrock embeddings not available, skipping semantic processing")

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
        active_batch = []
        
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
                if file_name not in active_batch:
                    active_batch.append(file_name)
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
            
            if file_name not in active_batch:
                active_batch.append(file_name)
            
            # Only process embeddings if available
            if BEDROCK_AVAILABLE and BedrockEmbeddingClient:
                try:
                    embedding_client = BedrockEmbeddingClient()
                    process_dataset(
                        data=cleaned_data,
                        file_name=file_name,
                        embedding_client=embedding_client,
                        mongo_client=mongo_client
                    )
                except Exception as e:
                    logger.warning(f"[WARN] Embedding processing failed for {file_name}: {e}")
                    # Continue anyway - upload still succeeds
            else:
                logger.info(f"[INFO] Bedrock embeddings not available, skipping semantic processing")
            
            results.append({
                "file_name": file_name,
                "status": "success",
                "message": "File uploaded successfully",
                "rows": len(cleaned_data),
                "from_cache": False
            })
        
        # Update global state for this upload batch only
        _set_active_datasets(request, db, active_batch)
        
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
