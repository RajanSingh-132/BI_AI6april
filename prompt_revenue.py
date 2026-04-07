"""
SIMPLIFIED Revenue Analysis Module
Single formula: Total Revenue = SUM(revenue_column)
Comprehensive audit logging for full trail.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple
from audit_logger import get_logger, AuditLog
from datetime import datetime
from pydantic import BaseModel, Field

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

SYSTEM_PROMPT = """
You are an AI Business Analyst focused on REVENUE ANALYSIS using a SINGLE, SIMPLE FORMULA.

FORMULA: Total Revenue = SUM(deal_value_or_revenue_column)

Rules:
1. Treat the dataset as the ONLY source of truth. NO fabrication.
2. Identify the revenue column (Deal_Value, revenue, amount, or similar).
3. Apply only filters explicitly mentioned in the user query.
4. Return SUM of all revenue values from matching rows.
5. Group by entity (e.g., Lead_Source, Owner, Industry) ONLY if user asks for breakdown.
6. When grouped, sum_of_group_values MUST equal total_dataset_value exactly.
7. row_count_lock must match the actual number of rows used.
8. If a required column is missing, set validation_passed=false.

Output structure (JSON only):
{
  "query": "user query",
  "revenue_column_identified": "column_name",
  "filters_applied": ["filter1", "filter2"],
  "total_rows_in_dataset": N,
  "rows_after_filters": N,
  "total_revenue": FLOAT,
  "group_breakdown": [{"entity": "value", "entity_name": "name", "revenue": FLOAT, "rows": N}],
  "validation_passed": true/false,
  "validation_notes": ["note1"]
}
"""


CORRECTION_SYSTEM_PROMPT = """
You are correcting a failed revenue analysis using the SAME SIMPLE FORMULA.

Formula: Total Revenue = SUM(revenue_column)

Recalculate:
1. Identify the revenue column correctly.
2. Apply all filters from the original query.
3. Sum the revenue values.
4. Return corrected JSON only.
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


def serialize_dataset(dataset: Any) -> str:
    """Convert dataset to JSON string for LLM prompt."""
    if dataset is None:
        return ""

    if isinstance(dataset, str):
        return dataset

    if pd is not None and isinstance(dataset, pd.DataFrame):
        return json.dumps(dataset.to_dict(orient="records"), indent=2, default=str)

    if isinstance(dataset, (list, dict)):
        return json.dumps(dataset, indent=2, default=str)

    return str(dataset)


