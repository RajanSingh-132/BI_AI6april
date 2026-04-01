import os
import json
import re
import html
from dotenv import load_dotenv
from google import genai

from mongo_client import mongo_client
from utils.request_tracker import tracker
from rag_retriever import RAGRetriever
from prompt import SYSTEM_PROMPT
from routes import upload as upload_module
from multi_file_queries import multi_file_processor
from data_relationships import relationship_manager

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY missing")

client = genai.Client(api_key=API_KEY)
tracker.gemini_hit()

retriever = RAGRetriever()


# ----------------------------
# KPI VALUE FORMATTERS
# ----------------------------
def format_indian_number(value):
    """
    Format numeric values using Indian digit grouping.
    Examples: 876366 -> 8,76,366 and 541565.4 -> 5,41,565.4
    """
    if value is None:
        return value

    value_str = str(value).strip()
    if not value_str:
        return value

    sign = ""
    if value_str.startswith("-"):
        sign = "-"
        value_str = value_str[1:]

    value_str = value_str.replace(",", "")

    if not re.fullmatch(r"\d+(?:\.\d+)?", value_str):
        return value

    integer_part, dot, fractional_part = value_str.partition(".")

    if len(integer_part) <= 3:
        formatted_integer = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_integer = ",".join(groups + [last_three])

    return f"{sign}{formatted_integer}{dot}{fractional_part}" if dot else f"{sign}{formatted_integer}"


def format_rupee_kpi_value(kpi):
    """
    Apply Indian number formatting only to rupee KPI values.
    """
    if not isinstance(kpi, dict):
        return kpi

    formatted_kpi = kpi.copy()
    if formatted_kpi.get("unit") == "₹":
        formatted_kpi["value"] = format_indian_number(formatted_kpi.get("value"))

    return formatted_kpi


def format_answer_html(answer: str) -> str:
    """
    Normalize model output into lightweight HTML blocks.
    """
    if not answer:
        return ""

    answer = answer.replace("\r\n", "\n").replace("\r", "\n").strip()

    if re.search(r"</?(p|ul|li|strong|em|table|thead|tbody|tr|td|th|div|br)\b", answer, re.IGNORECASE):
        return answer

    lines = [line.strip() for line in answer.split("\n") if line.strip()]
    if not lines:
        return ""

    parts = []
    in_list = False

    for line in lines:
        if line.startswith(("- ", "* ")) or re.match(r"^\d+\.\s+", line):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            item = re.sub(r"^(- |\* |\d+\.\s+)", "", line)
            parts.append(f"<li>{html.escape(item)}</li>")
            continue

        if in_list:
            parts.append("</ul>")
            in_list = False

        parts.append(f"<p>{html.escape(line)}</p>")

    if in_list:
        parts.append("</ul>")

    return "".join(parts)


def _strip_inline_html(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"</?(strong|b|em|i|code|span)[^>]*>", "", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html.unescape(fragment)
    fragment = fragment.replace("\t", " ")
    fragment = re.sub(r"\s+", " ", fragment)
    return fragment.strip()


def _table_html_to_text(match) -> str:
    table_html = match.group(0)
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL)
    parsed_rows = []

    for row_html in rows:
        cells = re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", row_html, flags=re.IGNORECASE | re.DOTALL)
        cleaned_cells = [_strip_inline_html(cell) for cell in cells]
        if cleaned_cells:
            parsed_rows.append(cleaned_cells)

    if not parsed_rows:
        return ""

    header = parsed_rows[0]
    body = parsed_rows[1:]
    lines = []

    for row in body:
        if row and row[0].strip().upper() == "TOTAL":
            total_value = next((cell for cell in reversed(row) if cell and cell.strip().upper() != "TOTAL"), "")
            lines.append(f"TOTAL: {total_value}" if total_value else "TOTAL")
            continue

        pieces = []
        for idx, cell in enumerate(row):
            if not cell:
                continue
            label = header[idx] if idx < len(header) and header[idx] else f"col_{idx + 1}"
            pieces.append(f"{label}: {cell}")
        if pieces:
            lines.append(f"- {' | '.join(pieces)}")

    return "\n".join(lines) + "\n"


