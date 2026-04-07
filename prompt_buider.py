import re
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# NOTE: This module contains legacy code using deprecated prompt modules (prompt_re, prompt_co, prompt_le)
# The new semantic analysis system should be used instead (master_prompt.py, semantic_extractor.py)
# Keeping this for reference but marking as deprecated.

# from prompt_re import SYSTEM_PROMPT as REVENUE_SYSTEM_PROMPT, calculate_all_revenue_metrics
# from prompt_co import SYSTEM_PROMPT as COST_SYSTEM_PROMPT
# from prompt_le import SYSTEM_PROMPT as LEADS_SYSTEM_PROMPT

DEFAULT_SYSTEM_PROMPT = ""  # Placeholder - use new semantic system instead


def route_query(user_query: str) -> str:
    """
    Route user query to one of: revenue, cost, leads.
    """
    q = (user_query or "").lower().strip()

    revenue_keywords = (
        "revenue", "deal value", "deal_value", "sales amount", "total sales","re"
    )
    cost_keywords = (
        "cost", "spend", "ad spend", "amount spent", "expense", "expenses"
    )
    leads_keywords = (
        "lead", "leads", "lead status", "conversion", "converted", "pipeline"
    )

    if any(k in q for k in leads_keywords):
        return "leads"
    if any(k in q for k in revenue_keywords):
        return "revenue"
    if any(k in q for k in cost_keywords):
        return "cost"
    return "unsupported"


def get_system_prompt_for_query(user_query: str) -> str:
    """
    Select prompt template based on query intent.
    """
    intent = route_query(user_query)
    if intent == "revenue":
        return REVENUE_SYSTEM_PROMPT
    if intent == "cost":
        return COST_SYSTEM_PROMPT
    if intent == "leads":
        return LEADS_SYSTEM_PROMPT
    return DEFAULT_SYSTEM_PROMPT


