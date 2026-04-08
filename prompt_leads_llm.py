"""
LLM-Driven Leads Analysis Module
Single formula: Total Leads = COUNT(lead_records)

The LLM intelligently identifies the lead ID or count column from the dataset schema.
No hardcoded column lists - fully dynamic and semantic.
"""

import logging
import os
from typing import Any, Dict, List, Tuple
from audit_logger import get_logger
import json

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    import pandas as pd
except ImportError:
    pd = None

logger = logging.getLogger(__name__)


LEAD_COLUMN_IDENTIFICATION_PROMPT = """
You are an expert data analyst. Given a dataset schema, identify how to count leads.

Options:
1. Find a lead ID column (lead_id, id, etc.) - count distinct/total values
2. Count total rows if each row = one lead

Consider:
1. Column names - look for: "lead_id", "id", "lead_name", "lead", "customer", "record"
2. Context - in lead/sales datasets, rows typically represent individual leads
3. Return the best column for counting leads

Return ONLY a JSON response:
{
  "count_method": "column_name_or_row_count",
  "reasoning": "why you selected this method",
  "is_row_count": true/false,
  "confidence": 0.0-1.0
}

Examples:
- If dataset has 'lead_id': {"count_method": "lead_id", "is_row_count": false, ...}
- If each row is a lead: {"count_method": "row_count", "is_row_count": true, ...}
"""

LEADS_ANALYSIS_PROMPT = """
You are an AI Business Analyst. Analyze leads using: Total Leads = COUNT(leads)

Given:
- Dataset: with rows and columns
- Count method: how to identify/count leads
- User query: what analysis is requested

Rules:
1. Treat dataset as the ONLY source of truth. NO fabrication.
2. Apply filters explicitly mentioned in the user query.
3. Count total leads matching criteria.
4. Group by entity ONLY if user asks for breakdown.
5. Return JSON with complete analysis.
6. Never doing hallucination.

Output (JSON only):
{
  "query": "user query",
  "count_method": "how_counted",
  "filters_applied": ["filter1"],
  "total_leads_in_dataset": N,
  "leads_after_filters": N,
  "group_breakdown": [{"entity": "value", "lead_count": N}],
  "validation_passed": true/false,
  "validation_notes": []
}
"""


class LeadsAnalyzer:
    """
    Analyzes leads from datasets using LLM-driven column identification.
    Uses SINGLE FORMULA: Total Leads = COUNT(leads)
    
    No hardcoded column lists - fully semantic and dynamic.
    """

    def __init__(self):
        self.audit_logger = get_logger()
        self.client = None
        
        if GENAI_AVAILABLE:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self.client = genai.Client(api_key=api_key)
                self.audit_logger.logger.info("[LEADS] LLM client initialized")
            else:
                self.audit_logger.logger.warning("[LEADS] GEMINI_API_KEY not set")
        else:
            self.audit_logger.logger.warning("[LEADS] genai library not available")

    def _get_schema_from_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract dataset schema for LLM analysis."""
        schema = {
            "total_rows": len(df),
            "columns": []
        }
        
        for col in df.columns:
            col_info = {
                "name": col,
                "dtype": str(df[col].dtype),
                "sample_values": df[col].head(3).tolist()
            }
            schema["columns"].append(col_info)
        
        return schema

    def _identify_lead_column_with_llm(self, schema: Dict[str, Any]) -> Tuple[str, bool, bool, str]:
        """
        Use LLM to identify how to count leads from dataset schema.
        Returns: (column_name_or_method, success, is_row_count, reasoning)
        """
        if not self.client:
            return self._identify_lead_column_fallback(schema)
        
        try:
            schema_str = json.dumps(schema, indent=2, default=str)
            prompt = f"""{LEAD_COLUMN_IDENTIFICATION_PROMPT}

Dataset Schema:
{schema_str}

