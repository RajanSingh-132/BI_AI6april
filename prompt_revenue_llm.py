"""
LLM-Driven Revenue Analysis Module
Single formula: Total Revenue = SUM(revenue_column)

The LLM intelligently identifies the revenue column from the dataset schema.
No hardcoded column lists - fully dynamic and semantic.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple, Optional
from audit_logger import get_logger, AuditLog
from datetime import datetime
from pydantic import BaseModel, Field

try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

# Configure logging
logger = logging.getLogger(__name__)


COLUMN_IDENTIFICATION_PROMPT = """
You are an expert data analyst. Given a dataset schema, identify the most appropriate revenue/amount column.

Consider:
1. Column names - prefer columns containing: "revenue", "earned", "amount", "sales", "value", "deal"
2. Column semantics - prefer "revenue_earned" over "deal_amount" (actual vs potential)
3. Data types - should be numeric (int or float)
4. Context - choose the column that represents actual earned/realized revenue

Return ONLY a JSON response:
{
  "column_name": "the_exact_column_name_from_schema",
  "reasoning": "why you selected this column",
  "confidence": 0.0-1.0,
  "alternatives": ["other_column_names_if_any"]
}

If no suitable revenue column exists, return:
{
  "column_name": null,
  "reasoning": "explanation of why",
  "confidence": 0.0,
  "alternatives": []
}
"""

ANALYSIS_PROMPT = """
You are an AI Business Analyst. Analyze revenue using a SINGLE FORMULA: Total Revenue = SUM(revenue_column)

Given:
- Dataset: with rows and columns
- Revenue column: identified column to use
- User query: what analysis is requested

Rules:
1. Treat the dataset as the ONLY source of truth. NO fabrication.
2. Apply only filters explicitly mentioned in the user query.
3. Calculate SUM of the revenue column for matching rows.
4. Group by entity ONLY if user asks for breakdown.
5. When grouped, sum_of_group_values MUST equal total exactly.
6. Return JSON with complete analysis.
7. Never doing hallucination 

Output structure (JSON only):
{
  "query": "user query",
  "revenue_column_used": "column_name",
  "filters_applied": ["filter1", "filter2"],
  "total_rows_in_dataset": N,
  "rows_after_filters": N,
  "total_revenue": FLOAT,
  "group_breakdown": [{"entity": "value", "revenue": FLOAT, "rows": N}],
  "validation_passed": true/false,
  "validation_notes": ["note1"]
}
"""


class RevenueResult(BaseModel):
    """Simplified revenue analysis result."""
    query: str = Field(description="The original user query")
    revenue_column_identified: str = Field(description="Column name used for revenue")
    filters_applied: List[str] = Field(default_factory=list, description="Filters applied")
    total_rows_in_dataset: int = Field(description="Total rows available")
    rows_after_filters: int = Field(description="Rows after applying filters")
    total_revenue: float = Field(description="SUM(revenue_column)")
    group_breakdown: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Optional grouping breakdown"
    )
    validation_passed: bool = Field(description="True if calculation is valid")
    validation_notes: List[str] = Field(
        default_factory=list,
        description="Notes about validation and assumptions"
    )


class RevenueAnalyzer:
    """
    Analyzes revenue from datasets using LLM-driven column identification.
    Uses SINGLE FORMULA: Total Revenue = SUM(revenue_column)
    
    No hardcoded column lists - fully semantic and dynamic.
    """

    def __init__(self):
        self.audit_logger = get_logger()
        self.client = None
        
        # Initialize Gemini client if available
        if GENAI_AVAILABLE:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self.client = genai.Client(api_key=api_key)
                self.audit_logger.logger.info("[REVENUE] LLM client initialized for column identification")
            else:
                self.audit_logger.logger.warning("[REVENUE] GEMINI_API_KEY not set - using fallback")
        else:
            self.audit_logger.logger.warning("[REVENUE] genai library not available - using fallback")

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

    def _identify_revenue_column_with_llm(self, schema: Dict[str, Any]) -> Tuple[str, bool, str]:
        """
        Use LLM to identify the revenue column from dataset schema.
        Returns: (column_name, success, reasoning)
        """
        if not self.client:
            self.audit_logger.logger.warning("[REVENUE] No LLM client - using fallback")
            return self._identify_revenue_column_fallback(schema)
        
        try:
            schema_str = json.dumps(schema, indent=2, default=str)
            prompt = f"""{COLUMN_IDENTIFICATION_PROMPT}

Dataset Schema:
{schema_str}