def _detect_lead_status_column(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None

    def _norm(name: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(name).lower().strip())

    valid_status_cols = {
        "status",
        "leadstatus",
        "stage",
        "dealstatus",
        "leadstage",
        "opportunitystage",
        "pipelinestatus",
        "pipelinestage",
    }

    # 1) Strong name-based match
    for col in df.columns:
        norm = _norm(col)
        if norm in valid_status_cols:
            return col

    # 2) Fuzzy lead/status naming patterns
    for col in df.columns:
        norm = _norm(col)
        has_lead_or_pipeline = ("lead" in norm) or ("pipeline" in norm)
        has_state_word = any(t in norm for t in ("status", "stage", "state", "outcome", "result"))
        if has_lead_or_pipeline and has_state_word:
            return col

    # 3) Value-based detection fallback for string-like columns
    vocab = {
        "won", "closedwon", "success", "converted",
        "lost", "closedlost", "failed", "rejected",
        "onhold", "pending", "inprogress", "open",
    }
    best_col = None
    best_ratio = 0.0
    for col in df.columns:
        series = (
            df[col]
            .astype(str)
            .str.lower()
            .str.strip()
            .replace({"": np.nan, "nan": np.nan, "none": np.nan})
            .dropna()
        )
        if series.empty:
            continue
        cleaned = series.str.replace(r"[^a-z0-9]", "", regex=True)
        ratio = float(cleaned.isin(vocab).mean())
        if ratio > best_ratio:
            best_ratio = ratio
            best_col = col

    if best_col is not None and best_ratio >= 0.2:
        return best_col

    return None


def _detect_leads_count_column(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None

    def _norm(name: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(name).lower().strip())

    candidates = []
    for col in df.columns:
        norm = _norm(col)
        if "lead" not in norm:
            continue
        if any(t in norm for t in ("status", "stage", "source", "owner", "name", "id")):
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        ratio_numeric = float(values.notna().mean()) if len(values) else 0.0
        non_zero_ratio = float(values.fillna(0).ne(0).mean()) if len(values) else 0.0
        if ratio_numeric >= 0.6:
            candidates.append((ratio_numeric, non_zero_ratio, str(col)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def _detect_numeric_column_by_intent(df: pd.DataFrame, intent: str) -> str | None:
    if df.empty:
        return None

    if intent == "revenue":
        strong = ("revenue", "dealvalue", "deal_value", "re", "amount", "value", "expectedrevenue")
    elif intent == "cost":
        strong = ("cost", "spend", "expense", "amountspent", "adspend", "totalcost")
    else:
        strong = ()

    deny = ("name", "id", "email", "phone", "city", "state", "country", "status", "stage", "rep", "owner")
    scored = []

    for col in df.columns:
        col_raw = str(col).strip().lower()
        norm = re.sub(r"[^a-z0-9]", "", col_raw)

        score = 0
        if any(k in norm for k in strong):
            score += 10
        if any(k in norm for k in deny):
            score -= 6

        series = pd.to_numeric(df[col], errors="coerce").fillna(0)
        non_zero_ratio = float((series != 0).mean()) if len(series) else 0.0
        sum_abs = float(np.abs(series.to_numpy(dtype=float)).sum())
        score += int(non_zero_ratio * 4)
        if sum_abs > 0:
            score += 1

        scored.append((score, non_zero_ratio, sum_abs, str(col)))

    if not scored:
        return None

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    best = scored[0]
    if best[0] <= 0:
        return None
    return best[3]


def _detect_entity_column_for_revenue(df: pd.DataFrame, query: str) -> tuple[str | None, str | None]:
    q = (query or "").lower()
    entity_specs = [
        ("Owner", ("owner", "lead_owner", "lead owner", "account owner", "sales owner")),
        ("Sales Rep", ("sales rep", "sales_rep", "rep", "salesperson", "sales person")),
        ("Manager", ("manager", "lead manager", "account manager")),
    ]

    for label, query_tokens in entity_specs:
        if not any(t in q for t in query_tokens):
            continue
        for col in df.columns:
            col_l = str(col).lower().strip()
            if any(t in col_l for t in query_tokens):
                return str(col), label

    # Fallback for common owner-like queries
    if any(t in q for t in ("owner", "who", "which person", "which user")):
        for col in df.columns:
            col_l = str(col).lower().strip()
            if any(t in col_l for t in ("owner", "sales_rep", "rep", "manager")):
                return str(col), "Owner"

    return None, None


def _is_highest_entity_revenue_query(query: str) -> bool:
    q = (query or "").lower()
    asks_highest = any(t in q for t in ("highest", "top", "max", "most"))
    asks_revenue = any(t in q for t in ("revenue", "deal value", "deal_value", "sales", "re"))
    asks_entity = any(t in q for t in ("owner", "sales rep", "rep", "manager", "who"))
    return asks_highest and asks_revenue and asks_entity


def _is_lowest_entity_revenue_query(query: str) -> bool:
    q = (query or "").lower()
    asks_lowest = any(t in q for t in ("lowest", "bottom", "min", "minimum", "least"))
    asks_revenue = any(t in q for t in ("revenue", "deal value", "deal_value", "sales"))
    asks_entity = any(t in q for t in ("owner", "sales rep", "rep", "manager", "who"))
    return asks_lowest and asks_revenue and asks_entity


def _is_entity_revenue_analysis_query(query: str) -> bool:
    q = (query or "").lower()
    asks_analysis = any(t in q for t in ("analysis", "analyse", "breakdown", "by owner", "by rep", "by manager"))
    asks_revenue = any(t in q for t in ("revenue", "deal value", "deal_value", "sales"))
    asks_entity = any(t in q for t in ("owner", "sales rep", "rep", "manager"))
    return asks_analysis and asks_revenue and asks_entity


def _detect_entity_column_for_leads(df: pd.DataFrame, query: str) -> tuple[str | None, str | None]:
    q = (query or "").lower()
    entity_specs = [
        ("Owner", ("owner", "lead_owner", "lead owner", "account owner", "sales owner")),
        ("Sales Rep", ("sales rep", "sales_rep", "rep", "salesperson", "sales person")),
        ("Manager", ("manager", "lead manager", "account manager")),
        ("User", ("user", "agent", "assignee")),
    ]

    for label, query_tokens in entity_specs:
        if not any(t in q for t in query_tokens):
            continue
        for col in df.columns:
            col_l = str(col).lower().strip()
            if any(t in col_l for t in query_tokens):
                return str(col), label

    # Fallback for "who has highest leads" style questions.
    if any(t in q for t in ("who", "highest", "top", "lowest", "most", "least", "analysis", "breakdown")):
        for col in df.columns:
            col_l = str(col).lower().strip()
            if any(t in col_l for t in ("owner", "sales_rep", "rep", "manager", "user", "agent", "assignee")):
                return str(col), "Owner"

    return None, None


def _is_highest_entity_leads_query(query: str) -> bool:
    q = (query or "").lower()
    asks_highest = any(t in q for t in ("highest", "top", "max", "most"))
    asks_leads = any(t in q for t in ("lead", "leads", "lead count", "total leads"))
    asks_entity = any(t in q for t in ("owner", "sales rep", "rep", "manager", "user", "agent", "who"))
    return asks_highest and asks_leads and asks_entity


def _is_lowest_entity_leads_query(query: str) -> bool:
    q = (query or "").lower()
    asks_lowest = any(t in q for t in ("lowest", "bottom", "min", "minimum", "least"))
    asks_leads = any(t in q for t in ("lead", "leads", "lead count", "total leads"))
    asks_entity = any(t in q for t in ("owner", "sales rep", "rep", "manager", "user", "agent", "who"))
    return asks_lowest and asks_leads and asks_entity


def _is_entity_leads_analysis_query(query: str) -> bool:
    q = (query or "").lower()
    asks_analysis = any(t in q for t in ("analysis", "analyse", "breakdown", "by owner", "by rep", "by manager", "by user", "by agent"))
    asks_leads = any(t in q for t in ("lead", "leads"))
    asks_entity = any(t in q for t in ("owner", "sales rep", "rep", "manager", "user", "agent", "who"))
    return asks_analysis and asks_leads and asks_entity


def _build_leads_charts(query: str, selected_kpis: List[Dict[str, Any]], all_kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    q = (query or "").lower()
    by_name = {str(k.get("name", "")): k for k in all_kpis}

    def to_float(v: Any) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0

    success = to_float((by_name.get("Successful Leads") or {}).get("value", 0))
    failed = to_float((by_name.get("Failed Leads") or {}).get("value", 0))
    on_hold = to_float((by_name.get("On Hold Leads") or {}).get("value", 0))
    total = to_float((by_name.get("Total Leads") or {}).get("value", 0))
    success_pct = to_float((by_name.get("Lead Distribution - Success") or {}).get("value", 0))
    failed_pct = to_float((by_name.get("Lead Distribution - Failed") or {}).get("value", 0))
    on_hold_pct = to_float((by_name.get("Lead Distribution - On Hold") or {}).get("value", 0))

    if any(t in q for t in ("success", "won", "converted")):
        return [
            {
                "type": "bar",
                "title": "Successful vs Other Leads",
                "x_axis": ["Successful Leads", "Other Leads"],
                "y_axis": [round(success, 2), round(max(total - success, 0.0), 2)],
                "insight": "Compares successful leads against the remaining lead pool."
            },
            {
                "type": "pie",
                "title": "Lead Success Split",
                "labels": ["Successful %", "Remaining %"],
                "values": [round(success_pct, 2), round(max(100.0 - success_pct, 0.0), 2)],
                "insight": "Shows the percentage share of successful leads."
            }
        ]

    if any(t in q for t in ("failed", "lost", "rejected")):
        return [
            {
                "type": "bar",
                "title": "Failed vs Other Leads",
                "x_axis": ["Failed Leads", "Other Leads"],
                "y_axis": [round(failed, 2), round(max(total - failed, 0.0), 2)],
                "insight": "Compares failed leads against the remaining lead pool."
            },
            {
                "type": "pie",
                "title": "Lead Failure Split",
                "labels": ["Failed %", "Remaining %"],
                "values": [round(failed_pct, 2), round(max(100.0 - failed_pct, 0.0), 2)],
                "insight": "Shows the percentage share of failed leads."
            }
        ]

    if any(t in q for t in ("on hold", "pending", "open", "in progress")):
        return [
            {
                "type": "bar",
                "title": "On-Hold vs Other Leads",
                "x_axis": ["On Hold Leads", "Other Leads"],
                "y_axis": [round(on_hold, 2), round(max(total - on_hold, 0.0), 2)],
                "insight": "Compares on-hold leads against the remaining lead pool."
            },
            {
                "type": "pie",
                "title": "On-Hold Lead Split",
                "labels": ["On Hold %", "Remaining %"],
                "values": [round(on_hold_pct, 2), round(max(100.0 - on_hold_pct, 0.0), 2)],
                "insight": "Shows the percentage share of on-hold leads."
            }
        ]

    return [
        {
            "type": "bar",
            "title": "Leads Status Comparison",
            "x_axis": ["Successful Leads", "Failed Leads", "On Hold Leads"],
            "y_axis": [round(success, 2), round(failed, 2), round(on_hold, 2)],
            "insight": "Compares lead volumes by status category."
        },
        {
            "type": "pie",
            "title": "Leads Distribution",
            "labels": ["Success %", "Failed %", "On Hold %"],
            "values": [round(success_pct, 2), round(failed_pct, 2), round(on_hold_pct, 2)],
            "insight": "Shows lead status share as percentages."
        }
    ]


def _calculate_leads_metrics_numpy(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Leads metrics with NumPy-backed counting on normalized status values.
    """
    df = pd.DataFrame(data)
    status_col = _detect_lead_status_column(df)
    if status_col is None:
        # Fallback for datasets that track aggregated lead counts
        # but do not expose per-row lead status.
        lead_count_col = _detect_leads_count_column(df)
        if lead_count_col:
            lead_counts = pd.to_numeric(df[lead_count_col], errors="coerce").fillna(0).to_numpy(dtype=float)
            total_leads = int(np.round(np.sum(lead_counts)))
            return {
                "metric": "Total Leads",
                "value": total_leads,
                "unit": "count",
                "value_column": lead_count_col,
                "status_col": lead_count_col,
                "operation": "SUM",
                "extra_kpis": [],
            }

        # Last-resort fallback: count dataset rows as leads for total-lead queries.
        total_leads = int(df.shape[0])
        return {
            "metric": "Total Leads",
            "value": total_leads,
            "unit": "count",
            "value_column": None,
            "status_col": None,
            "operation": "COUNT",
            "extra_kpis": [],
        }

    statuses = (
        df[status_col]
        .astype(str)
        .str.lower()
        .str.strip()
        .to_numpy(dtype=str)
    )

    success_list = np.array(["won", "closed won", "success", "converted"], dtype=str)
    failed_list = np.array(["lost", "closed lost", "failed", "rejected"], dtype=str)
    on_hold_list = np.array(["on hold", "pending", "in progress", "open"], dtype=str)

    total_leads = int(statuses.size)
    success_leads = int(np.sum(np.isin(statuses, success_list)))
    failed_leads = int(np.sum(np.isin(statuses, failed_list)))
    on_hold_leads = int(np.sum(np.isin(statuses, on_hold_list)))
    success_pct = float(round((success_leads / total_leads * 100), 2)) if total_leads > 0 else 0.0
    failed_pct = float(round((failed_leads / total_leads * 100), 2)) if total_leads > 0 else 0.0
    on_hold_pct = float(round((on_hold_leads / total_leads * 100), 2)) if total_leads > 0 else 0.0

    return {
        "metric": "Total Leads",
        "value": total_leads,
        "unit": "count",
        "status_col": status_col,
        "operation": "COUNT",
        "extra_kpis": [
            {"name": "Successful Leads", "value": success_leads, "unit": "count"},
            {"name": "Failed Leads", "value": failed_leads, "unit": "count"},
            {"name": "On Hold Leads", "value": on_hold_leads, "unit": "count"},
            {"name": "Lead Distribution - Success", "value": success_pct, "unit": "%"},
            {"name": "Lead Distribution - Failed", "value": failed_pct, "unit": "%"},
            {"name": "Lead Distribution - On Hold", "value": on_hold_pct, "unit": "%"},
        ],
    }


def _build_selected_kpis(intent: str, query: str, all_kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    q = (query or "").lower()

    def has_any(*tokens: str) -> bool:
        return any(t in q for t in tokens)

    selected: List[Dict[str, Any]] = []
    by_name = {str(k.get("name", "")): k for k in all_kpis}

    def add(name: str):
        kpi = by_name.get(name)
        if kpi and kpi not in selected:
            selected.append(kpi)

    ask_distribution = has_any("distribution", "percent", "percentage", "%", "ratio", "split")

    if intent == "revenue":
        ask_total = has_any("total", "sum", "overall")
        ask_average = has_any("average", "avg", "mean")
        ask_median = has_any("median")
        ask_std = has_any("std", "standard deviation", "volatility")
        ask_variance = has_any("variance")
        ask_top = has_any("top", "high", "highest", "max", "best")
        ask_low = has_any("low", "lowest", "min", "minimum", "worst", "bottom")
        ask_range = has_any("range", "spread")
        ask_above = has_any("above average")
        ask_below = has_any("below average")
        ask_profit = has_any("gross profit", "profit")
        ask_margin = has_any("gross margin", "margin %", "margin percentage")
        ask_per_unit = has_any("per unit", "unit revenue", "arpu")
        ask_p25 = has_any("p25", "25th percentile", "bottom quartile")
        ask_p75 = has_any("p75", "75th percentile", "top quartile")
        ask_iqr = has_any("iqr", "interquartile range")
        ask_analysis = has_any("analysis", "analyse", "summary", "overview", "performance")

        if ask_total:
            add("Total Revenue")
        if ask_average:
            add("Average Revenue")
        if ask_median:
            add("Median Revenue")
        if ask_std:
            add("Revenue Std Deviation")
        if ask_variance:
            add("Revenue Variance")
        if ask_top:
            add("Top Revenue")
            if ask_distribution:
                add("Top Revenue Distribution")
        if ask_low:
            add("Low Revenue")
            if ask_distribution:
                add("Low Revenue Distribution")
        if ask_range:
            add("Revenue Range")
        if ask_above:
            add("Above-Average Count")
        if ask_below:
            add("Below-Average Count")
        if ask_profit:
            add("Gross Profit")
        if ask_margin:
            add("Gross Margin %")
        if ask_per_unit:
            add("Revenue per Unit")
        if ask_p25:
            add("Revenue P25")
        if ask_p75:
            add("Revenue P75")
        if ask_iqr:
            add("Revenue IQR")
        if ask_distribution and not (ask_top or ask_low):
            add("Top Revenue Distribution")
            add("Low Revenue Distribution")
        if ask_analysis:
            add("Total Revenue")
            add("Average Revenue")
            add("Top Revenue")
            add("Low Revenue")
            add("Revenue Range")

    elif intent == "cost":
        ask_total = has_any("total", "sum", "overall", "spend", "cost")
        ask_best = has_any("best", "low", "lowest", "min", "minimum", "cheap", "cheapest")
        ask_worst = has_any("worst", "high", "highest", "max", "maximum", "expensive")

        if ask_total:
            add("Total Cost")
        if ask_best:
            add("Best Cost")
            if ask_distribution:
                add("Best Cost Distribution")
        if ask_worst:
            add("Worst Cost")
            if ask_distribution:
                add("Worst Cost Distribution")
        if ask_distribution and not (ask_best or ask_worst):
            add("Best Cost Distribution")
            add("Worst Cost Distribution")

    elif intent == "leads":
        ask_total = has_any("total", "all leads", "overall")
        ask_success = has_any("success", "successful", "won", "converted", "best")
        ask_failed = has_any("failed", "lost", "rejected", "worst")
        ask_on_hold = has_any("on hold", "pending", "in progress", "open")
        ask_analysis = has_any("analysis", "analyse", "summary", "overview", "breakdown")

        if ask_total:
            add("Total Leads")
        if ask_success:
            add("Successful Leads")
            if ask_distribution:
                add("Lead Distribution - Success")
        if ask_failed:
            add("Failed Leads")
            if ask_distribution:
                add("Lead Distribution - Failed")
        if ask_on_hold:
            add("On Hold Leads")
            if ask_distribution:
                add("Lead Distribution - On Hold")
        if ask_distribution and not (ask_success or ask_failed or ask_on_hold):
            add("Lead Distribution - Success")
            add("Lead Distribution - Failed")
            add("Lead Distribution - On Hold")
        if ask_analysis:
            add("Total Leads")
            add("Successful Leads")
            add("Failed Leads")
            add("On Hold Leads")
            add("Lead Distribution - Success")

    if not selected:
        if intent == "revenue":
            # Sensible revenue default for broad/ambiguous revenue questions.
            for default_name in ("Total Revenue", "Average Revenue", "Top Revenue", "Low Revenue", "Revenue Range"):
                add(default_name)
        if not selected:
            selected = [all_kpis[0]] if all_kpis else []

    return selected


def _build_revenue_charts(selected_kpis: List[Dict[str, Any]], all_kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build mandatory revenue charts (bar + pie) from numpy-computed KPI values.
    """
    def to_float(v: Any) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0

    bar_labels: List[str] = []
    bar_values: List[float] = []
    for k in selected_kpis:
        name = str(k.get("name", "")).strip()
        if not name:
            continue
        value = to_float(k.get("value", 0))
        if np.isfinite(value):
            bar_labels.append(name)
            bar_values.append(round(value, 2))
        if len(bar_labels) >= 5:
            break

    if not bar_labels:
        for k in all_kpis[:5]:
            bar_labels.append(str(k.get("name", "KPI")))
            bar_values.append(round(to_float(k.get("value", 0)), 2))

    by_name = {str(k.get("name", "")): k for k in all_kpis}
    top_dist = to_float((by_name.get("Top Revenue Distribution") or {}).get("value", 0))
    low_dist = to_float((by_name.get("Low Revenue Distribution") or {}).get("value", 0))
    pie_labels = ["Top Revenue Share", "Low Revenue Share"]
    pie_values = [round(top_dist, 2), round(low_dist, 2)]

    return [
        {
            "type": "bar",
            "title": "Revenue Comparison",
            "x_axis": bar_labels,
            "y_axis": bar_values,
            "insight": "Bar chart compares query-relevant revenue KPIs calculated via NumPy."
        },
        {
            "type": "pie",
            "title": "Revenue Distribution",
            "labels": pie_labels,
            "values": pie_values,
            "insight": "Pie chart shows top vs low revenue distribution based on exact row counts."
        }
    ]


def calculate_by_intent(intent: str, data: List[Dict[str, Any]], user_query: str = "") -> Dict[str, Any]:
    """
    Calculate metric using intent-specific formula engines and return dynamic KPI list
    based on the user query.
    """
    if intent == "revenue":
        df = pd.DataFrame(data)
        column = _detect_numeric_column_by_intent(df, "revenue")
        if not column:
            raise ValueError("Revenue column not found")
        entity_col, entity_label = _detect_entity_column_for_revenue(df, user_query)
        if entity_col and (
            _is_highest_entity_revenue_query(user_query)
            or _is_lowest_entity_revenue_query(user_query)
            or _is_entity_revenue_analysis_query(user_query)
        ):
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
            grouped = (
                df.groupby(entity_col, dropna=False)[column]
                .sum()
                .reset_index()
                .sort_values(column, ascending=False)
            )
            grouped[entity_col] = grouped[entity_col].astype(str).str.strip()
            if grouped.empty:
                raise ValueError("No entity rows found for revenue aggregation")

            top_entity = str(grouped.iloc[0][entity_col])
            top_total = float(round(float(grouped.iloc[0][column]), 2))
            low_entity = str(grouped.iloc[-1][entity_col])
            low_total = float(round(float(grouped.iloc[-1][column]), 2))
            overall_total = float(round(float(grouped[column].sum()), 2))
            owner_count = int(grouped.shape[0])

            q = (user_query or "").lower()
            need_high = _is_highest_entity_revenue_query(user_query)
            need_low = _is_lowest_entity_revenue_query(user_query)
            need_analysis = _is_entity_revenue_analysis_query(user_query)
            if not (need_high or need_low or need_analysis):
                need_analysis = True

            selected_kpis: List[Dict[str, Any]] = []
            if need_high or need_analysis:
                selected_kpis.extend([
                    {
                        "name": f"Top {entity_label or 'Entity'} Name",
                        "value": top_entity,
                        "unit": "name",
                        "insight": f"{top_entity} is the highest revenue {entity_label or 'entity'}."
                    },
                    {
                        "name": f"Top {entity_label or 'Entity'} Total Revenue",
                        "value": top_total,
                        "unit": "INR",
                        "insight": f"{top_entity} generated the highest aggregated revenue."
                    },
                ])
            if need_low or need_analysis:
                selected_kpis.extend([
                    {
                        "name": f"Lowest {entity_label or 'Entity'} Name",
                        "value": low_entity,
                        "unit": "name",
                        "insight": f"{low_entity} is the lowest revenue {entity_label or 'entity'}."
                    },
                    {
                        "name": f"Lowest {entity_label or 'Entity'} Total Revenue",
                        "value": low_total,
                        "unit": "INR",
                        "insight": f"{low_entity} generated the lowest aggregated revenue."
                    },
                ])
            # Keep entity responses rich (not a single KPI) for owner-focused questions.
            if need_high or need_low or need_analysis:
                selected_kpis.extend([
                    {
                        "name": "Total Revenue",
                        "value": overall_total,
                        "unit": "INR",
                        "insight": "Total revenue aggregated across all entities."
                    },
                    {
                        "name": f"Total {entity_label or 'Entity'} Count",
                        "value": owner_count,
                        "unit": "count",
                        "insight": f"Number of distinct {entity_label or 'entities'} in the dataset."
                    }
                ])

            metric_name = f"Top {entity_label or 'Entity'} ({top_entity}) Total Revenue"
            primary_value = top_total
            primary_unit = "INR"
            primary_entity_value = top_entity
            if need_low and not need_high and not need_analysis:
                metric_name = f"Lowest {entity_label or 'Entity'} ({low_entity}) Total Revenue"
                primary_value = low_total
                primary_entity_value = low_entity

            top5 = grouped.head(5)
            x_axis = [str(v) for v in top5[entity_col].tolist()]
            y_axis = [float(round(v, 2)) for v in top5[column].tolist()]
            others_total = float(round(float(grouped[column].sum()) - top_total, 2))
            charts = [
                {
                    "type": "bar",
                    "title": f"Top {entity_label or 'Entity'} Revenue",
                    "x_axis": x_axis,
                    "y_axis": y_axis,
                    "insight": f"Bar chart ranks {entity_label or 'entities'} by total revenue."
                },
                {
                    "type": "pie",
                    "title": f"{entity_label or 'Entity'} Revenue Share",
                    "labels": [top_entity, "Others"],
                    "values": [top_total, max(others_total, 0.0)],
                    "insight": f"Pie chart shows top {entity_label or 'entity'} contribution versus the rest."
                }
            ]

            return {
                "metric": metric_name,
                "value": primary_value,
                "unit": primary_unit,
                "value_column": column,
                "operation": "SUM",
                "kpis": selected_kpis,
                "charts": charts,
                "entity_column": entity_col,
                "entity_value": None if (need_high and need_low) or need_analysis else primary_entity_value,
                "all_kpis": selected_kpis,
                "extra_kpis": [],
            }
        cost_col = None
        qty_col = None
        for c in df.columns:
            c_norm = str(c).lower().strip()
            if cost_col is None and c_norm in {"cost", "cost_price", "cogs", "spend", "total_cost", "expense"}:
                cost_col = str(c)
            if qty_col is None and c_norm in {"quantity", "qty", "units", "unit", "unit_sold", "units_sold"}:
                qty_col = str(c)

        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
        metrics = calculate_all_revenue_metrics(df, column, cost_col=cost_col, quantity_col=qty_col)

        all_kpis = [
            {"name": "Total Revenue", "value": metrics["total_revenue"], "unit": "INR"},
            {"name": "Average Revenue", "value": metrics["average_revenue"], "unit": "INR"},
            {"name": "Median Revenue", "value": metrics["median_revenue"], "unit": "INR"},
            {"name": "Revenue Std Deviation", "value": metrics["std_deviation"], "unit": "INR"},
            {"name": "Revenue Variance", "value": metrics["variance"], "unit": "INR^2"},
            {"name": "Top Revenue", "value": metrics["top_revenue"], "unit": "INR"},
            {"name": "Low Revenue", "value": metrics["low_revenue"], "unit": "INR"},
            {"name": "Revenue Range", "value": metrics["revenue_range"], "unit": "INR"},
            {"name": "Top Revenue Distribution", "value": metrics["top_revenue_pct"], "unit": "%"},
            {"name": "Low Revenue Distribution", "value": metrics["low_revenue_pct"], "unit": "%"},
            {"name": "Above-Average Count", "value": metrics["above_avg_count"], "unit": "count"},
            {"name": "Below-Average Count", "value": metrics["below_avg_count"], "unit": "count"},
            {"name": "Revenue P25", "value": metrics["percentile_25"], "unit": "INR"},
            {"name": "Revenue P75", "value": metrics["percentile_75"], "unit": "INR"},
            {"name": "Revenue IQR", "value": metrics["iqr"], "unit": "INR"},
        ]
        if metrics.get("gross_profit") is not None:
            all_kpis.append({"name": "Gross Profit", "value": metrics["gross_profit"], "unit": "INR"})
        if metrics.get("gross_margin_pct") is not None:
            all_kpis.append({"name": "Gross Margin %", "value": metrics["gross_margin_pct"], "unit": "%"})
        if metrics.get("revenue_per_unit") is not None:
            all_kpis.append({"name": "Revenue per Unit", "value": metrics["revenue_per_unit"], "unit": "INR"})

        selected_kpis = _build_selected_kpis("revenue", user_query, all_kpis)
        primary = selected_kpis[0] if selected_kpis else all_kpis[0]
        name = str(primary.get("name", ""))
        if name == "Total Revenue" or name == "Gross Profit":
            op = "SUM"
        elif name == "Top Revenue":
            op = "MAX"
        elif name == "Low Revenue":
            op = "MIN"
        elif name == "Average Revenue":
            op = "MEAN"
        elif name == "Median Revenue":
            op = "MEDIAN"
        elif name == "Revenue Std Deviation":
            op = "STD"
        elif name == "Revenue Variance":
            op = "VAR"
        elif name == "Revenue Range":
            op = "RANGE"
        elif name == "Revenue P25":
            op = "P25"
        elif name == "Revenue P75":
            op = "P75"
        elif name == "Revenue IQR":
            op = "IQR"
        else:
            op = "COUNT"

        return {
            "metric": primary["name"],
            "value": primary["value"],
            "unit": primary["unit"],
            "value_column": column,
            "operation": op,
            "kpis": selected_kpis,
            "charts": _build_revenue_charts(selected_kpis, all_kpis),
            "all_kpis": all_kpis,
            "extra_kpis": [k for k in selected_kpis if k["name"] != primary["name"]],
        }

    if intent == "cost":
        df = pd.DataFrame(data)
        column = _detect_numeric_column_by_intent(df, "cost")
        if not column:
            raise ValueError("Cost column not found")
        values = pd.to_numeric(df[column], errors="coerce").fillna(0).to_numpy(dtype=float)

        total = float(np.sum(values))
        best_cost = float(np.min(values)) if values.size else 0.0
        worst_cost = float(np.max(values)) if values.size else 0.0
        best_count = int(np.sum(values == best_cost)) if values.size else 0
        worst_count = int(np.sum(values == worst_cost)) if values.size else 0
        best_pct = float(round((best_count / len(values) * 100), 2)) if len(values) else 0.0
        worst_pct = float(round((worst_count / len(values) * 100), 2)) if len(values) else 0.0

        all_kpis = [
            {"name": "Total Cost", "value": float(round(total, 2)), "unit": "INR"},
            {"name": "Best Cost", "value": float(round(best_cost, 2)), "unit": "INR"},
            {"name": "Worst Cost", "value": float(round(worst_cost, 2)), "unit": "INR"},
            {"name": "Best Cost Distribution", "value": best_pct, "unit": "%"},
            {"name": "Worst Cost Distribution", "value": worst_pct, "unit": "%"},
        ]
        selected_kpis = _build_selected_kpis("cost", user_query, all_kpis)
        primary = selected_kpis[0] if selected_kpis else all_kpis[0]

        return {
            "metric": primary["name"],
            "value": primary["value"],
            "unit": primary["unit"],
            "value_column": column,
            "operation": "SUM",
            "kpis": selected_kpis,
            "all_kpis": all_kpis,
            "extra_kpis": [k for k in selected_kpis if k["name"] != primary["name"]],
        }

    if intent == "leads":
        df = pd.DataFrame(data)
        entity_col, entity_label = _detect_entity_column_for_leads(df, user_query)
        if entity_col and (
            _is_highest_entity_leads_query(user_query)
            or _is_lowest_entity_leads_query(user_query)
            or _is_entity_leads_analysis_query(user_query)
        ):
            lead_count_col = _detect_leads_count_column(df)
            if lead_count_col:
                df[lead_count_col] = pd.to_numeric(df[lead_count_col], errors="coerce").fillna(0)
                grouped = (
                    df.groupby(entity_col, dropna=False)[lead_count_col]
                    .sum()
                    .reset_index()
                    .sort_values(lead_count_col, ascending=False)
                )
            else:
                grouped = (
                    df.groupby(entity_col, dropna=False)
                    .size()
                    .reset_index(name="lead_count")
                    .sort_values("lead_count", ascending=False)
                )
                lead_count_col = "lead_count"

            grouped[entity_col] = grouped[entity_col].astype(str).str.strip()
            if grouped.empty:
                raise ValueError("No entity rows found for leads aggregation")

            top_entity = str(grouped.iloc[0][entity_col])
            top_total = float(round(float(grouped.iloc[0][lead_count_col]), 2))
            low_entity = str(grouped.iloc[-1][entity_col])
            low_total = float(round(float(grouped.iloc[-1][lead_count_col]), 2))
            overall_total = float(round(float(grouped[lead_count_col].sum()), 2))
            entity_count = int(grouped.shape[0])

            need_high = _is_highest_entity_leads_query(user_query)
            need_low = _is_lowest_entity_leads_query(user_query)
            need_analysis = _is_entity_leads_analysis_query(user_query)
            if not (need_high or need_low or need_analysis):
                need_analysis = True

            selected_kpis: List[Dict[str, Any]] = []
            if need_high or need_analysis:
                selected_kpis.extend([
                    {
                        "name": f"Top {entity_label or 'Entity'} Name",
                        "value": top_entity,
                        "unit": "name",
                        "insight": f"{top_entity} has the highest number of leads."
                    },
                    {
                        "name": f"Top {entity_label or 'Entity'} Leads",
                        "value": top_total,
                        "unit": "count",
                        "insight": f"{top_entity} leads with the highest lead volume."
                    },
                ])
            if need_low or need_analysis:
                selected_kpis.extend([
                    {
                        "name": f"Lowest {entity_label or 'Entity'} Name",
                        "value": low_entity,
                        "unit": "name",
                        "insight": f"{low_entity} has the lowest number of leads."
                    },
                    {
                        "name": f"Lowest {entity_label or 'Entity'} Leads",
                        "value": low_total,
                        "unit": "count",
                        "insight": f"{low_entity} has the lowest lead volume."
                    },
                ])
            selected_kpis.extend([
                {
                    "name": "Total Leads",
                    "value": overall_total,
                    "unit": "count",
                    "insight": "Total leads across all entities."
                },
                {
                    "name": f"Total {entity_label or 'Entity'} Count",
                    "value": entity_count,
                    "unit": "count",
                    "insight": f"Number of distinct {entity_label or 'entities'} in the dataset."
                }
            ])

            metric_name = f"Top {entity_label or 'Entity'} ({top_entity}) Leads"
            primary_value = top_total
            primary_entity_value = top_entity
            if need_low and not need_high and not need_analysis:
                metric_name = f"Lowest {entity_label or 'Entity'} ({low_entity}) Leads"
                primary_value = low_total
                primary_entity_value = low_entity

            top5 = grouped.head(5)
            x_axis = [str(v) for v in top5[entity_col].tolist()]
            y_axis = [float(round(v, 2)) for v in top5[lead_count_col].tolist()]
            others_total = float(round(float(grouped[lead_count_col].sum()) - top_total, 2))
            charts = [
                {
                    "type": "bar",
                    "title": f"Top {entity_label or 'Entity'} Leads",
                    "x_axis": x_axis,
                    "y_axis": y_axis,
                    "insight": f"Ranks {entity_label or 'entities'} by lead volume."
                },
                {
                    "type": "pie",
                    "title": f"{entity_label or 'Entity'} Lead Share",
                    "labels": [top_entity, "Others"],
                    "values": [top_total, max(others_total, 0.0)],
                    "insight": f"Shows top {entity_label or 'entity'} share of total leads."
                }
            ]

            return {
                "metric": metric_name,
                "value": primary_value,
                "unit": "count",
                "value_column": entity_col,
                "operation": "COUNT",
                "kpis": selected_kpis,
                "charts": charts,
                "entity_column": entity_col,
                "entity_value": None if (need_high and need_low) or need_analysis else primary_entity_value,
                "all_kpis": selected_kpis,
                "extra_kpis": [],
            }

        leads_calc = _calculate_leads_metrics_numpy(data)
        all_kpis = [
            {"name": "Total Leads", "value": leads_calc["value"], "unit": "count"},
            *leads_calc.get("extra_kpis", []),
        ]
        selected_kpis = _build_selected_kpis("leads", user_query, all_kpis)
        primary = selected_kpis[0] if selected_kpis else all_kpis[0]

        leads_calc["metric"] = primary["name"]
        leads_calc["value"] = primary["value"]
        leads_calc["unit"] = primary["unit"]
        leads_calc["kpis"] = selected_kpis
        leads_calc["all_kpis"] = all_kpis
        leads_calc["extra_kpis"] = [k for k in selected_kpis if k["name"] != primary["name"]]
        leads_calc["operation"] = leads_calc.get("operation", "COUNT")
        leads_calc["charts"] = _build_leads_charts(user_query, selected_kpis, all_kpis)
        return leads_calc

    raise ValueError("Unsupported query")