class RevenueAnalyzer:
    """
    Analyzes revenue from datasets.
    Uses SINGLE FORMULA: Total Revenue = SUM(revenue_column)
    """

    # Priority order: prefer "revenue_earned" over "deal_amount"
    # This ensures actual earned revenue is used instead of deal potential
    REVENUE_COLUMNS = [
        "revenue_earned",  # Actual revenue earned (highest priority)
        "revenue",         # Generic revenue column
        "sales_revenue",   # Sales revenue
        "amount_earned",   # Amount earned
        "Deal_Value",      # Salesforce deal value
        "deal_value",
        "deal_amount",     # Deal amount (potential, not earned)
        "amount",
        "sales",
        "total",
        "value",
    ]

    def __init__(self):
        self.audit_logger = get_logger()

    def _identify_revenue_column(self, df: pd.DataFrame) -> Tuple[str, bool]:
        """
        Identify which column contains revenue data.
        Uses priority-based matching:
        1. Exact match (case-insensitive)
        2. Substring match (case-insensitive) - matches columns containing the keyword
        """
        if not isinstance(df, pd.DataFrame):
            return "", False

        df_columns = [c.lower() for c in df.columns]

        # PASS 1: Exact match
        for col in self.REVENUE_COLUMNS:
            col_lower = col.lower()
            if col_lower in df_columns:
                # Find the original column name with correct casing
                matching_col = [c for c in df.columns if c.lower() == col_lower][0]
                self.audit_logger.logger.info(
                    f"[REVENUE_COL] Exact match found: {col_lower} → {matching_col}"
                )
                return matching_col, True

        # PASS 2: Substring match (higher priority columns first)
        for col in self.REVENUE_COLUMNS:
            col_lower = col.lower()
            for df_col in df_columns:
                if col_lower in df_col:
                    # Find the original column name with correct casing
                    matching_col = [c for c in df.columns if c.lower() == df_col][0]
                    self.audit_logger.logger.info(
                        f"[REVENUE_COL] Substring match found: {col_lower} in {df_col} → {matching_col}"
                    )
                    return matching_col, True

        return "", False

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
            revenue_col, col_found = self._identify_revenue_column(dataset)

            if not col_found:
                audit_logger.log_calculation(
                    operation="calculate_total_revenue",
                    module="prompt_revenue",
                    query=query,
                    input_rows=initial_row_count,
                    output_rows=0,
                    filters=[],
                    formula="SUM(revenue_column) - FAILED: Column not found",
                    result=0.0,
                    column_mapping={},
                    validation_passed=False,
                    notes=["Revenue column not identified in dataset"],
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
                    "validation_notes": ["Revenue column not found in dataset"],
                }

            # Audit log: column identification
            audit_logger.logger.info(
                f"[OK] Revenue column identified: {revenue_col}"
            )

            # Apply filters if provided
            filtered_df = dataset.copy()
            filters_applied = []

            if filters:
                for col, value in filters.items():
                    if col in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df[col] == value]
                        filters_applied.append(f"{col}={value}")
                        audit_logger.logger.info(f"[FILTER] Applied: {col}={value}")

            filtered_row_count = len(filtered_df)

            # SINGLE FORMULA: Total Revenue = SUM(revenue_column)
            total_revenue = float(filtered_df[revenue_col].sum())

            # Audit log: calculation
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
                    f"Formula: Total Revenue = SUM({revenue_col})",
                    f"Rows used: {filtered_row_count}",
                    f"Total: {total_revenue}",
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
                    f"Used column: {revenue_col}",
                    f"Rows processed: {filtered_row_count} / {initial_row_count}",
                ],
            }

        except Exception as e:
            audit_logger.logger.error(f"Error in calculate_total_revenue: {str(e)}")
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
        filters: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Calculate revenue grouped by entity.
        Formula: Revenue per group = SUM(revenue_column) where group_by = value
        """
        audit_logger = get_logger()

        try:
            if not isinstance(dataset, pd.DataFrame):
                dataset = pd.DataFrame(dataset)

            initial_row_count = len(dataset)
            revenue_col, col_found = self._identify_revenue_column(dataset)

            if not col_found:
                return {
                    "query": query,
                    "revenue_column_identified": "",
                    "filters_applied": [],
                    "total_rows_in_dataset": initial_row_count,
                    "rows_after_filters": 0,
                    "total_revenue": 0.0,
                    "group_breakdown": [],
                    "validation_passed": False,
                    "validation_notes": ["Revenue column not found"],
                }

            # Find matching column name case-insensitively
            matching_group_col = None
            for col in dataset.columns:
                if col.lower() == group_by.lower():
                    matching_group_col = col
                    break
            
            if not matching_group_col:
                return {
                    "query": query,
                    "revenue_column_identified": revenue_col,
                    "filters_applied": [],
                    "total_rows_in_dataset": initial_row_count,
                    "rows_after_filters": 0,
                    "total_revenue": 0.0,
                    "group_breakdown": [],
                    "validation_passed": False,
                    "validation_notes": [f"Group column '{group_by}' not found"],
                }

            filtered_df = dataset.copy()
            filters_applied = []

            if filters:
                for col, value in filters.items():
                    if col in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df[col] == value]
                        filters_applied.append(f"{col}={value}")

            filtered_row_count = len(filtered_df)
            total_revenue = float(filtered_df[revenue_col].sum())

            # Group by entity and sum revenue
            group_results = []
            grouped = filtered_df.groupby(matching_group_col)[revenue_col].agg(["sum", "count"])

            for group_value, row in grouped.iterrows():
                group_results.append({
                    "entity": matching_group_col,
                    "entity_name": str(group_value),
                    "revenue": float(row["sum"]),
                    "rows": int(row["count"]),
                })

                audit_logger.logger.info(
                    f"[GROUP] {matching_group_col}={group_value}, Revenue={row['sum']}, Rows={row['count']}"
                )

            # Validate: sum of groups = total
            sum_of_groups = sum(g["revenue"] for g in group_results)
            validation_passed = abs(sum_of_groups - total_revenue) < 0.01

            audit_logger.log_calculation(
                operation="calculate_revenue_by_group",
                module="prompt_revenue",
                query=query,
                input_rows=initial_row_count,
                output_rows=len(group_results),
                filters=filters_applied + [f"group_by={matching_group_col}"],
                formula=f"SUM({revenue_col}) GROUP BY {matching_group_col}",
                result=total_revenue,
                column_mapping={"revenue": revenue_col, "group": matching_group_col},
                validation_passed=validation_passed,
                notes=[
                    f"Total revenue: {total_revenue}",
                    f"Number of groups: {len(group_results)}",
                    f"Sum of groups: {sum_of_groups}",
                ],
            )

            return {
                "query": query,
                "revenue_column_identified": revenue_col,
                "filters_applied": filters_applied,
                "total_rows_in_dataset": initial_row_count,
                "rows_after_filters": filtered_row_count,
                "total_revenue": total_revenue,
                "group_breakdown": group_results,
                "validation_passed": validation_passed,
                "validation_notes": [
                    f"Grouped by: {matching_group_col}",
                    f"Number of groups: {len(group_results)}",
                    f"Total rows: {filtered_row_count}",
                ] + ([] if validation_passed else [f"Reconciliation: {sum_of_groups} vs {total_revenue}"]),
            }

        except Exception as e:
            audit_logger.logger.error(f"Error in calculate_revenue_by_group: {str(e)}")
            return {
                "query": query,
                "revenue_column_identified": "",
                "filters_applied": [],
                "total_rows_in_dataset": 0,
                "rows_after_filters": 0,
                "total_revenue": 0.0,
                "group_breakdown": [],
                "validation_passed": False,
                "validation_notes": [f"Error: {str(e)}"],
            }


# Legacy compatibility - keep for backward compatibility
def total_revenue(context: dict[str, Any]) -> Any:
    """Legacy: Get total revenue from context."""
    return context.get("revenue")


def revenue_per_click(context: dict[str, Any]) -> float | None:
    """Legacy: Calculate revenue per click."""
    revenue = context.get("revenue")
    clicks = context.get("clicks")
    if not clicks:
        return None
    return round(revenue / clicks, 2)


def roas(context: dict[str, Any]) -> float | None:
    """Legacy: Calculate ROAS."""
    revenue = context.get("revenue")
    cost = context.get("cost")
    if not cost:
        return None
    return round(revenue / cost, 2)


def revenue_per_user(context: dict[str, Any]) -> float | None:
    """Legacy: Calculate revenue per user."""
    revenue = context.get("revenue")
    users = context.get("users")
    if not users:
        return None
    return round(revenue / users, 2)


def revenue_contribution(
    context: dict[str, Any],
    global_context: dict[str, Any],
) -> float | None:
    """Legacy: Calculate revenue contribution percentage."""
    revenue = context.get("revenue")
    global_revenue = global_context.get("revenue")
    if not global_revenue:
        return None
    return round((revenue / global_revenue) * 100, 2)


__all__ = [
    "RevenueAnalyzer",
    "RevenueResult",
    "SYSTEM_PROMPT",
    "serialize_dataset",
    "total_revenue",
    "revenue_per_click",
    "roas",
    "revenue_per_user",
    "revenue_contribution",
]

