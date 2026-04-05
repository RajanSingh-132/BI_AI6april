import re
import html
import pandas as pd
import numpy as np
import pandas as pd
import logging

def calculate_leads_metrics(data):
    """
    Calculate total leads and categorize into success, failed, and on-hold.

    Args:
        data (list[dict] | pd.DataFrame): Input dataset rows.

    Returns:
        tuple:
        (
            total_leads: int,
            success_leads: int,
            failed_leads: int,
            on_hold_leads: int,
            status_col: str,
            df: pd.DataFrame
        )
    """

    # Convert input data to DataFrame
    df = pd.DataFrame(data)

    # -------------------------------
    # STEP 1 — Detect status column
    # -------------------------------
    status_col = None

    valid_status_cols = ["status", "lead_status", "stage", "deal_status"]

    for col in df.columns:
        if col.lower().strip() in valid_status_cols:
            status_col = col
            break

    if status_col is None:
        raise ValueError("Lead status column not found. Expected one of: status, lead_status, stage, deal_status")

    # -------------------------------
    # STEP 2 — Normalize values
    # -------------------------------
    df[status_col] = df[status_col].astype(str).str.lower().str.strip()

    # -------------------------------
    # STEP 3 — Define categories
    # -------------------------------
    success_list = ["won", "closed won", "success", "converted"]
    failed_list = ["lost", "closed lost", "failed", "rejected"]
    on_hold_list = ["on hold", "pending", "in progress", "open"]

    # -------------------------------
    # STEP 4 — Calculate counts
    # -------------------------------
    total_leads = len(df)

    success_leads = int(df[df[status_col].isin(success_list)].shape[0])
    failed_leads = int(df[df[status_col].isin(failed_list)].shape[0])
    on_hold_leads = int(df[df[status_col].isin(on_hold_list)].shape[0])

    # -------------------------------
    # LOGGING
    # -------------------------------
    print(f"[LEADS_LOG] status_col={status_col}")
    print(f"[LEADS_LOG] total_leads={total_leads}")
    print(f"[LEADS_LOG] success_leads={success_leads}")
    print(f"[LEADS_LOG] failed_leads={failed_leads}")
    print(f"[LEADS_LOG] on_hold_leads={on_hold_leads}")

    logging.info(f"Leads calculated: total={total_leads}, success={success_leads}, failed={failed_leads}, on_hold={on_hold_leads}")

    return (
        total_leads,
        success_leads,
        failed_leads,
        on_hold_leads,
        status_col,
        df
    )


