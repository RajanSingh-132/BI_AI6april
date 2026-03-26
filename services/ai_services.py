import os
import json
import re
from dotenv import load_dotenv
from google import genai

from mongo_client import mongo_client
from utils.request_tracker import tracker
from rag_retriever import RAGRetriever
from prompt import SYSTEM_PROMPT
from routes.upload import ACTIVE_DATASET

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
        return []

    db = mongo_client.db
    collection = db["documents"]

    result = collection.find_one({
        "type": "dataset",
        "file_name": dataset
    })

    return result.get("data", []) if result else []


# ----------------------------
# MAIN FUNCTION
# ----------------------------
def generate_ai_response(user_id: str, message: str, history=None) -> dict:

    query = message.lower().strip()
    dataset = ACTIVE_DATASET

    print("ACTIVE DATASET:", dataset)

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
    print("DATA LENGTH:", len(data))

    if dataset and data:

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
            if answer:
                print("🔥 SAVING TO DB:", query)

                mongo_client.save_result({
                    "file_name": dataset,
                    "query": query,
                    "answer": answer,
                    "kpis": final_kpis,
                    "charts": final_charts
                })

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
    docs = retriever.get_relevant_documents(message)
    context = "\n\n".join(doc.page_content for doc in docs)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\n\n{context}\n\n{message}"
        )

        raw_text = response.text if hasattr(response, "text") else str(response)

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