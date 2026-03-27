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
def generate_ai_response(user_id: str, message: str, history=None, request=None) -> dict:

    query = message.lower().strip()
    
    # ✅ PRIMARY: Get dataset from MongoDB metadata (most reliable)
    dataset = None
    try:
        metadata = mongo_client.db["metadata"].find_one({"_id": "active_dataset"})
        if metadata:
            dataset = metadata.get("value")
            print(f"📍 Got dataset from MongoDB metadata: {dataset}")
    except Exception as e:
        print(f"⚠️  Could not read from MongoDB metadata: {e}")
    
    # ✅ FALLBACK 1: Get from app state
    if not dataset and request and hasattr(request.app.state, 'ACTIVE_DATASET'):
        dataset = request.app.state.ACTIVE_DATASET
        print(f"📍 Got dataset from app.state: {dataset}")
    
    # ✅ FALLBACK 2: Get from module global
    if not dataset:
        dataset = upload_module.ACTIVE_DATASET
        print(f"📍 Got dataset from module: {dataset}")

    print("ACTIVE DATASET:", dataset)
    print(f"🎯 Processing query: {query[:60]}...")

    # ----------------------------
    # CACHE CHECK
    # ----------------------------
    if dataset:
        cached = mongo_client.get_cached_result(dataset, query)

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
    data = fetch_data(dataset)
    print(f"📊 Fetched {len(data)} data rows from dataset")
    
    if not dataset:
        print("⚠️  No active dataset - falling back to RAG")
    elif not data:
        print(f"⚠️  Dataset '{dataset}' has no data - falling back to RAG")

    if dataset and data:

        print("\n" + "✅"*25)
        print(f"MAIN PATH: Using dataset '{dataset}' with {len(data)} rows")
        print("✅"*25 + "\n")

        dataset_json = json.dumps(data[:50], indent=2)

        prompt = f"""
{SYSTEM_PROMPT}

Dataset:
{dataset_json}

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
                print(f"   Dataset: {dataset}")
                print(f"   Query: {query}")
                print(f"   Final KPIs: {final_kpis}")
                print(f"   Final Charts: {final_charts}")
                
                save_data = {
                    "file_name": dataset,
                    "query": query,
                    "answer": answer,
                    "kpis": final_kpis,
                    "charts": final_charts
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
                "charts": final_charts
            }

        except Exception as e:
            print("❌ AI Error:", str(e))

            return {
                "answer": "AI service unavailable",
                "kpis": [],
                "charts": []
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
            "charts": []
        }

    except Exception as e:
        print("❌ AI Error:", str(e))

        return {
            "answer": "AI service unavailable",
            "kpis": [],
            "charts": []
        }