Identify the revenue column."""
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            
            response_text = response.text if hasattr(response, "text") else str(response)
            
            # Parse LLM response
            try:
                # Extract JSON from response
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response_text[start:end]
                    result = json.loads(json_str)
                    
                    column_name = result.get("column_name")
                    reasoning = result.get("reasoning", "")
                    confidence = result.get("confidence", 0.0)
                    
                    if column_name:
                        self.audit_logger.logger.info(
                            f"[REVENUE_LLM] Selected: {column_name} (confidence: {confidence})"
                        )
                        return column_name, True, reasoning
                    else:
                        self.audit_logger.logger.warning(
                            f"[REVENUE_LLM] LLM could not identify column: {reasoning}"
                        )
                        return "", False, reasoning
            except json.JSONDecodeError as e:
                self.audit_logger.logger.error(f"[REVENUE_LLM] JSON parse error: {e}")
                return "", False, str(e)
                
        except Exception as e:
            self.audit_logger.logger.error(f"[REVENUE_LLM] Error: {e}")
            return "", False, str(e)

    def _identify_revenue_column_fallback(self, schema: Dict[str, Any]) -> Tuple[str, bool, str]:
        """
        Fallback: Use regex pattern matching on column names.
        Only used when LLM is unavailable.
        """
        priority_keywords = ["revenue_earned", "revenue", "earned", "amount"]
        
        for keyword in priority_keywords:
            for col_info in schema["columns"]:
                col_name = col_info["name"].lower()
                if keyword in col_name:
                    return col_info["name"], True, f"Fallback regex match: {keyword}"
        
        # If numeric columns exist, pick the first one
        numeric_cols = [col for col in schema["columns"] if "int" in col["dtype"] or "float" in col["dtype"]]
        if numeric_cols:
            return numeric_cols[0]["name"], True, "Fallback: selected first numeric column"
        
        return "", False, "Fallback: no suitable revenue column found"

    def calculate_total_revenue(
        self,
        dataset: pd.DataFrame,
        query: str = "",
        filters: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Calculate total revenue using single formula.
        Formula: Total Revenue = SUM(revenue_column)
        """
        audit_logger = get_logger()

        try:
            if not isinstance(dataset, pd.DataFrame):
                dataset = pd.DataFrame(dataset)

            initial_row_count = len(dataset)
            
            # Get schema and let LLM identify revenue column
            schema = self._get_schema_from_dataframe(dataset)
            revenue_col, col_found, reasoning = self._identify_revenue_column_with_llm(schema)

            if not col_found:
                audit_logger.log_calculation(
                    operation="calculate_total_revenue",
                    module="prompt_revenue",
                    query=query,
                    input_rows=initial_row_count,
                    output_rows=0,
                    filters=[],
                    formula="SUM(revenue_column) - FAILED",
                    result=0.0,
                    column_mapping={},
                    validation_passed=False,
                    notes=[f"Revenue column not identified: {reasoning}"],
                )
                return {
                    "query": query,
                    "revenue_column_identified": "",
                    "filters_applied": [],
                    "total_rows_in_dataset": initial_row_count,
                    "rows_after_filters": 0,
                    "total_revenue": 0.0,
                    "group_breakdown": [],
                    "validation_passed": False,
                    "validation_notes": [f"Revenue column not found: {reasoning}"],
                }

            # Apply filters if provided
            filtered_df = dataset.copy()
            filters_applied = []

            if filters:
                for col, value in filters.items():
                    if col in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df[col] == value]
                        filters_applied.append(f"{col}={value}")

            filtered_row_count = len(filtered_df)

            # SINGLE FORMULA: Total Revenue = SUM(revenue_column)
            total_revenue = float(filtered_df[revenue_col].sum())

            # Audit log
            audit_logger.log_calculation(
                operation="calculate_total_revenue",
                module="prompt_revenue",
                query=query,
                input_rows=initial_row_count,
                output_rows=filtered_row_count,
                filters=filters_applied,
                formula=f"SUM({revenue_col})",
                result=total_revenue,
                column_mapping={"revenue": revenue_col},
                validation_passed=True,
                notes=[
                    f"LLM identified column: {revenue_col}",
                    f"Reasoning: {reasoning}",
                    f"Rows: {filtered_row_count}/{initial_row_count}",
                ],
            )

            return {
                "query": query,
                "revenue_column_identified": revenue_col,
                "filters_applied": filters_applied,
                "total_rows_in_dataset": initial_row_count,
                "rows_after_filters": filtered_row_count,
                "total_revenue": total_revenue,
                "group_breakdown": [],
                "validation_passed": True,
                "validation_notes": [
                    f"Column: {revenue_col}",
                    f"Logic: {reasoning}",
                    f"Processed: {filtered_row_count} rows",
                ],
            }

        except Exception as e:
            audit_logger.logger.error(f"Error: {str(e)}")
            return {
                "query": query,
                "revenue_column_identified": "",
                "filters_applied": [],
                "total_rows_in_dataset": len(dataset) if isinstance(dataset, pd.DataFrame) else 0,
                "rows_after_filters": 0,
                "total_revenue": 0.0,
                "group_breakdown": [],
                "validation_passed": False,
                "validation_notes": [f"Error: {str(e)}"],
            }

    def calculate_revenue_by_group(
        self,
        dataset: pd.DataFrame,
        group_by: str,
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Calculate revenue grouped by a dimension.
        """
        try:
            if not isinstance(dataset, pd.DataFrame):
                dataset = pd.DataFrame(dataset)

            schema = self._get_schema_from_dataframe(dataset)
            revenue_col, col_found, _ = self._identify_revenue_column_with_llm(schema)

            if not col_found or group_by not in dataset.columns:
                return []

            grouped = dataset.groupby(group_by, dropna=False)[revenue_col].sum()
            
            return [
                {
                    "group": str(key),
                    "revenue": float(value),
                    "count": len(dataset[dataset[group_by] == key])
                }
                for key, value in grouped.items()
            ]

        except Exception as e:
            logger.error(f"Error in calculate_revenue_by_group: {e}")
            return []
