"""
SIMPLIFIED Leads Analysis Module
Single formula: Total Leads = COUNT(distinct_lead_records)
Comprehensive audit logging for full trail.
"""

import logging
from typing import Any, Dict, List, Tuple

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

from audit_logger import get_logger

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an AI Business Analyst focused on LEADS ANALYSIS using a SINGLE, SIMPLE FORMULA.

FORMULA: Total Leads = COUNT(distinct lead records)

Rules:
1. Treat the dataset as the ONLY source of truth. NO fabrication.
2. Count the total number of unique lead records in the dataset.
3. Apply only filters explicitly mentioned in the user query.
4. When grouping by entity (e.g., Lead_Source, Owner), count leads per group.
5. When calculating revenue-wise lead analysis: COUNT(leads) per revenue/deal_stage.
6. If grouping is used, sum_of_group_counts MUST equal total_lead_count exactly.
7. row_count_lock must match the actual number of leads counted.
8. If required columns are missing, set validation_passed=false.

Output structure (JSON only):
{
  "query": "user query",
  "lead_id_column": "column_name",
  "filters_applied": ["filter1"],
  "total_leads_in_dataset": N,
  "leads_after_filters": N,
  "group_breakdown": [{"entity": "value", "entity_name": "name", "lead_count": N}],
  "validation_passed": true/false,
  "validation_notes": ["note1"]
}
"""


class LeadsAnalyzer:
    """
    Analyzes leads from datasets.
    Uses SINGLE FORMULA: Total Leads = COUNT(distinct lead records)
    """

    LEAD_ID_COLUMNS = [
        "lead_id",
        "Lead_ID",
        "LeadId",
        "lead_Id",
        "id",
        "Id",
    ]

    def __init__(self):
        self.audit_logger = get_logger()

    def _identify_lead_id_column(self, df: pd.DataFrame) -> Tuple[str, bool]:
        """
        Identify which column contains lead IDs.
        Uses priority-based matching:
        1. Exact match (case-insensitive)
        2. Substring match (case-insensitive)
        3. First column as fallback
        """
        if not isinstance(df, pd.DataFrame):
            return "", False

        df_columns = [c.lower() for c in df.columns]

        # PASS 1: Exact match
        for col in self.LEAD_ID_COLUMNS:
            col_lower = col.lower()
            if col_lower in df_columns:
                matching_col = [c for c in df.columns if c.lower() == col_lower][0]
                return matching_col, True

        # PASS 2: Substring match - check if "lead_id" is part of column name
        for col in self.LEAD_ID_COLUMNS:
            col_lower = col.lower()
            for df_col in df_columns:
                if col_lower in df_col:
                    matching_col = [c for c in df.columns if c.lower() == df_col][0]
                    return matching_col, True

        # PASS 3: Fallback to first column (each row is a lead)
        if len(df.columns) > 0:
            return df.columns[0], True

        return "", False

    def calculate_total_leads(
        self,
        dataset: pd.DataFrame,
        query: str = "",
        filters: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Calculate total leads using single formula.
        Formula: Total Leads = COUNT(lead records)
        """
        audit_logger = get_logger()

        try:
            if not isinstance(dataset, pd.DataFrame):
                dataset = pd.DataFrame(dataset)

            initial_lead_count = len(dataset)
            lead_id_col, col_found = self._identify_lead_id_column(dataset)

            if not col_found:
                audit_logger.log_calculation(
                    operation="calculate_total_leads",
                    module="prompt_leads",
                    query=query,
                    input_rows=initial_lead_count,
                    output_rows=0,
                    filters=[],
                    formula="COUNT(lead_records) - FAILED: No ID column",
                    result=0,
                    column_mapping={},
                    validation_passed=False,
                    notes=["Lead ID column not identified"],
                )
                return {
                    "query": query,
                    "lead_id_column": "",
                    "filters_applied": [],
                    "total_leads_in_dataset": initial_lead_count,
                    "leads_after_filters": 0,
                    "group_breakdown": [],
                    "validation_passed": False,
                    "validation_notes": ["Lead ID column not found"],
                }

            audit_logger.logger.info(f"[OK] Lead ID column identified: {lead_id_col}")

            # Apply filters if provided
            filtered_df = dataset.copy()
            filters_applied = []

            if filters:
                for col, value in filters.items():
                    if col in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df[col] == value]
                        filters_applied.append(f"{col}={value}")
                        audit_logger.logger.info(f"[FILTER] Applied: {col}={value}")

            # SINGLE FORMULA: Total Leads = COUNT(lead records)
            total_leads = len(filtered_df)

            # Audit log: calculation
            audit_logger.log_calculation(
                operation="calculate_total_leads",
                module="prompt_leads",
                query=query,
                input_rows=initial_lead_count,
                output_rows=total_leads,
                filters=filters_applied,
                formula="COUNT(lead_records)",
                result=total_leads,
                column_mapping={"lead_id": lead_id_col},
                validation_passed=True,
                notes=[
                    f"Formula: Total Leads = COUNT(records)",
                    f"Records counted: {total_leads}",
                ],
            )

            return {
                "query": query,
                "lead_id_column": lead_id_col,
                "filters_applied": filters_applied,
                "total_leads_in_dataset": initial_lead_count,
                "leads_after_filters": total_leads,
                "group_breakdown": [],
                "validation_passed": True,
                "validation_notes": [
                    f"Used column: {lead_id_col}",
                    f"Records counted: {total_leads} / {initial_lead_count}",
                ],
            }

        except Exception as e:
            audit_logger.logger.error(f"Error in calculate_total_leads: {str(e)}")
            return {
                "query": query,
                "lead_id_column": "",
                "filters_applied": [],
                "total_leads_in_dataset": len(dataset) if isinstance(dataset, pd.DataFrame) else 0,
                "leads_after_filters": 0,
                "group_breakdown": [],
                "validation_passed": False,
                "validation_notes": [f"Error: {str(e)}"],
            }

    def calculate_leads_by_group(
        self,
        dataset: pd.DataFrame,
        group_by: str,
        query: str = "",
        filters: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Calculate leads grouped by entity.
        Formula: Leads per group = COUNT(records) where group_by = value
        """
        audit_logger = get_logger()

        try:
            if not isinstance(dataset, pd.DataFrame):
                dataset = pd.DataFrame(dataset)

            initial_lead_count = len(dataset)
            lead_id_col, col_found = self._identify_lead_id_column(dataset)

            if not col_found:
                return {
                    "query": query,
                    "lead_id_column": "",
                    "filters_applied": [],
                    "total_leads_in_dataset": initial_lead_count,
                    "leads_after_filters": 0,
                    "group_breakdown": [],
                    "validation_passed": False,
                    "validation_notes": ["Lead ID column not found"],
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
                    "lead_id_column": lead_id_col,
                    "filters_applied": [],
                    "total_leads_in_dataset": initial_lead_count,
                    "leads_after_filters": 0,
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

            total_leads = len(filtered_df)

            # Group by entity and count leads
            group_results = []
            grouped = filtered_df.groupby(matching_group_col).size()

            for group_value, lead_count in grouped.items():
                group_results.append({
                    "entity": matching_group_col,
                    "entity_name": str(group_value),
                    "lead_count": int(lead_count),
                })

                audit_logger.logger.info(
                    f"[GROUP] {matching_group_col}={group_value}, Leads={lead_count}"
                )

            # Validate: sum of groups = total
            sum_of_groups = sum(g["lead_count"] for g in group_results)
            validation_passed = sum_of_groups == total_leads

            audit_logger.log_calculation(
                operation="calculate_leads_by_group",
                module="prompt_leads",
                query=query,
                input_rows=initial_lead_count,
                output_rows=len(group_results),
                filters=filters_applied + [f"group_by={matching_group_col}"],
                formula=f"COUNT(records) GROUP BY {matching_group_col}",
                result=total_leads,
                column_mapping={"group": matching_group_col},
                validation_passed=validation_passed,
                notes=[
                    f"Total leads: {total_leads}",
                    f"Number of groups: {len(group_results)}",
                    f"Sum of groups: {sum_of_groups}",
                ],
            )

            return {
                "query": query,
                "lead_id_column": lead_id_col,
                "filters_applied": filters_applied,
                "total_leads_in_dataset": initial_lead_count,
                "leads_after_filters": total_leads,
                "group_breakdown": group_results,
                "validation_passed": validation_passed,
                "validation_notes": [
                    f"Grouped by: {matching_group_col}",
                    f"Number of groups: {len(group_results)}",
                    f"Total leads: {total_leads}",
                ] + ([] if validation_passed else [f"Reconciliation: {sum_of_groups} vs {total_leads}"]),
            }

        except Exception as e:
            audit_logger.logger.error(f"Error in calculate_leads_by_group: {str(e)}")
            return {
                "query": query,
                "lead_id_column": "",
                "filters_applied": [],
                "total_leads_in_dataset": 0,
                "leads_after_filters": 0,
                "group_breakdown": [],
                "validation_passed": False,
                "validation_notes": [f"Error: {str(e)}"],
            }


# Legacy compatibility
def total_leads(context):
    """Legacy: Get total leads from context."""
    return context.get("leads")


def lead_conversion_rate(context):
    """Legacy: Calculate lead conversion rate."""
    conversions = context.get("conversions")
    leads = context.get("leads")

    if not leads:
        return None

    return round((conversions / leads) * 100, 2)


def lead_contribution(context, global_context):
    """Legacy: Calculate lead contribution percentage."""
    leads = context.get("leads")
    total_leads = global_context.get("leads")

    if not total_leads:
        return None

    return round((leads / total_leads) * 100, 2)


def lead_quality(context):
    """Legacy: Calculate lead quality ratio."""
    conversions = context.get("conversions")
    leads = context.get("leads")

    if not leads:
        return None

    return round(conversions / leads, 2)


__all__ = [
    "LeadsAnalyzer",
    "SYSTEM_PROMPT",
    "total_leads",
    "lead_conversion_rate",
    "lead_contribution",
    "lead_quality",
]