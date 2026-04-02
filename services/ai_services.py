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
    Handles both ₹ (U+20B9) and mojibake variant â‚¹ to be encoding-safe.
    """
    if not isinstance(kpi, dict):
        return kpi

    formatted_kpi = kpi.copy()
    unit = str(formatted_kpi.get("unit", ""))
    if unit in {"\u20b9", "â‚¹", "₹"}:
        formatted_kpi["value"] = format_indian_number(formatted_kpi.get("value"))

    return formatted_kpi


SAFE_HTML_TAG_PATTERN = re.compile(
    r"</?(p|strong|ul|ol|li|em|code|table|thead|tbody|tfoot|tr|th|td|div|br)\b",
    re.IGNORECASE
)


def _decode_nested_html_entities(text: str, rounds: int = 3) -> str:
    """
    Decode model output that may contain escaped HTML such as &lt;p&gt;... .
    """
    decoded = text
    for _ in range(rounds):
        next_text = html.unescape(decoded)
        if next_text == decoded:
            break
        decoded = next_text
    return decoded


def format_answer_html(answer: str) -> str:
    """
    Normalize model output into lightweight HTML blocks.
    """
    if not answer:
        return ""

    answer = answer.replace("\r\n", "\n").replace("\r", "\n").strip()
    answer = _decode_nested_html_entities(answer)
    answer = re.sub(r"^\s*FINAL ANSWER:\s*", "", answer, flags=re.IGNORECASE).strip()
    answer = re.sub(
        r"<p>\s*<strong>\s*</strong>\s*</p>",
        "",
        answer,
        flags=re.IGNORECASE
    ).strip()

    if SAFE_HTML_TAG_PATTERN.search(answer):
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


# ----------------------------
# ✅ FIX 1: ARITHMETIC VERIFICATION
# Recomputes totals from the LLM's own row-level breakdown
# (computation_plan / verification_plan) and fixes mismatches
# before the result reaches the frontend or cache.
# Also patches the answer HTML so the displayed text matches
# the corrected value (previously the HTML was left unchanged).
# ----------------------------
def verify_and_fix_computation_plan(parsed: dict) -> dict:
    """
    If the model included a computation_plan or verification_plan with
    rows + expected_total, recompute the sum from the rows and override
    the plan total if there is a mismatch.

    Also patches any KPI whose value string matches the wrong total AND
    patches the answer HTML / plain-text answer so the displayed number
    matches the corrected value.
    """
    plan = parsed.get("computation_plan") or parsed.get("verification_plan")
    if not plan or not isinstance(plan, dict):
        return parsed

    rows = plan.get("rows", [])
    reported_total = plan.get("expected_total")

    if not rows or reported_total is None:
        return parsed

    try:
        reported_total = float(reported_total)
    except (TypeError, ValueError):
        return parsed

    computed = round(sum(float(row.get("value", 0)) for row in rows), 2)

    if abs(computed - reported_total) > 0.01:
        print(
            f"⚠️  ARITHMETIC MISMATCH DETECTED: "
            f"LLM reported {reported_total}, row-sum={computed}. "
            f"Overriding with correct value."
        )
        plan["expected_total"] = computed
        plan["mismatch_detected"] = True
        plan["original_reported_total"] = reported_total

        if "computation_plan" in parsed:
            parsed["computation_plan"] = plan
        else:
            parsed["verification_plan"] = plan

        # ── Patch KPI tiles that carry the wrong total ──────────────
        kpis = parsed.get("kpis", [])
        for kpi in kpis:
            raw_val = kpi.get("value")
            if raw_val is None:
                continue
            try:
                kpi_num = float(str(raw_val).replace(",", ""))
                if abs(kpi_num - reported_total) < 0.5:
                    kpi["value"] = computed
                    kpi["value_corrected"] = True
                    print(
                        f"   KPI '{kpi.get('name', '?')}' corrected: "
                        f"{reported_total} → {computed}"
                    )
            except (TypeError, ValueError):
                continue

        parsed["kpis"] = kpis

        # ── FIX: Patch answer HTML so displayed text shows corrected value ──
        # Replace the wrong number in the answer string so the frontend
        # does not show the stale incorrect figure.
        answer_html = parsed.get("answer", "")
        if answer_html:
            wrong_str_variants = [
                str(int(reported_total)) if reported_total == int(reported_total) else str(reported_total),
                format_indian_number(str(int(reported_total) if reported_total == int(reported_total) else reported_total)),
                f"{reported_total:,.2f}",
                f"{reported_total:,.0f}",
            ]
            correct_str = format_indian_number(
                str(int(computed) if computed == int(computed) else computed)
            )
            for wrong_str in wrong_str_variants:
                if wrong_str and wrong_str in answer_html:
                    answer_html = answer_html.replace(wrong_str, correct_str)
                    print(f"   Answer HTML patched: '{wrong_str}' → '{correct_str}'")
                    break
            parsed["answer"] = answer_html

    else:
        print(f"✅ Arithmetic verified: {computed} matches reported {reported_total}")

    return parsed


# ----------------------------
# ✅ FIX 2: DEAD-BUCKET GUARD
# The prompt.py REVENUE FILTER RULE says DEAD rows must NEVER appear
# in any revenue total. This guard scans the computation_plan rows and
# removes any DEAD bucket rows, then recalculates.
# ----------------------------
def remove_dead_bucket_rows(parsed: dict) -> dict:
    """
    Scan computation_plan rows. If any row carries bucket=DEAD
    (or semantically equivalent), remove it and recalculate expected_total.
    """
    plan = parsed.get("computation_plan") or parsed.get("verification_plan")
    if not plan or not isinstance(plan, dict):
        return parsed

    rows = plan.get("rows", [])
    if not rows:
        return parsed

    dead_keywords = {"dead", "lost", "closed lost", "dropped", "rejected",
                     "cancelled", "disqualified", "failed", "inactive",
                     "churned", "expired", "withdrawn", "junk", "invalid"}

    clean_rows = []
    removed = []
    for row in rows:
        bucket = str(row.get("bucket", "")).strip().lower()
        status = str(row.get("status", "")).strip().lower()
        if bucket == "dead" or any(kw in status for kw in dead_keywords):
            removed.append(row)
        else:
            clean_rows.append(row)

    if removed:
        dead_total = round(sum(float(r.get("value", 0)) for r in removed), 2)
        print(
            f"⚠️  DEAD BUCKET GUARD: Removed {len(removed)} dead row(s) "
            f"totalling {dead_total} from computation plan."
        )
        plan["rows"] = clean_rows
        plan["expected_total"] = round(
            sum(float(r.get("value", 0)) for r in clean_rows), 2
        )
        plan["dead_rows_removed"] = len(removed)
        plan["dead_rows_value"] = dead_total

        if "computation_plan" in parsed:
            parsed["computation_plan"] = plan
        else:
            parsed["verification_plan"] = plan

    return parsed


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
# ✅ FIX 3: BUILD DATASET CONTEXT WITH ROW COUNT HEADER
# Previously the prompt passed data[:500] with no indication of the
# total row count.  The model had no way to know it was seeing a slice,
# so it claimed to have analysed all rows when it hadn't.
# Now we prepend a header line stating total rows and shown rows so the
# model (and its TOTAL ROW COUNT RULE in the system prompt) can be honest.
# ----------------------------
def build_dataset_context(dataset_configs: list, max_rows_per_dataset: int = 500) -> str:
    """
    Build the dataset context string that is injected into the prompt.
    Each dataset block is prefixed with:
      Total rows in dataset: N | Showing rows: M
    so the model knows when it is only seeing a slice.
    """
    dataset_context = ""
    for config in dataset_configs:
        total_rows = len(config["data"])
        slice_data = config["data"][:max_rows_per_dataset]
        shown_rows = len(slice_data)

        dataset_json = json.dumps(slice_data, indent=2)
        dataset_context += (
            f"\n\nDataset: {config['name']}\n"
            f"Total rows in dataset: {total_rows} | Showing rows: {shown_rows}\n"
            f"{dataset_json}"
        )
    return dataset_context


# ----------------------------
# MAIN FUNCTION
# ----------------------------
def generate_ai_response(user_id: str, message: str, history=None, request=None, active_datasets=None, comparison_mode=False) -> dict:

    query = message.lower().strip()

    # ✅ GET ACTIVE DATASETS
    datasets = active_datasets or []

    if not datasets:
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

    primary_dataset = datasets[0] if datasets else None

    print(f"ACTIVE DATASETS: {datasets}")
    print(f"PRIMARY DATASET: {primary_dataset}")
    print(f"COMPARISON MODE: {comparison_mode}")
    print(f"🎯 Processing query: {query[:500]}...")

    # ----------------------------
    # 🔥 DETECT MULTI-FILE QUERIES
    # ----------------------------
    is_multi_file = multi_file_processor.is_multi_file_query(query, datasets or [])
    multi_file_context = None

    if is_multi_file and len(datasets) > 1:
        print("\n" + "🔗"*25)
        print("🔗 MULTI-FILE QUERY DETECTED")

        relationships = relationship_manager.get_relationships()

        relevant_datasets = multi_file_processor.identify_relevant_datasets(
            query, datasets, relationships
        )
        print(f"   Relevant datasets: {relevant_datasets}")

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
            # ✅ Only serve cache entries that passed verification
            if cached.get("arithmetic_verified") is False:
                print("⚠️  Cached result failed verification — skipping cache, recalculating.")
            else:
                print("✅ Returning cached result")
                cached_answer_html = cached.get("answer_html")
                if not cached_answer_html:
                    cached_answer_html = format_answer_html(cached.get("answer", ""))
                return {
                    "answer": html_to_display_text(cached_answer_html),
                    "answer_html": cached_answer_html,
                    "kpis": [format_rupee_kpi_value(kpi) for kpi in cached.get("kpis", [])],
                    "charts": cached["charts"],
                    "ai_intelligence_analysis": cached.get("ai_intelligence_analysis", []),
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

        # ✅ FIX 3: Use build_dataset_context() so the model knows
        # the total row count and shown row count for each dataset.
        dataset_context = build_dataset_context(dataset_configs, max_rows_per_dataset=500)

        comparison_instruction = ""
        if comparison_mode and len(dataset_configs) > 1:
            comparison_instruction = f"""

