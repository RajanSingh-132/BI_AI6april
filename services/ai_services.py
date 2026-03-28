import os
import json
import re
from dotenv import load_dotenv
from google import genai

from mongo_client import mongo_client
from utils.request_tracker import tracker
from rag_retriever import RAGRetriever
from prompt import SYSTEM_PROMPT
from routes import upload as upload_module

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY missing")

client = genai.Client(api_key=API_KEY)
tracker.gemini_hit()

retriever = RAGRetriever()


# ----------------------------
# FETCH DATA
# ----------------------------
def fetch_data(dataset):

    if not dataset:
        print("❌ FETCH_DATA: No dataset provided, returning empty")
        return []

    db = mongo_client.db
    collection = db["documents"]
    
    print(f"🔍 FETCH_DATA: Looking for dataset '{dataset}'")

    result = collection.find_one({
        "type": "dataset",
        "file_name": dataset
    })
    
    if result:
        data = result.get("data", [])
        print(f"✅ FETCH_DATA: Found dataset with {len(data)} rows")
        return data
    else:
        print(f"❌ FETCH_DATA: Dataset '{dataset}' not found in MongoDB")
        return []


# ----------------------------
# MAIN FUNCTION
# ----------------------------
def generate_ai_response(user_id: str, message: str, history=None, request=None, active_datasets=None, comparison_mode=False) -> dict:

    query = message.lower().strip()
    
    # ✅ GET ACTIVE DATASETS
    datasets = active_datasets or []
    
    if not datasets:
        # PRIMARY: Get datasets from MongoDB metadata (most reliable)
        try:
            metadata = mongo_client.db["metadata"].find_one({"_id": "active_datasets"})
            if metadata:
                datasets = metadata.get("value", [])
                print(f"📍 Got datasets from MongoDB metadata: {datasets}")
        except Exception as e:
            print(f"⚠️  Could not read from MongoDB metadata: {e}")
    
    if not datasets and request and hasattr(request.app.state, 'ACTIVE_DATASETS'):
        datasets = request.app.state.ACTIVE_DATASETS
        print(f"📍 Got datasets from app.state: {datasets}")
    
    if not datasets:
        datasets = upload_module.ACTIVE_DATASETS if hasattr(upload_module, 'ACTIVE_DATASETS') else []
        print(f"📍 Got datasets from module: {datasets}")
    
    # Use primary dataset if available, or first in list
    primary_dataset = datasets[0] if datasets else None
    
    print(f"ACTIVE DATASETS: {datasets}")
    print(f"PRIMARY DATASET: {primary_dataset}")
    print(f"COMPARISON MODE: {comparison_mode}")
    print(f"🎯 Processing query: {query[:60]}...")

    # ----------------------------
    # CACHE CHECK (single dataset only)
    # ----------------------------
    if primary_dataset and not comparison_mode:
        cached = mongo_client.get_cached_result(primary_dataset, query)

        if cached:
            print("✅ Returning cached result")
            return {
                "answer": cached["answer"],
                "kpis": cached["kpis"],
                "charts": cached["charts"]
            }

    # ----------------------------
    # FETCH DATA
    # ----------------------------
    dataset_configs = []
    
    for dataset_name in datasets:
        data = fetch_data(dataset_name)
        print(f"📊 Fetched {len(data)} data rows from dataset: {dataset_name}")
        if data:
            dataset_configs.append({
                "name": dataset_name,
                "data": data
            })
    
    if not dataset_configs:
        print("⚠️  No datasets available - falling back to RAG")
    else:
        print(f"✅ Loaded {len(dataset_configs)} dataset(s)")

    if dataset_configs:

        print("\n" + "✅"*25)
        print(f"MAIN PATH: Using {len(dataset_configs)} dataset(s)")
        for config in dataset_configs:
            print(f"   - {config['name']}: {len(config['data'])} rows")
        print("✅"*25 + "\n")

        # Build dataset context
        dataset_context = ""
        for config in dataset_configs:
            dataset_json = json.dumps(config['data'][:50], indent=2)
            dataset_context += f"\n\nDataset: {config['name']}\n{dataset_json}"

        # Add comparison instructions if needed
        comparison_instruction = ""
        if comparison_mode and len(dataset_configs) > 1:
            comparison_instruction = f"""

COMPARISON MODE ENABLED:
- You have access to {len(dataset_configs)} datasets: {', '.join([c['name'] for c in dataset_configs])}
- Compare metrics across these datasets
- Highlight differences and patterns
- Specify which dataset each result comes from
- Format: "[Dataset: {dataset_name}] Metric: Value"
"""

        prompt = f"""
{SYSTEM_PROMPT}
{comparison_instruction}

Datasets:
{dataset_context}

User Query:
{message}
"""