SYSTEM_PROMPT = """
You are an advanced AI Business Analyst.

Your job is to analyze ANY tabular dataset dynamically and generate meaningful lead metrics.

--------------------------------------------------

CORE INTELLIGENCE

You MUST:
1. Automatically detect dataset type using column names
2. Identify lead-related columns (status, stage, lead_state, etc.)
3. Calculate EXACT counts — NEVER estimate
4. Iterate through EVERY row
5. Skip invalid/missing values safely
6. Adapt to CRM datasets (Zoho, HubSpot, Salesforce, etc.)
7. NEVER assume equal distribution

--------------------------------------------------

LEADS CALCULATION ENGINE (MANDATORY — PANDAS ONLY)

STEP 1 — COLUMN DETECTION:

Detect:
- lead_status column using:
  ["status", "lead_status", "stage", "deal_status"]

If not found:
→ Return error: "Lead status column not found"

--------------------------------------------------

STEP 2 — NORMALIZATION:

Convert all values to lowercase:

  df[status_col] = df[status_col].astype(str).str.lower().str.strip()

--------------------------------------------------

STEP 3 — CLASSIFICATION LOGIC:

Map values into 3 categories:

SUCCESS LEADS:
  ["won", "closed won", "success", "converted"]

FAILED LEADS:
  ["lost", "closed lost", "failed", "rejected"]

ON HOLD LEADS:
  ["on hold", "pending", "in progress", "open"]

--------------------------------------------------

STEP 4 — COUNT USING PANDAS:

total_leads = len(df)

success_leads = len(df[df[status_col].isin(success_list)])
failed_leads = len(df[df[status_col].isin(failed_list)])
on_hold_leads = len(df[df[status_col].isin(on_hold_list)])

--------------------------------------------------

RULES:

- NEVER use assumptions
- NEVER create fake rows
- ALWAYS count using pandas filtering
- ALWAYS include ALL rows
- If status not matched → ignore (do NOT classify)

--------------------------------------------------

ANTI-HALLUCINATION (CRITICAL)

- Use ONLY dataset rows
- Do NOT generate fake leads
- Do NOT assume missing statuses

--------------------------------------------------

CALCULATION VERIFICATION

You MUST:
- Show row-wise breakdown
- Show counts per category
- Ensure:
    total = success + failed + on_hold (+ ignored if any)

--------------------------------------------------

TRANSPARENCY TABLE (MANDATORY)

<p>✅ CALCULATION BREAKDOWN — Leads Analysis:</p>

<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
<thead>
<tr style="background:#e3f2fd">
<th>[Lead ID]</th>
<th>[Lead Name]</th>
<th>[Status]</th>
</tr>
</thead>
<tbody>
<tr><td>...</td><td>...</td><td>...</td></tr>
</tbody>
</table>

--------------------------------------------------

RESPONSE FORMAT (STRICT HTML + JSON)

<p><strong>Answer:</strong></p>
<p>Analysis of total leads and their status distribution.</p>

<p><strong>Key Insights:</strong></p>
<ul>
<li><strong>Total Leads:</strong> X</li>
<li><strong>Successful Leads:</strong> X</li>
<li><strong>Failed Leads:</strong> X</li>
<li><strong>On Hold Leads:</strong> X</li>
</ul>

--------------------------------------------------

FINAL OUTPUT JSON:

{
  "answer": "<HTML content>",
  "kpis": [
    {
      "name": "Total Leads",
      "value": total_leads,
      "unit": "count",
      "insight": "Total number of leads in dataset"
    },
    {
      "name": "Successful Leads",
      "value": success_leads,
      "unit": "count",
      "insight": "Leads successfully converted"
    },
    {
      "name": "Failed Leads",
      "value": failed_leads,
      "unit": "count",
      "insight": "Leads that did not convert"
    },
    {
      "name": "On Hold Leads",
      "value": on_hold_leads,
      "unit": "count",
      "insight": "Leads still in progress or pending"
    }
  ],
  "row_count": total_leads
}

--------------------------------------------------

GREETING HANDLING

{
  "answer": "Hello! I can analyse your leads and their performance. Please provide your dataset.",
  "kpis": []
}

--------------------------------------------------

FAIL SAFE

{
  "answer": "Sorry, I can only analyse lead-related datasets.",
  "kpis": []
}

--------------------------------------------------
"""

# ===================================================
# RESPONSE FORMATTER
# ===================================================

SAFE_HTML_TAG_PATTERN = re.compile(
    r"</?(p|strong|ul|ol|li|em|code|table|thead|tbody|tfoot|tr|th|td|div|br|span|h1|h2|h3|h4|blockquote)\b",
    re.IGNORECASE
)


def _decode_nested_html_entities(text: str, rounds: int = 3) -> str:
    decoded = text
    for _ in range(rounds):
        next_text = html.unescape(decoded)
        if next_text == decoded:
            break
        decoded = next_text
    return decoded


def format_response(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""

    text = _decode_nested_html_entities(text.strip())
    text = re.sub(r"^\s*FINAL ANSWER:\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(
        r"<p>\s*<strong>\s*</strong>\s*</p>",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    if SAFE_HTML_TAG_PATTERN.search(text):
        return text

    text = re.sub(r"\n\s*\n+", "\n", text)

    lines = text.split("\n")
    formatted = []
    in_ul = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith(("- ", "* ")) or re.match(r"^\d+\.\s+", line):
            if not in_ul:
                formatted.append("<ul>")
                in_ul = True
            item = re.sub(r"^(- |\* |\d+\.\s+)", "", line)
            item = html.escape(item)
            item = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item)
            item = re.sub(r"\*(.*?)\*", r"<em>\1</em>", item)
            formatted.append(f"<li>{item}</li>")

        else:
            if in_ul:
                formatted.append("</ul>")
                in_ul = False
            escaped_line = html.escape(line)
            escaped_line = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped_line)
            escaped_line = re.sub(r"\*(.*?)\*", r"<em>\1</em>", escaped_line)
            formatted.append(f"<p>{escaped_line}</p>")

    if in_ul:
        formatted.append("</ul>")

    html_output = "\n".join(formatted)
    html_output = re.sub(r"<p>\s*</p>", "", html_output)

    return html_output
