"""
Master Prompt Orchestrator - LLM-Driven Semantic Analysis
Performs semantic extraction for query intent.
Uses LLM for intelligent column identification in analyzers.
Includes Revenue Per Lead (RPL) analysis for efficiency metrics.
"""

import json
import logging
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

# Import LLM-driven analyzers
from prompt_revenue_llm import RevenueAnalyzer
from prompt_leads_llm import LeadsAnalyzer
from prompt_revenue_per_lead import RevenuePerLeadAnalyzer
from audit_logger import get_logger
from semantic_extractor import SemanticExtractor, MetricDatabase, DimensionDatabase

logger = logging.getLogger(__name__)


class DynamicAnalysisOrchestrator:
    """
    Performs semantic extraction and dynamic analysis.
    No hardcoded analysis types - decides what to calculate based on intent.
    Supports Revenue, Leads, and Revenue-Per-Lead (RPL) metrics.
    """

    def __init__(self):
        self.semantic_extractor = SemanticExtractor()
        self.revenue_analyzer = RevenueAnalyzer()
        self.leads_analyzer = LeadsAnalyzer()
        self.rpl_analyzer = RevenuePerLeadAnalyzer()
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

        # Check if this is an RPL (Revenue Per Lead) query
        is_rpl_query = self._is_rpl_query(query, intent)

        if is_rpl_query:
            # Special handling for RPL analysis
            self.audit_logger.logger.info("[CALC] Processing metric: revenue_per_lead (RPL)")
            results["revenue_per_lead"] = self._calculate_rpl(
                plan, dataset, query
            )
        else:
            # Standard metric-by-metric calculation
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

    def _is_rpl_query(self, query: str, intent) -> bool:
        """
        Detect if this is a Revenue Per Lead (RPL) query.
        
        RPL queries ask for revenue efficiency metrics like:
        - "revenue per lead"
        - "revenue-wise lead analysis"
        - "lead efficiency"
        - "revenue by lead source"
        """
        query_lower = query.lower()
        
        rpl_keywords = [
            "revenue per lead",
            "revenue-wise lead",
            "per lead",
            "lead efficiency",
            "rpl",
            "revenue by lead source",
            "revenue analysis by lead",
            "revenue efficiency",
        ]
        
        for keyword in rpl_keywords:
            if keyword in query_lower:
                self.audit_logger.logger.info(f"[RPL] Detected RPL query (keyword: '{keyword}')")
                return True
        
        return False

    def _calculate_rpl(
        self,
        metric_plan: Dict[str, Any],
        dataset: pd.DataFrame,
        query: str,
    ) -> Dict[str, Any]:
        """
        Calculate Revenue Per Lead metrics.
        
        RPL = Total Revenue / Total Leads (by group if requested)
        """
        result = {}

        try:
            # Determine grouping dimension if requested
            group_by = None
            if metric_plan.get("get_breakdown") and metric_plan.get("breakdown_columns"):
                dimension_key = metric_plan["breakdown_columns"][0]
                group_by = self._find_actual_column(dimension_key, dataset)

            # Run RPL analysis
            rpl_result = self.rpl_analyzer.analyze_revenue_per_lead(
                dataset=dataset,
                group_by=group_by,
                query=query
            )

            # Transform result for consistency with other metrics
            result["overall"] = {
                "total_revenue": rpl_result["overall_metrics"]["total_revenue"],
                "total_leads": rpl_result["overall_metrics"]["total_leads"],
                "revenue_per_lead": rpl_result["overall_metrics"]["revenue_per_lead"],
            }

            # Format breakdown if available
            if rpl_result["by_group"]:
                result["breakdown"] = {
                    "group_breakdown": [
                        {
                            "entity_name": g["group_value"],
                            "revenue": g["revenue"],
                            "lead_count": g["lead_count"],
                            "revenue_per_lead": g["rpl"],
                        }
                        for g in rpl_result["by_group"]
                    ]
                }

            result["validation"] = rpl_result["validation"]
            result["columns_used"] = rpl_result["columns_used"]

            self.audit_logger.logger.info(
                f"[RPL] Calculation complete: "
                f"RPL={result['overall']['revenue_per_lead']:,.2f}, "
                f"Revenue={result['overall']['total_revenue']:,.2f}, "
                f"Leads={result['overall']['total_leads']}"
            )

        except Exception as e:
            self.audit_logger.logger.error(f"[RPL] Calculation failed: {str(e)}")
            result["error"] = str(e)

        return result

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

        # Check if this is an RPL result
        if "revenue_per_lead" in results:
            rpl_data = results["revenue_per_lead"]
            
            combined["metric_type"] = "revenue_per_lead"
            combined["overall"] = rpl_data.get("overall", {})
            combined["columns_used"] = rpl_data.get("columns_used", {})
            
            if "breakdown" in rpl_data:
                combined["group_breakdown"] = rpl_data["breakdown"]["group_breakdown"]

            if "validation" in rpl_data:
                combined["validation"] = rpl_data["validation"]

        # Flat structure if single standard metric
        elif len(results) == 1:
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

        # Special handling for RPL results
        if combined.get("metric_type") == "revenue_per_lead":
            lines.append("=== Revenue Per Lead (RPL) Analysis ===\n")
            
            overall = combined.get("overall", {})
            lines.append(f"Overall RPL: ${overall.get('revenue_per_lead', 0):,.2f}")
            lines.append(f"  Total Revenue: ${overall.get('total_revenue', 0):,.2f}")
            lines.append(f"  Total Leads: {overall.get('total_leads', 0)}")

            # Add breakdown if available
            if "group_breakdown" in combined:
                lines.append("\nBreakdown by Source:")
                for item in combined["group_breakdown"]:
                    lines.append(
                        f"  {item['entity_name']:<15} "
                        f"Revenue: ${item['revenue']:>12,.2f} | "
                        f"Leads: {item['lead_count']:>5} | "
                        f"RPL: ${item['revenue_per_lead']:>10,.2f}"
                    )

            # Add validation notes if any
            if "validation" in combined and not combined["validation"].get("passed", True):
                lines.append("\n⚠️  Validation Notes:")
                for note in combined["validation"].get("notes", []):
                    lines.append(f"  - {note}")

        # Standard metrics handling
        elif "metrics" in combined:
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