User Query:
{message}
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            raw_text = response.text if hasattr(response, "text") else str(response)

            # ----------------------------
            # 🔥 CLEAN RAW TEXT
            # ----------------------------
            raw_text = raw_text.replace("```json", "")
            raw_text = raw_text.replace("```", "")
            raw_text = raw_text.replace("\\n", " ")
            raw_text = raw_text.replace("\n", " ")
            raw_text = raw_text.replace("Answer:", "")
            raw_text = raw_text.strip()

            print("RAW CLEANED:", raw_text)

            # ----------------------------
            # 🔥 EXTRACT FULL JSON
            # ----------------------------
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1

            if start == -1 or end == -1:
                print("❌ JSON not found")
                return {
                    "answer": "Invalid AI response format",
                    "kpis": [],
                    "charts": []
                }

            json_str = raw_text[start:end]

            try:
                parsed = json.loads(json_str)
            except Exception as e:
                print("❌ JSON Parse Error:", e)
                return {
                    "answer": "Error parsing AI response",
                    "kpis": [],
                    "charts": []
                }

            # ----------------------------
            # 🔥 CLEAN FINAL OUTPUT
            # ----------------------------
            answer = parsed.get("answer", "").strip()

            answer = answer.replace("\\n", " ")
            answer = answer.replace("\n", " ")
            answer = answer.replace("Answer:", "")
            answer = re.sub(r"\s+", " ", answer).strip()

            final_kpis = parsed.get("kpis", [])
            final_charts = parsed.get("charts", [])

            print("FINAL ANSWER:", answer)

            # ----------------------------
            # 🔥 SAVE RESULT
            # ----------------------------
            print("\n" + "🔴"*25)
            print("SAVE CHECKPOINT 1: Checking if answer exists")
            print(f"   Answer exists: {bool(answer)}")
            print(f"   Answer length: {len(answer) if answer else 0}")
            
            if answer:
                print("\n🔴 SAVE CHECKPOINT 2: Inside save block")
                print(f"   Primary Dataset: {primary_dataset}")
                print(f"   All Datasets: {[c['name'] for c in dataset_configs]}")
                print(f"   Query: {query}")
                print(f"   Final KPIs: {final_kpis}")
                print(f"   Final Charts: {final_charts}")
                
                # Save using primary dataset for caching (single or multi-dataset)
                if primary_dataset:
                    save_data = {
                        "file_name": primary_dataset,
                        "query": query,
                        "answer": answer,
                        "kpis": final_kpis,
                        "charts": final_charts,
                        "datasets": [c['name'] for c in dataset_configs],  # Track all datasets used
                        "comparison_mode": comparison_mode
                    }
                    
                    print(f"\n🔴 SAVE CHECKPOINT 3: Calling mongo_client.save_result()")
                    print(f"   Data to save: {save_data}")
                    
                    result = mongo_client.save_result(save_data)
                    
                    print(f"\n🔴 SAVE CHECKPOINT 4: Save result returned: {result}")
                    
                    if result:
                        print("✅ SAVE SUCCESSFUL")
                    else:
                        print("❌ SAVE FAILED - result was False")
            else:
                print("\n🔴 SAVE CHECKPOINT 1 FAILED: No answer to save")
                
            print("🔴"*25 + "\n")

            return {
                "answer": answer,
                "kpis": final_kpis,
                "charts": final_charts,
                "datasets_used": [c['name'] for c in dataset_configs],
                "comparison_mode": comparison_mode
            }

        except Exception as e:
            print("❌ AI Error:", str(e))

            return {
                "answer": "AI service unavailable",
                "kpis": [],
                "charts": [],
                "datasets_used": [],
                "comparison_mode": False
            }

    # ----------------------------
    # FALLBACK (RAG)
    # ----------------------------
    print("🔄 Using RAG fallback (no dataset)")
    docs = retriever.get_relevant_documents(message)
    context = "\n\n".join(doc.page_content for doc in docs)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\n\n{context}\n\n{message}"
        )

        raw_text = response.text if hasattr(response, "text") else str(response)
        
        print("💾 RAG Fallback: NOT saving to DB (no dataset)")

        return {
            "answer": raw_text.strip(),
            "kpis": [],
            "charts": [],
            "datasets_used": [],
            "comparison_mode": False
        }

    except Exception as e:
        print("❌ AI Error:", str(e))

        return {
            "answer": "AI service unavailable",
            "kpis": [],
            "charts": [],
            "datasets_used": [],
            "comparison_mode": False
        }