def html_to_display_text(answer_html: str) -> str:
    """
    Convert HTML-heavy answers into plain text for frontends that
    display tags literally.
    """
    if not answer_html:
        return ""

    text = answer_html
    text = re.sub(r"<p>\s*<strong>\s*</strong>\s*</p>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<table\b[^>]*>.*?</table>", _table_html_to_text, text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<li\b[^>]*>", "\n- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(ul|ol|div|thead|tbody|tr)\b[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(strong|b|em|i|code|span)\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\t", " ")
    text = re.sub(r"[ \u00A0]{2,}", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_plain_text_response(raw_answer: str, is_multi_file: bool = False, multi_file_context=None) -> dict:
    """
    Gracefully handle valid model replies that are not wrapped in JSON.
    """
    cleaned_answer = raw_answer.replace("\\n", "\n").replace("Answer:", "").strip()
    answer_html = format_answer_html(cleaned_answer)
    return {
        "answer": html_to_display_text(answer_html),
        "answer_html": answer_html,
        "kpis": [],
        "charts": [],
        "datasets_used": [],
        "comparison_mode": False,
        "ai_intelligence_analysis": [],
        "is_multi_file_analysis": is_multi_file,
        "multi_file_context": multi_file_context
    }


def load_model_json(json_str: str):
    """
    Parse model JSON defensively because the model sometimes returns
    raw control characters inside string values.
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as first_error:
        try:
            parsed = json.loads(json_str, strict=False)
            print("[warn] JSON parsed with strict=False fallback")
            return parsed
        except json.JSONDecodeError:
            sanitized_json = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", " ", json_str)
            if sanitized_json != json_str:
                parsed = json.loads(sanitized_json, strict=False)
                print("[warn] JSON parsed after control-character cleanup")
                return parsed
            raise first_error


def extract_json_objects(text: str):
    """
    Extract balanced top-level JSON object strings from mixed model output.
    """
    objects = []
    start = None
    depth = 0
    in_string = False
    escape = False

    for idx, ch in enumerate(text):
        if start is None:
            if ch == "{":
                start = idx
                depth = 1
                in_string = False
                escape = False
            continue

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                objects.append(text[start:idx + 1])
                start = None

    return objects


def extract_response_payload(raw_text: str):
    """
    Pick the final API payload from model output that may contain
    multiple JSON objects plus commentary.
    """
    parsed_candidates = []

    for candidate in extract_json_objects(raw_text):
        try:
            parsed = load_model_json(candidate)
        except Exception:
            continue

        if isinstance(parsed, dict):
            parsed_candidates.append(parsed)

    for parsed in reversed(parsed_candidates):
        if {"answer", "kpis", "charts"}.issubset(parsed.keys()):
            return parsed

    for parsed in reversed(parsed_candidates):
        if any(key in parsed for key in ("answer", "kpis", "charts")):
            return parsed

    return None


def format_rupee_kpi_value(kpi):
    """
    Apply Indian number formatting only to rupee KPI values.
    This late definition intentionally overrides the earlier helper
    so runtime behavior is consistent even if the source file had
    encoding noise around the rupee symbol.
    """
    if not isinstance(kpi, dict):
        return kpi

    formatted_kpi = kpi.copy()
    unit = str(formatted_kpi.get("unit", ""))
    if unit in {"\u20b9", "â‚¹"}:
        formatted_kpi["value"] = format_indian_number(formatted_kpi.get("value"))

    return formatted_kpi


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
    # 🔥 DETECT MULTI-FILE QUERIES
    # ----------------------------
    is_multi_file = multi_file_processor.is_multi_file_query(query, datasets or [])
    multi_file_context = None
    
    if is_multi_file and len(datasets) > 1:
        print("\n" + "🔗"*25)
        print("🔗 MULTI-FILE QUERY DETECTED")
        
        # Get relationship metadata
        relationships = relationship_manager.get_relationships()
        
        # Identify relevant datasets for this query
        relevant_datasets = multi_file_processor.identify_relevant_datasets(
            query, datasets, relationships
        )
        print(f"   Relevant datasets: {relevant_datasets}")
        
        # Build analysis context
        fetched_data_for_context = {
            dname: fetch_data(dname) for dname in relevant_datasets
        }
        
        multi_file_context = multi_file_processor.build_analysis_context(
            query, relevant_datasets, relationships, fetched_data_for_context
        )
        
        print(f"   Query type: {multi_file_context.get('query_type')}")
        print(f"   Shared columns: {multi_file_context.get('shared_columns')}")
        print("🔗"*25 + "\n")
    
    # ----------------------------
    # CACHE CHECK (single dataset only)
    # ----------------------------
    if primary_dataset and not comparison_mode and not is_multi_file:
        cached = mongo_client.get_cached_result(primary_dataset, query)

        if cached:
            print("✅ Returning cached result")
            cached_answer_html = cached.get("answer_html")
            if not cached_answer_html:
                cached_answer_html = format_answer_html(cached.get("answer", ""))
            return {
                "answer": html_to_display_text(cached_answer_html),
                "answer_html": cached_answer_html,
                "kpis": [format_rupee_kpi_value(kpi) for kpi in cached.get("kpis", [])],
                "charts": cached["charts"],
                "ai_intelligence_analysis": cached.get("ai_intelligence_analysis", []),  # 🎯 Include cached insights
                "comparison_mode": cached.get("comparison_mode", False),
                "datasets_used": cached.get("datasets", [])
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
            dataset_json = json.dumps(config['data'][:500], indent=2)
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
        
        # 🔥 ADD MULTI-FILE CONTEXT IF APPLICABLE
        multi_file_instruction = ""
        if is_multi_file and multi_file_context:
            multi_file_instruction = multi_file_processor.generate_multi_file_prompt_extension(
                multi_file_context
            )

        prompt = f"""
{SYSTEM_PROMPT}
{comparison_instruction}
{multi_file_instruction}

Datasets:
{dataset_context}

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
            raw_text = raw_text.strip()

            raw_preview = raw_text[:800].replace("\n", "\\n")
            if len(raw_text) > 800:
                raw_preview += "..."
            print("RAW CLEANED PREVIEW:", raw_preview)

            if "{" not in raw_text or "}" not in raw_text:
                return build_plain_text_response(
                    raw_text,
                    is_multi_file=is_multi_file,
                    multi_file_context=multi_file_context
                )

            preferred_payload = extract_response_payload(raw_text)
            if preferred_payload is not None:
                raw_text = json.dumps(preferred_payload)

            # ----------------------------
            # 🔥 EXTRACT FULL JSON
            # ----------------------------
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1

            if start == -1 or end == -1:
                return build_plain_text_response(
                    raw_text,
                    is_multi_file=is_multi_file,
                    multi_file_context=multi_file_context
                )
                print("❌ JSON not found")
                return {
                    "answer": "Invalid AI response format",
                    "kpis": [],
                    "charts": [],
                    "is_multi_file_analysis": is_multi_file,
                    "multi_file_context": multi_file_context
                }

            json_str = raw_text[start:end]

            try:
                parsed = load_model_json(json_str)
            except Exception as e:
                return build_plain_text_response(
                    raw_text,
                    is_multi_file=is_multi_file,
                    multi_file_context=multi_file_context
                )
                print("❌ JSON Parse Error:", e)
                return {
                    "answer": "Error parsing AI response",
                    "kpis": [],
                    "charts": [],
                    "is_multi_file_analysis": is_multi_file,
                    "multi_file_context": multi_file_context
                }

            # ----------------------------
            # 🔥 PREPARE FINAL OUTPUT (PRESERVE HTML FOR FRONTEND)
            # ----------------------------
            answer = parsed.get("answer", "").strip()

            answer = answer.replace("\\n", "\n")
            answer = answer.replace("Answer:", "").strip()
            answer_html = format_answer_html(answer)
            answer_html = re.sub(r'\s+(?=<)', ' ', answer_html)
            answer_html = re.sub(r'(?<=>)\s+', ' ', answer_html)
            answer_html = re.sub(r"<p>\s*<strong>\s*</strong>\s*</p>", "", answer_html, flags=re.IGNORECASE)
            answer = html_to_display_text(answer_html)

            final_kpis = [format_rupee_kpi_value(kpi) for kpi in parsed.get("kpis", [])]
            final_charts = parsed.get("charts", [])

            print("FINAL ANSWER:", answer)
            
            # ----------------------------
            # 🔥 EXTRACT ENRICHMENT DATA FROM KPIs
            # ----------------------------
            # Parse enrichment (Name, Industry, Owner, Context) from insight text
            import re as regex_module
            enriched_kpis = []
            for kpi in final_kpis:
                enriched_kpi = kpi.copy()
                insight = kpi.get("insight", "")
                
                # Extract Name | Industry | Owner | Context from insight
                name_match = regex_module.search(r'Name:\s*([^|]+)', insight)
                industry_match = regex_module.search(r'Industry:\s*([^|]+)', insight)
                owner_match = regex_module.search(r'(?:Owner|Lead Owner|Manager):\s*([^|]+)', insight)
                
                # Extract all pipe-separated segments for context
                segments = [s.strip() for s in insight.split('|')]
                
                if name_match:
                    enriched_kpi["name_field"] = name_match.group(1).strip()
                if industry_match:
                    enriched_kpi["industry_field"] = industry_match.group(1).strip()
                if owner_match:
                    enriched_kpi["owner_field"] = owner_match.group(1).strip()
                
                # Build enriched display with all fields
                enrichment_parts = []
                if name_match:
                    enrichment_parts.append(f"Name: {name_match.group(1).strip()}")
                if industry_match:
                    enrichment_parts.append(f"Industry: {industry_match.group(1).strip()}")
                if owner_match:
                    enrichment_parts.append(f"Owner: {owner_match.group(1).strip()}")
                
                # Add business context from insight
                if segments:
                    for seg in segments:
                        if seg and not any(prefix in seg for prefix in ['Name:', 'Industry:', 'Owner:', 'Lead Owner:', 'Manager:']):
                            enrichment_parts.append(seg)
                            break  # Just add the first contextual segment
                
                enriched_kpi["enrichment_context"] = " | ".join(enrichment_parts) if enrichment_parts else ""
                
                enriched_kpis.append(enriched_kpi)
            
            final_kpis = enriched_kpis

            # ----------------------------
            # 🔥 EXTRACT & SURFACE INSIGHTS (AI Intelligence Analysis Engine)
            # ----------------------------
            ai_intelligence_analysis = []
            for idx, kpi in enumerate(final_kpis):
                insight = kpi.get("insight", "")
                if insight:
                    ai_intelligence_analysis.append({
                        "metric": kpi.get("name", ""),
                        "value": kpi.get("value", ""),
                        "unit": kpi.get("unit", ""),
                        "key_insight": insight,  # 🎯 Full insight
                        "enrichment": kpi.get("enrichment_context", "")  # 🎯 Enriched display
                    })

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
                        "answer_html": answer_html,
                        "kpis": final_kpis,
                        "charts": final_charts,
                        "datasets": [c['name'] for c in dataset_configs],  # Track all datasets used
                        "comparison_mode": comparison_mode,
                        "ai_intelligence_analysis": ai_intelligence_analysis  # 🎯 Cache insights too
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
                "answer_html": answer_html,
                "kpis": final_kpis,
                "charts": final_charts,
                "datasets_used": [c['name'] for c in dataset_configs],
                "comparison_mode": comparison_mode,
                "ai_intelligence_analysis": ai_intelligence_analysis,  # 🎯 Prominent insights section
                "is_multi_file_analysis": is_multi_file,  # 🔗 Flag for multi-file analysis
                "multi_file_context": multi_file_context  # 🔗 Context for multi-file queries
            }

        except Exception as e:
            print("❌ AI Error:", str(e))

            return {
                "answer": "AI service unavailable",
                "kpis": [],
                "charts": [],
                "datasets_used": [],
                "comparison_mode": False,
                "is_multi_file_analysis": is_multi_file,
                "multi_file_context": None
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
        answer_html = format_answer_html(raw_text.strip())
        
        print("💾 RAG Fallback: NOT saving to DB (no dataset)")

        return {
            "answer": html_to_display_text(answer_html),
            "answer_html": answer_html,
            "kpis": [],
            "charts": [],
            "datasets_used": [],
            "comparison_mode": False,
            "is_multi_file_analysis": False,
            "multi_file_context": None
        }

    except Exception as e:
        print("❌ AI Error:", str(e))

        return {
            "answer": "AI service unavailable",
            "kpis": [],
            "charts": [],
            "datasets_used": [],
            "comparison_mode": False,
            "is_multi_file_analysis": False,
            "multi_file_context": None
        }