Identify how to count leads."""
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            
            response_text = response.text if hasattr(response, "text") else str(response)
            
            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response_text[start:end]
                    result = json.loads(json_str)
                    
                    count_method = result.get("count_method")
                    is_row_count = result.get("is_row_count", False)
                    reasoning = result.get("reasoning", "")
                    
                    if count_method:
                        self.audit_logger.logger.info(
                            f"[LEADS_LLM] Selected: {count_method} (row_count={is_row_count})"
                        )
                        return count_method, True, is_row_count, reasoning
                    
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            self.audit_logger.logger.error(f"[LEADS_LLM] Error: {e}")
        
        return self._identify_lead_column_fallback(schema)

    def _identify_lead_column_fallback(self, schema: Dict[str, Any]) -> Tuple[str, bool, bool, str]:
        """
        Fallback: Use regex on column names or default to row counting.
        """
        lead_keywords = ["lead_id", "lead", "id", "customer", "record"]
        
        for keyword in lead_keywords:
            for col_info in schema["columns"]:
                if keyword in col_info["name"].lower():
                    return col_info["name"], True, False, f"Fallback regex match: {keyword}"
        
        # Default to row counting
        return "row_count", True, True, "Fallback: counting total rows as leads"

    def calculate_total_leads(
        self,
        dataset: pd.DataFrame,
        query: str = "",
        filters: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Calculate total leads using single formula.
        Formula: Total Leads = COUNT(leads)
        """
        audit_logger = get_logger()

        try:
            if not isinstance(dataset, pd.DataFrame):
                dataset = pd.DataFrame(dataset)

            initial_row_count = len(dataset)
            
            schema = self._get_schema_from_dataframe(dataset)
            count_method, col_found, is_row_count, reasoning = self._identify_lead_column_with_llm(schema)

            if not col_found:
                return {
                    "query": query,
                    "lead_id_column": "",
                    "filters_applied": [],
                    "total_leads_in_dataset": initial_row_count,
                    "leads_after_filters": 0,
                    "group_breakdown": [],
                    "validation_passed": False,
                    "validation_notes": [f"Lead column not found: {reasoning}"],
                }

            # Apply filters
            filtered_df = dataset.copy()
            filters_applied = []

            if filters:
                for col, value in filters.items():
                    if col in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df[col] == value]
                        filters_applied.append(f"{col}={value}")

            filtered_row_count = len(filtered_df)

            # COUNT: Total Leads = COUNT(leads)
            if is_row_count:
                total_leads = filtered_row_count
            else:
                total_leads = filtered_df[count_method].nunique()

            # Audit log
            audit_logger.log_calculation(
                operation="calculate_total_leads",
                module="prompt_leads",
                query=query,
                input_rows=initial_row_count,
                output_rows=filtered_row_count,
                filters=filters_applied,
                formula=f"COUNT({count_method})",
                result=float(total_leads),
                column_mapping={"lead_id": count_method},
                validation_passed=True,
                notes=[
                    f"LLM identified method: {count_method}",
                    f"Reasoning: {reasoning}",
                    f"Rows: {filtered_row_count}/{initial_row_count}",
                ],
            )

            return {
                "query": query,
                "lead_id_column": count_method,
                "filters_applied": filters_applied,
                "total_leads_in_dataset": initial_row_count,
                "leads_after_filters": filtered_row_count,
                "total_leads": total_leads,
                "group_breakdown": [],
                "validation_passed": True,
                "validation_notes": [
                    f"Method: {count_method}",
                    f"Logic: {reasoning}",
                    f"Counted: {total_leads} leads",
                ],
            }

        except Exception as e:
            audit_logger.logger.error(f"Error: {str(e)}")
            return {
                "query": query,
                "lead_id_column": "",
                "filters_applied": [],
                "total_leads_in_dataset": len(dataset) if isinstance(dataset, pd.DataFrame) else 0,
                "leads_after_filters": 0,
                "total_leads": 0,
                "group_breakdown": [],
                "validation_passed": False,
                "validation_notes": [f"Error: {str(e)}"],
            }

    def calculate_leads_by_group(
        self,
        dataset: pd.DataFrame,
        group_by: str,
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Calculate leads grouped by a dimension.
        """
        try:
            if not isinstance(dataset, pd.DataFrame):
                dataset = pd.DataFrame(dataset)

            schema = self._get_schema_from_dataframe(dataset)
            count_method, col_found, is_row_count, _ = self._identify_lead_column_with_llm(schema)

            if not col_found or group_by not in dataset.columns:
                return []

            grouped = dataset.groupby(group_by, dropna=False)
            
            results = []
            for key, group_df in grouped:
                if is_row_count:
                    count = len(group_df)
                else:
                    count = group_df[count_method].nunique()
                
                results.append({
                    "group": str(key),
                    "lead_count": count,
                    "rows": len(group_df)
                })
            
            return results

        except Exception as e:
            logger.error(f"Error in calculate_leads_by_group: {e}")
            return []
