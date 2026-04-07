"""
Master Prompt Orchestrator - Dynamic Semantic Analysis
Performs semantic extraction without hardcoded analysis types.
Intelligently selects calculations based on query understanding.
"""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

from prompt_revenue import RevenueAnalyzer
from prompt_leads import LeadsAnalyzer
from audit_logger import get_logger
from semantic_extractor import SemanticExtractor, MetricDatabase, DimensionDatabase

logger = logging.getLogger(__name__)


class DynamicAnalysisOrchestrator:
    """
    Performs semantic extraction and dynamic analysis.
    No hardcoded analysis types - decides what to calculate based on intent.
    """

    def __init__(self):
        self.semantic_extractor = SemanticExtractor()
        self.revenue_analyzer = RevenueAnalyzer()
        self.leads_analyzer = LeadsAnalyzer()
        self.audit_logger = get_logger()

    def analyze(
        self,
        query: str,
        dataset: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Analyze query and perform appropriate calculations.
        No predefined analysis types - dynamically determined.
        """
        self.audit_logger.logger.info("=== Dynamic Semantic Analysis Started ===")
        self.audit_logger.logger.info(f"Query: {query}")

        if not isinstance(dataset, pd.DataFrame):
            dataset = pd.DataFrame(dataset)

        # Step 1: Extract semantic intent
        intent = self.semantic_extractor.extract_intent(query, dataset)

        # Step 2: Prepare analysis plan
        analysis_plan = self._build_analysis_plan(intent, dataset)
        self.audit_logger.logger.info(f"Analysis plan: {analysis_plan}")

        # Step 3: Execute calculations
        results = self._execute_plan(analysis_plan, intent, dataset, query)

        # Step 4: Combine results into final output
        final_result = self._combine_results(results, intent)

        # Add metadata
        final_result["_metadata"] = {
            "semantic_intent": {
                "metrics": list(intent.requested_metrics),
                "dimensions": list(intent.requested_dimensions),
                "operations": list(intent.requested_operations),
                "is_total": intent.is_asking_for_total,
                "is_breakdown": intent.is_asking_for_breakdown,
                "is_comparison": intent.is_asking_for_comparison,
                "is_combined": intent.is_asking_for_combined,
            },
            "confidence": intent.confidence,
            "reasoning": intent.reasoning,
            "original_query": query,
        }

        self.audit_logger.logger.info("=== Dynamic Semantic Analysis Completed ===\n")

        return final_result

    def _build_analysis_plan(
        self,
        intent,
        dataset: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Build analysis plan based on semantic intent.
        Determines which metrics to calculate and how.
        """
        plan = {
            "metrics_to_calculate": {},
            "has_breakdown": intent.is_asking_for_breakdown,
            "has_combined": intent.is_asking_for_combined,
            "dimensions": list(intent.requested_dimensions),
        }

        # For each requested metric, determine calculations
        for metric in intent.requested_metrics:
            metric_key = MetricDatabase.find_metric(metric) or metric
            plan["metrics_to_calculate"][metric_key] = {
                "metric": metric_key,
                "get_total": True,  # Always get total
                "get_breakdown": intent.is_asking_for_breakdown
                and intent.requested_dimensions,
                "breakdown_columns": list(intent.requested_dimensions),
            }

        return plan

    def _execute_plan(
        self,
        plan: Dict[str, Any],
        intent,
        dataset: pd.DataFrame,
        query: str,
    ) -> Dict[str, Any]:
        """Execute the analysis plan."""
        results = {}

        for metric_key, metric_plan in plan["metrics_to_calculate"].items():
            self.audit_logger.logger.info(f"[CALC] Processing metric: {metric_key}")

            if metric_key == "revenue":
                results[metric_key] = self._calculate_revenue(
                    metric_plan, dataset, query
                )
            elif metric_key == "leads":
                results[metric_key] = self._calculate_leads(
                    metric_plan, dataset, query
                )
            elif metric_key == "conversions":
                results[metric_key] = self._calculate_conversions(
                    metric_plan, dataset, query
                )
            else:
                self.audit_logger.logger.warning(f"Unknown metric: {metric_key}")

        return results

    def _calculate_revenue(
        self,
        metric_plan: Dict[str, Any],
        dataset: pd.DataFrame,
        query: str,
    ) -> Dict[str, Any]:
        """Calculate revenue metric."""
        result = {}

        # Get total revenue
        if metric_plan["get_total"]:
            total_result = self.revenue_analyzer.calculate_total_revenue(
                dataset=dataset,
                query=query,
            )
            result["total"] = total_result

        # Get breakdown if requested
        if metric_plan["get_breakdown"] and metric_plan["breakdown_columns"]:
            breakdown_by = metric_plan["breakdown_columns"][0]
            # Find actual column name in dataset
            actual_col = self._find_actual_column(breakdown_by, dataset)
            if actual_col:
                breakdown_result = (
                    self.revenue_analyzer.calculate_revenue_by_group(
                        dataset=dataset,
                        group_by=actual_col,
                        query=query,
                    )
                )
                result["breakdown"] = breakdown_result

        return result

    def _calculate_leads(
        self,
        metric_plan: Dict[str, Any],
        dataset: pd.DataFrame,
        query: str,
    ) -> Dict[str, Any]:
        """Calculate leads metric."""
        result = {}

        # Get total leads
        if metric_plan["get_total"]:
            total_result = self.leads_analyzer.calculate_total_leads(
                dataset=dataset,
                query=query,
            )
            result["total"] = total_result

        # Get breakdown if requested
        if metric_plan["get_breakdown"] and metric_plan["breakdown_columns"]:
            breakdown_by = metric_plan["breakdown_columns"][0]
            # Find actual column name in dataset
            actual_col = self._find_actual_column(breakdown_by, dataset)
            if actual_col:
                breakdown_result = self.leads_analyzer.calculate_leads_by_group(
                    dataset=dataset,
                    group_by=actual_col,
                    query=query,
                )
                result["breakdown"] = breakdown_result

        return result

    def _calculate_conversions(
        self,
        metric_plan: Dict[str, Any],
        dataset: pd.DataFrame,
        query: str,
    ) -> Dict[str, Any]:
        """Calculate conversion metrics (placeholder)."""
        # This would require conversions column in data
        return {"error": "Conversions metric not yet implemented"}

    def _find_actual_column(self, dimension_key: str, dataset: pd.DataFrame) -> Optional[str]:
        """Find actual column name in dataset for a dimension."""
        possible_columns = DimensionDatabase.get_columns_for_dimension(dimension_key)
        
        if not isinstance(dataset, pd.DataFrame):
            return None
        
        for col in possible_columns:
            if col in dataset.columns:
                return col
        
        # Try case-insensitive match
        for col in dataset.columns:
            if col.lower() == dimension_key.lower():
                return col
        
        return None

    def _combine_results(
        self,
        results: Dict[str, Any],
        intent,
    ) -> Dict[str, Any]:
        """Combine individual metric results into final output."""
        combined = {}

        # Flat structure if single metric
        if len(results) == 1:
            metric_key = list(results.keys())[0]
            metric_results = results[metric_key]

            if "total" in metric_results:
                combined.update(metric_results["total"])

            if "breakdown" in metric_results:
                combined["group_breakdown"] = metric_results["breakdown"].get(
                    "group_breakdown", []
                )

        # Nested structure if multiple metrics
        elif len(results) > 1:
            combined["metrics"] = {}

            for metric_key, metric_results in results.items():
                combined["metrics"][metric_key] = {}

                if "total" in metric_results:
                    total_data = metric_results["total"]
                    # Extract key metric value
                    if metric_key == "revenue":
                        combined["metrics"][metric_key]["total"] = total_data.get(
                            "total_revenue", 0
                        )
                    elif metric_key == "leads":
                        combined["metrics"][metric_key]["total"] = total_data.get(
                            "leads_after_filters", 0
                        )

                if "breakdown" in metric_results:
                    combined["metrics"][metric_key]["breakdown"] = metric_results[
                        "breakdown"
                    ].get("group_breakdown", [])

            # Also compute combined analysis if requested
            if intent.is_asking_for_combined or (
                len(results) > 1 and intent.is_asking_for_breakdown
            ):
                combined["combined_analysis"] = self._create_combined_view(results)

        # Calculate formatted explanation
        combined["explanation"] = self._format_explanation(combined, results, intent)

        return combined

    def _create_combined_view(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create a combined view for multiple metrics."""
        view = {}

        # If we have both revenue and leads with breakdowns
        if "revenue" in results and "leads" in results:
            rev_breakdown = (
                results["revenue"]
                .get("breakdown", {})
                .get("group_breakdown", [])
            )
            leads_breakdown = (
                results["leads"]
                .get("breakdown", {})
                .get("group_breakdown", [])
            )

            if rev_breakdown and leads_breakdown:
                # Merge by entity name
                leads_map = {
                    g["entity_name"]: g["lead_count"] for g in leads_breakdown
                }

                merged = []
                for rev_group in rev_breakdown:
                    entity = rev_group["entity_name"]
                    lead_count = leads_map.get(entity, 0)
                    merged.append({
                        "entity": entity,
                        "revenue": rev_group["revenue"],
                        "leads": lead_count,
                        "revenue_per_lead": (
                            rev_group["revenue"] / lead_count if lead_count else 0
                        ),
                    })

                view["by_entity"] = merged

        return view

    def _format_explanation(
        self,
        combined: Dict[str, Any],
        results: Dict[str, Any],
        intent,
    ) -> str:
        """Format a human-readable explanation of results."""
        lines = []

        if "metrics" in combined:
            # Multiple metrics
            for metric_key, metric_data in combined.get("metrics", {}).items():
                if metric_key == "revenue":
                    lines.append(
                        f"Total Revenue: ${metric_data.get('total', 0):,.2f}"
                    )
                elif metric_key == "leads":
                    lines.append(f"Total Leads: {metric_data.get('total', 0)}")

            # Add combined analysis
            if "combined_analysis" in combined:
                by_entity = combined["combined_analysis"].get("by_entity", [])
                if by_entity:
                    lines.append("\nBreakdown by Entity:")
                    for item in by_entity:
                        lines.append(
                            f"  {item['entity']}: ${item['revenue']:,.2f} "
                            f"({item['leads']} leads, "
                            f"${item['revenue_per_lead']:,.2f}/lead)"
                        )
        else:
            # Single metric or simple layout
            for metric_key, metric_results in results.items():
                if metric_key == "revenue":
                    total_data = metric_results.get("total", {})
                    total_rev = total_data.get("total_revenue", 0)
                    lines.append(f"Total Revenue: ${total_rev:,.2f}")

                    if "breakdown" in metric_results:
                        breakdown = metric_results["breakdown"].get(
                            "group_breakdown", []
                        )
                        if breakdown:
                            lines.append("Breakdown:")
                            for item in breakdown:
                                lines.append(
                                    f"  {item['entity_name']}: ${item['revenue']:,.2f}"
                                )

                elif metric_key == "leads":
                    total_data = metric_results.get("total", {})
                    total_leads = total_data.get("leads_after_filters", 0)
                    lines.append(f"Total Leads: {total_leads}")

                    if "breakdown" in metric_results:
                        breakdown = metric_results["breakdown"].get(
                            "group_breakdown", []
                        )
                        if breakdown:
                            lines.append("Breakdown:")
                            for item in breakdown:
                                lines.append(
                                    f"  {item['entity_name']}: {item['lead_count']} leads"
                                )

        return "\n".join(lines)


def analyze_query(
    query: str,
    dataset: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Entry point for semantic analysis.
    No predefined analysis types - all semantic.
    """
    orchestrator = DynamicAnalysisOrchestrator()
    return orchestrator.analyze(query, dataset)


__all__ = [
    "DynamicAnalysisOrchestrator",
    "analyze_query",
]