COMPARISON MODE ENABLED:
- You have access to {len(dataset_configs)} datasets: {', '.join([c['name'] for c in dataset_configs])}
- Compare metrics across these datasets
- Highlight differences and patterns
- Specify which dataset each result comes from
- Format: "[Dataset: {dataset_configs[0]['name']}] Metric: Value"
"""

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

            json_str = raw_text[start:end]

            try:
                parsed = load_model_json(json_str)
            except Exception as e:
                print("❌ JSON Parse Error:", e)
                return build_plain_text_response(
                    raw_text,
                    is_multi_file=is_multi_file,
                    multi_file_context=multi_file_context
                )

            # ----------------------------
            # ✅ FIX 1+2: VERIFY & CLEAN COMPUTATION PLAN
            # Run dead-bucket guard first, then arithmetic check.
            # verify_and_fix_computation_plan now also patches answer HTML.
            # ----------------------------
            parsed = remove_dead_bucket_rows(parsed)
            parsed = verify_and_fix_computation_plan(parsed)

            # Track whether arithmetic passed for cache guard
            plan = parsed.get("computation_plan") or parsed.get("verification_plan") or {}
            arithmetic_verified = not plan.get("mismatch_detected", False)

            # ----------------------------
            # 🔥 PREPARE FINAL OUTPUT
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
            enriched_kpis = []
            for kpi in final_kpis:
                enriched_kpi = kpi.copy()
                insight = kpi.get("insight", "")

                name_match = re.search(r'Name:\s*([^|]+)', insight)
                industry_match = re.search(r'Industry:\s*([^|]+)', insight)
                owner_match = re.search(r'(?:Owner|Lead Owner|Manager):\s*([^|]+)', insight)

                segments = [s.strip() for s in insight.split('|')]

                if name_match:
                    enriched_kpi["name_field"] = name_match.group(1).strip()
                if industry_match:
                    enriched_kpi["industry_field"] = industry_match.group(1).strip()
                if owner_match:
                    enriched_kpi["owner_field"] = owner_match.group(1).strip()

                enrichment_parts = []
                if name_match:
                    enrichment_parts.append(f"Name: {name_match.group(1).strip()}")
                if industry_match:
                    enrichment_parts.append(f"Industry: {industry_match.group(1).strip()}")
                if owner_match:
                    enrichment_parts.append(f"Owner: {owner_match.group(1).strip()}")

                if segments:
                    for seg in segments:
                        if seg and not any(prefix in seg for prefix in ['Name:', 'Industry:', 'Owner:', 'Lead Owner:', 'Manager:']):
                            enrichment_parts.append(seg)
                            break

                enriched_kpi["enrichment_context"] = " | ".join(enrichment_parts) if enrichment_parts else ""
                enriched_kpis.append(enriched_kpi)

            final_kpis = enriched_kpis

            # ----------------------------
            # 🔥 EXTRACT & SURFACE INSIGHTS
            # ----------------------------
            ai_intelligence_analysis = []
            for kpi in final_kpis:
                insight = kpi.get("insight", "")
                if insight:
                    ai_intelligence_analysis.append({
                        "metric": kpi.get("name", ""),
                        "value": kpi.get("value", ""),
                        "unit": kpi.get("unit", ""),
                        "key_insight": insight,
                        "enrichment": kpi.get("enrichment_context", "")
                    })

            # ----------------------------
            # 🔥 SAVE RESULT
            # ✅ FIX 3: Tag cache entry with arithmetic_verified flag.
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
                print(f"   Arithmetic verified: {arithmetic_verified}")

                if primary_dataset:
                    save_data = {
                        "file_name": primary_dataset,
                        "query": query,
                        "answer": answer,
                        "answer_html": answer_html,
                        "kpis": final_kpis,
                        "charts": final_charts,
                        "datasets": [c['name'] for c in dataset_configs],
                        "comparison_mode": comparison_mode,
                        "ai_intelligence_analysis": ai_intelligence_analysis,
                        "arithmetic_verified": arithmetic_verified
                    }

                    print(f"\n🔴 SAVE CHECKPOINT 3: Calling mongo_client.save_result()")
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
                "ai_intelligence_analysis": ai_intelligence_analysis,
                "is_multi_file_analysis": is_multi_file,
                "multi_file_context": multi_file_context
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
