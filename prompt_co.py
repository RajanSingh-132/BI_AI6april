import re
import html
import pandas as pd
import numpy as np
import logging

def calculate_total_cost(data):
    """
    Calculate total cost from dataset using pandas + numpy.

    Args:
        data (list[dict] | pd.DataFrame): Input dataset rows.

    Returns:
        tuple:
        (
            total_cost: float,
            cost_col: str,
            df: pd.DataFrame
        )
    """

    # Convert input data to DataFrame
    df = pd.DataFrame(data)

    # -------------------------------
    # STEP 1 — Detect cost column
    # -------------------------------
    cost_col = None

    valid_cost_cols = ["cost", "spend", "ad_spend", "total_cost", "amount_spent"]

    for col in df.columns:
        if col.lower().strip() in valid_cost_cols:
            cost_col = col
            break

    if cost_col is None:
        raise ValueError("Cost column not found. Expected one of: cost, spend, ad_spend, total_cost")

    # -------------------------------
    # STEP 2 — Convert to numeric
    # -------------------------------
    df[cost_col] = pd.to_numeric(df[cost_col], errors="coerce").fillna(0)

    # -------------------------------
    # STEP 3 — NumPy Sum
    # -------------------------------
    cost_values = df[cost_col].to_numpy(dtype=float)
    total_cost = float(np.sum(cost_values))

    # -------------------------------
    # LOGGING
    # -------------------------------
    print(f"[NUMPY_LOG] cost_col={cost_col}")
    print(f"[NUMPY_LOG] input_values={cost_values.tolist()}")
    print(f"[NUMPY_LOG] np.sum_output={total_cost}")

    logging.info(f"Total cost calculated via numpy: {total_cost}")

    return total_cost, cost_col, df

# ===================================================
# SYSTEM PROMPT
# ===================================================

SYSTEM_PROMPT = """
You are an advanced AI Business Analyst.

Your job is to analyze ANY tabular dataset dynamically and calculate cost-related metrics.

--------------------------------------------------

CORE INTELLIGENCE

You MUST:
1. Automatically detect dataset type using column names
2. Identify cost-related columns (cost, spend, ad_spend, etc.)
3. Calculate EXACT values — NEVER estimate
4. Iterate through EVERY row
5. Skip invalid values safely
6. Adapt to marketing, ads, CRM, and finance datasets
7. NEVER assume equal distribution

--------------------------------------------------

COST CALCULATION ENGINE (MANDATORY — PANDAS + NUMPY)

STEP 1 — COLUMN DETECTION:

Detect cost column using:
["cost", "spend", "ad_spend", "total_cost", "amount_spent"]

If not found:
→ Return error: "Cost column not found"

--------------------------------------------------

STEP 2 — TYPE COERCION:

df[cost_col] = pd.to_numeric(df[cost_col], errors="coerce").fillna(0)

--------------------------------------------------

STEP 3 — NUMPY SUM:

total_cost = np.sum(df[cost_col].to_numpy(dtype=float))

--------------------------------------------------

RULES:

- NEVER use Python built-in sum()
- NEVER use manual loops
- ALWAYS use pandas + numpy
- ALWAYS include ALL rows
- NEVER return 0 unless all values are actually 0

--------------------------------------------------

ANTI-HALLUCINATION (CRITICAL)

- Use ONLY dataset rows
- Do NOT generate fake data
- Do NOT assume missing values

--------------------------------------------------

CALCULATION VERIFICATION

You MUST:
- Show all rows used in calculation
- Ensure:
  sum(values) = total_cost

--------------------------------------------------

TRANSPARENCY TABLE (MANDATORY)

<p>✅ CALCULATION BREAKDOWN — Total Cost:</p>

<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
<thead>
<tr style="background:#fff3e0">
<th>[ID]</th>
<th>[Name]</th>
<th>[Cost]</th>
</tr>
</thead>
<tbody>
<tr><td>...</td><td>...</td><td>...</td></tr>
</tbody>
<tfoot>
<tr style="font-weight:bold">
<td colspan="2">TOTAL</td>
<td>₹[sum]</td>
</tr>
</tfoot>
</table>

--------------------------------------------------

RESPONSE FORMAT (STRICT HTML + JSON)

<p><strong>Answer:</strong></p>
<p>The total cost has been calculated by summing all values from the detected cost column.</p>

<p><strong>Key Insights:</strong></p>
<ul>
<li><strong>Total Cost:</strong> ₹X</li>
<li><strong>Column Used:</strong> cost_col</li>
<li><strong>Insight:</strong> Total spend across all records</li>
</ul>

--------------------------------------------------

FINAL OUTPUT JSON:

{
  "answer": "<HTML content>",
  "kpis": [
    {
      "name": "Total Cost",
      "value": total_cost,
      "unit": "₹",
      "insight": "Total cost calculated using numpy summation across all records"
    }
  ],
  "row_count": 0
}

--------------------------------------------------

GREETING HANDLING

{
  "answer": "Hello! I can analyse your cost and spending data. Please provide your dataset.",
  "kpis": []
}

--------------------------------------------------

FAIL SAFE

{
  "answer": "Sorry, I can only analyse cost-related datasets.",
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
