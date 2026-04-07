"""
Dynamic Semantic Analyzer
Extracts metrics, dimensions, and operations from queries without hardcoding analysis types.
Uses semantic understanding to determine what calculations are needed.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    import pandas as pd
except ImportError:
    pd = None

from audit_logger import get_logger

logger = logging.getLogger(__name__)


@dataclass
class QueryIntent:
    """Semantic understanding of a query - not a hardcoded type."""
    
    # Core extractions
    requested_metrics: Set[str] = field(default_factory=set)  # e.g., {"revenue", "leads"}
    requested_dimensions: Set[str] = field(default_factory=set)  # e.g., {"source", "owner"}
    requested_operations: Set[str] = field(default_factory=set)  # e.g., {"sum", "count", "breakdown"}
    
    # Semantics
    is_asking_for_total: bool = False  # "total revenue", "sum"
    is_asking_for_breakdown: bool = False  # "breakdown", "by", "per", "each"
    is_asking_for_comparison: bool = False  # "compare", "vs", "versus"
    is_asking_for_combined: bool = False  # "and", "&", both metrics together
    
    # Query metadata
    original_query: str = ""
    confidence: float = 0.0
    reasoning: List[str] = field(default_factory=list)


class MetricDatabase:
    """Central registry of available metrics and their column synonyms."""
    
    METRICS = {
        "revenue": {
            "aliases": ["revenue", "sales", "amount", "deal_value", "value", "income", "earnings"],
            "columns": ["Deal_Value", "revenue", "amount", "sales", "total"],
            "aggregation": "sum",
            "type": "numeric",
        },
        "leads": {
            "aliases": ["leads", "lead", "prospect", "prospects", "records", "count"],
            "columns": ["Lead_ID", "id", "record"],
            "aggregation": "count",
            "type": "count",
        },
        "conversions": {
            "aliases": ["conversion", "conversions", "converted"],
            "columns": ["conversions", "converted"],
            "aggregation": "sum",
            "type": "numeric",
        },
        "profit": {
            "aliases": ["profit", "margin", "net"],
            "columns": ["profit", "net_profit"],
            "aggregation": "sum",
            "type": "numeric",
        },
    }
    
    @classmethod
    def find_metric(cls, term: str) -> Optional[str]:
        """Find metric key from user input term."""
        term_lower = term.lower().strip()
        for metric_key, metric_def in cls.METRICS.items():
            if term_lower in metric_def["aliases"]:
                return metric_key
        return None
    
    @classmethod
    def get_columns_for_metric(cls, metric: str) -> List[str]:
        """Get possible column names for a metric."""
        if metric in cls.METRICS:
            return cls.METRICS[metric]["columns"]
        return []
    
    @classmethod
    def get_aggregation_for_metric(cls, metric: str) -> str:
        """Get default aggregation for a metric."""
        if metric in cls.METRICS:
            return cls.METRICS[metric]["aggregation"]
        return "sum"


class DimensionDatabase:
    """Central registry of available dimensions and their column synonyms."""
    
    DIMENSIONS = {
        "source": {
            "aliases": ["source", "channel", "lead_source", "origin"],
            "columns": ["Lead_Source", "source", "channel"],
        },
        "owner": {
            "aliases": ["owner", "rep", "sales_rep", "assigned"],
            "columns": ["Owner", "owner", "assigned_to"],
        },
        "stage": {
            "aliases": ["stage", "deal_stage", "status"],
            "columns": ["Deal_Stage", "stage", "status"],
        },
        "industry": {
            "aliases": ["industry", "sector"],
            "columns": ["Industry", "industry", "sector"],
        },
        "time": {
            "aliases": ["date", "month", "year", "time", "when"],
            "columns": ["Date", "date", "month", "year"],
        },
    }
    
    @classmethod
    def find_dimension(cls, term: str) -> Optional[str]:
        """Find dimension key from user input term."""
        term_lower = term.lower().strip()
        for dim_key, dim_def in cls.DIMENSIONS.items():
            if term_lower in dim_def["aliases"]:
                return dim_key
        return None
    
    @classmethod
    def get_columns_for_dimension(cls, dimension: str) -> List[str]:
        """Get possible column names for a dimension."""
        if dimension in cls.DIMENSIONS:
            return cls.DIMENSIONS[dimension]["columns"]
        return []


class SemanticExtractor:
    """
    Extracts semantic meaning from queries without hardcoding analysis types.
    Identifies metrics, dimensions, and operations dynamically.
    """
    
    # Keywords for operations
    TOTAL_KEYWORDS = {"total", "sum", "cumulative", "aggregate", "overall"}
    BREAKDOWN_KEYWORDS = {"breakdown", "by", "per", "each", "split", "group", "breakdown by"}
    COMPARISON_KEYWORDS = {"compare", "vs", "versus", "comparison", "difference"}
    COMBINED_KEYWORDS = {"and", "&", "both"}
    
    # Context words that help identify intent
    RELATIONSHIP_KEYWORDS = {"relationship", "associated", "correlation", "linked", "together"}
    
    def __init__(self):
        self.audit_logger = get_logger()
    
    def extract_intent(
        self,
        query: str,
        dataset: pd.DataFrame,
    ) -> QueryIntent:
        """
        Extract semantic intent from query without predefined types.
        Dynamically identifies what the user is asking for.
        """
        intent = QueryIntent(original_query=query)
        query_lower = query.lower()
        words = query_lower.split()
        
        self.audit_logger.logger.info(f"[SEMANTIC] Extracting intent from: {query}")
        
        # 1. Detect requested metrics
        intent.requested_metrics = self._extract_metrics(query_lower, dataset)
        self.audit_logger.logger.info(f"[METRICS] Detected: {intent.requested_metrics}")
        
        # 2. Detect requested dimensions
        intent.requested_dimensions = self._extract_dimensions(query_lower, dataset)
        self.audit_logger.logger.info(f"[DIMENSIONS] Detected: {intent.requested_dimensions}")
        
        # 3. Detect operations
        intent.is_asking_for_total = self._check_operation(
            query_lower, self.TOTAL_KEYWORDS
        )
        intent.is_asking_for_breakdown = self._check_operation(
            query_lower, self.BREAKDOWN_KEYWORDS
        )
        intent.is_asking_for_comparison = self._check_operation(
            query_lower, self.COMPARISON_KEYWORDS
        )
        intent.is_asking_for_combined = self._check_operation(
            query_lower, self.COMBINED_KEYWORDS
        )
        
        self.audit_logger.logger.info(
            f"[OPERATIONS] Total={intent.is_asking_for_total}, "
            f"Breakdown={intent.is_asking_for_breakdown}, "
            f"Comparison={intent.is_asking_for_comparison}, "
            f"Combined={intent.is_asking_for_combined}"
        )
        
        # 4. Determine requested operations
        intent.requested_operations = self._determine_operations(intent)
        self.audit_logger.logger.info(f"[OPS] To perform: {intent.requested_operations}")
        
        # 5. Calculate confidence
        intent.confidence = self._calculate_confidence(intent)
        
        # Add reasoning
        intent.reasoning = self._build_reasoning(intent)
        
        self.audit_logger.logger.info(f"[CONFIDENCE] {intent.confidence:.2%}")
        
        return intent
    
    def _extract_metrics(
        self,
        query_lower: str,
        dataset: pd.DataFrame,
    ) -> Set[str]:
        """Extract metric names from query."""
        import re
        metrics = set()
        
        # Check for each metric using word boundaries to avoid matching partial words
        # e.g., "lead" in "lead_source" dimension should not match
        for metric_key, metric_def in MetricDatabase.METRICS.items():
            for alias in metric_def["aliases"]:
                # Use word boundary regex to match whole words only
                pattern = r'\b' + re.escape(alias) + r'\b'
                matches = re.finditer(pattern, query_lower)
                
                for match in matches:
                    # Special handling for "lead" - check if it's part of "lead_source" or "lead source"
                    if alias == "lead":
                        # Get context after the match
                        pos = match.end()
                        remaining = query_lower[pos:].strip()
                        # If "source" or "_source" follows "lead", skip it (it's a dimension, not a metric)
                        if remaining.startswith("source") or remaining.startswith("_source"):
                            continue
                        # If "lead" appears before "by", it might be a dimension
                        if remaining.startswith("by"):
                            continue
                    
                    metrics.add(metric_key)
                    break  # Found this metric, move to next metric
        
        # If no metrics found, infer from context
        if not metrics:
            # If asking "how many", probably leads
            if "how many" in query_lower or "count" in query_lower:
                metrics.add("leads")
            # If asking about money/finances, probably revenue
            elif any(w in query_lower for w in ["much", "money", "dollar", "$", "earn"]):
                metrics.add("revenue")
            # Default: revenue if ambiguous
            else:
                metrics.add("revenue")
        
        return metrics
    
    def _extract_dimensions(
        self,
        query_lower: str,
        dataset: pd.DataFrame,
    ) -> Set[str]:
        """Extract dimension names from query."""
        dimensions = set()
        
        # Look for dimension keywords
        for dim_key, dim_def in DimensionDatabase.DIMENSIONS.items():
            for alias in dim_def["aliases"]:
                if alias in query_lower:
                    dimensions.add(dim_key)
                    break
        
        # Look for column names in query directly
        if dataset is not None and isinstance(dataset, pd.DataFrame):
            for col in dataset.columns:
                if col.lower() in query_lower:
                    # Find dimension key for this column
                    for dim_key, dim_def in DimensionDatabase.DIMENSIONS.items():
                        if col in dim_def["columns"]:
                            dimensions.add(dim_key)
                            break
        
        return dimensions
    
    def _check_operation(
        self,
        query_lower: str,
        keywords: Set[str],
    ) -> bool:
        """Check if query contains operation keywords."""
        for keyword in keywords:
            if keyword in query_lower:
                return True
        return False
    
    def _determine_operations(self, intent: QueryIntent) -> Set[str]:
        """Determine what operations to perform based on intent."""
        operations = set()
        
        # If asking for breakdown with dimensions, add "breakdown"
        if intent.is_asking_for_breakdown and intent.requested_dimensions:
            operations.add("breakdown")
        
        # If asking for total or no breakdown, add "total"
        if intent.is_asking_for_total or not intent.is_asking_for_breakdown:
            operations.add("total")
        
        # If asking for comparison or multiple metrics together
        if intent.is_asking_for_comparison or (
            intent.is_asking_for_combined and len(intent.requested_metrics) > 1
        ):
            operations.add("combined_analysis")
        
        return operations
    
    def _calculate_confidence(self, intent: QueryIntent) -> float:
        """Calculate confidence in the extraction."""
        score = 0.0
        factors = 0
        
        # Confidence from metrics detected
        if intent.requested_metrics:
            score += 0.5
        factors += 1
        
        # Confidence from dimensions matching operations
        if intent.requested_dimensions and intent.is_asking_for_breakdown:
            score += 0.3
        factors += 1
        
        # Confidence from clear operations
        if intent.requested_operations:
            score += 0.2
        factors += 1
        
        return min(1.0, score / max(factors, 1))
    
    def _build_reasoning(self, intent: QueryIntent) -> List[str]:
        """Build human-readable reasoning."""
        reasons = []
        
        if intent.requested_metrics:
            reasons.append(f"User asking about: {', '.join(intent.requested_metrics)}")
        
        if intent.requested_dimensions:
            reasons.append(f"Grouping by: {', '.join(intent.requested_dimensions)}")
        
        if intent.is_asking_for_total:
            reasons.append("Request: total/aggregate")
        if intent.is_asking_for_breakdown:
            reasons.append("Request: breakdown/grouping")
        if intent.is_asking_for_comparison:
            reasons.append("Request: comparison/contrast")
        if intent.is_asking_for_combined:
            reasons.append("Request: combined metrics")
        
        return reasons


__all__ = [
    "QueryIntent",
    "SemanticExtractor",
    "MetricDatabase",
    "DimensionDatabase",
]
