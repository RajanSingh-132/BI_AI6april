"""
Multi-File Query Processor
Handles queries that span multiple related datasets
"""

import logging
from typing import List, Dict, Any, Tuple
from data_relationships import relationship_manager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MultiFileQueryProcessor:
    """Process queries across multiple related datasets"""
    
    def __init__(self):
        self.relationship_manager = relationship_manager
    
    # ===================================
    # 🔥 DETECT MULTI-FILE QUERY
    # ===================================
    def is_multi_file_query(self, query: str, available_datasets: List[str]) -> bool:
        """
        Detect if query requires data from multiple files
        Keywords: "compare", "join", "between", "from both", "across"
        """
        multi_file_keywords = [
            "compare", "vs", "between", "join", "from both",
            "across", "combine", "merge", "relationship",
            "connection", "link", "match", "pair"
        ]
        
        query_lower = query.lower()
        
        # Check for multi-file keywords
        has_keyword = any(kw in query_lower for kw in multi_file_keywords)
        
        # Check for multiple file references
        file_mentions = sum(
            1 for fname in available_datasets 
            if fname.lower() in query_lower
        )
        
        return has_keyword or file_mentions > 1 or len(available_datasets) > 1
    
    # ===================================
    # 🔥 IDENTIFY RELEVANT DATASETS
    # ===================================
    def identify_relevant_datasets(
        self,
        query: str,
        available_datasets: List[str],
        relationships: Dict[str, Any]
    ) -> List[str]:
        """
        Identify which datasets are needed for this query
        """
        try:
            relevant = []
            query_lower = query.lower()
            
            # Direct file name mentions
            for fname in available_datasets:
                if fname.lower() in query_lower:
                    relevant.append(fname)
            
            # If no explicit mentions, and multi-file query, use all connected datasets
            if not relevant and available_datasets:
                relevant = available_datasets[:2]  # Start with first 2
            
            logger.info(f"[MULTI-FILE] Relevant datasets: {relevant}")
            return relevant
        
        except Exception as e:
            logger.error(f"[ERR] identify_relevant_datasets: {e}")
            return available_datasets[:1]
    
    # ===================================
    # 🔥 BUILD ANALYSIS CONTEXT
    # ===================================
    def build_analysis_context(
        self,
        query: str,
        datasets: List[str],
        relationships: Dict[str, Any],
        fetched_data: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Build a comprehensive context for multi-file analysis
        """
        try:
            context = {
                "datasets_involved": datasets,
                "query_type": self._detect_query_type(query),
                "shared_columns": self._get_shared_columns_for_datasets(datasets, relationships),
                "data_summary": {},
                "join_suggestions": []
            }
            
            # Get data summary for each dataset
            for fname in datasets:
                if fname in fetched_data:
                    data = fetched_data[fname]
                    context["data_summary"][fname] = {
                        "rows": len(data),
                        "columns": list(data[0].keys()) if data else [],
                        "numeric_columns": self._get_numeric_columns(data),
                        "categorical_columns": self._get_categorical_columns(data)
                    }
            
            # Generate join suggestions
            if len(datasets) > 1:
                context["join_suggestions"] = self._suggest_joins(datasets, relationships)
            
            logger.info(f"[MULTI-FILE] Context built for {len(datasets)} datasets")
            return context
        
        except Exception as e:
            logger.error(f"[ERR] build_analysis_context: {e}")
            return {}
    
    # ===================================
    # 🔥 DETECT QUERY TYPE
    # ===================================
    def _detect_query_type(self, query: str) -> str:
        """Detect type of multi-file query"""
        query_lower = query.lower()
        
        if any(w in query_lower for w in ["compare", "vs", "between", "difference"]):
            return "comparison"
        elif any(w in query_lower for w in ["join", "merge", "combine", "match"]):
            return "join"
        elif any(w in query_lower for w in ["correlation", "relationship", "linked"]):
            return "correlation"
        else:
            return "cross_dataset"
    
    # ===================================
    # 🔥 GET SHARED COLUMNS
    # ===================================
    def _get_shared_columns_for_datasets(
        self,
        datasets: List[str],
        relationships: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Get shared columns for dataset pairs"""
        try:
            shared = {}
            for pair_key, cols in relationships.get("shared_columns", {}).items():
                # Check if both files in pair are in our selection
                f1, f2 = pair_key.split("_", 1)
                if f1 in datasets and f2 in datasets:
                    shared[pair_key] = cols
            return shared
        except Exception as e:
            logger.error(f"[ERR] _get_shared_columns_for_datasets: {e}")
            return {}
    
    # ===================================
    # 🔥 DETECT NUMERIC COLUMNS
    # ===================================
    def _get_numeric_columns(self, data: List[Dict]) -> List[str]:
        """Find numeric columns in dataset"""
        if not data:
            return []
        
        numeric = []
        first_row = data[0]
        
        for col, val in first_row.items():
            if isinstance(val, (int, float)):
                numeric.append(col)
        
        return numeric
    
    # ===================================
    # 🔥 DETECT CATEGORICAL COLUMNS
    # ===================================
    def _get_categorical_columns(self, data: List[Dict]) -> List[str]:
        """Find categorical columns in dataset"""
        if not data:
            return []
        
        categorical = []
        first_row = data[0]
        
        for col, val in first_row.items():
            if isinstance(val, str):
                categorical.append(col)
        
        return categorical
    
    # ===================================
    # 🔥 SUGGEST JOINS
    # ===================================
    def _suggest_joins(
        self,
        datasets: List[str],
        relationships: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Suggest how to join datasets based on shared columns"""
        try:
            suggestions = []
            shared = relationships.get("shared_columns", {})
            
            for pair_key, cols in shared.items():
                f1, f2 = pair_key.split("_", 1)
                if f1 in datasets and f2 in datasets:
                    suggestions.append({
                        "file1": f1,
                        "file2": f2,
                        "join_keys": cols,
                        "join_type": "inner"
                    })
            
            return suggestions
        
        except Exception as e:
            logger.error(f"[ERR] _suggest_joins: {e}")
            return []
    
    # ===================================
    # 🔥 GENERATE MULTI-FILE SYSTEM PROMPT EXTENSION
    # ===================================
    def generate_multi_file_prompt_extension(
        self,
        context: Dict[str, Any]
    ) -> str:
        """Generate additional prompt instructions for multi-file analysis"""
        try:
            extension = """

--------------------------------------------------
MULTI-FILE ANALYSIS (NEW)
--------------------------------------------------

You are analyzing multiple related datasets that share common fields.

DATASETS AVAILABLE:
"""
            
            for fname, summary in context.get("data_summary", {}).items():
                extension += f"\n- {fname}: {summary['rows']} rows"
                extension += f"\n  Columns: {', '.join(summary['columns'][:5])}"
                if len(summary['columns']) > 5:
                    extension += f" ... +{len(summary['columns']) - 5} more"
            
            extension += "\n\nSHARED COLUMNS (for joining):"
            for pair, cols in context.get("shared_columns", {}).items():
                extension += f"\n- {pair}: {', '.join(cols)}"
            
            extension += f"\n\nQUERY TYPE: {context.get('query_type', 'cross_dataset')}"
            
            if context.get("join_suggestions"):
                extension += "\n\nJOIN SUGGESTIONS:"
                for suggestion in context["join_suggestions"]:
                    extension += f"\n- Join {suggestion['file1']} with {suggestion['file2']}"
                    extension += f" on {', '.join(suggestion['join_keys'])}"
            
            extension += """

INSTRUCTIONS FOR MULTI-FILE QUERIES:
1. IDENTIFY which dataset each column belongs to
2. USE shared columns to correlate data across files
3. APPLY same formulas but ACROSS datasets
4. COMPARE metrics between files when relevant
5. GENERATE insights that span multiple datasets
6. MENTION dataset names in results when combining data

IMPORTANT: When calculating metrics across files:
- Use the correct dataset's columns
- Be explicit about which file each value comes from
- Show how files relate to each other
- Leverage shared columns for deeper analysis

--------------------------------------------------
"""
            
            return extension
        
        except Exception as e:
            logger.error(f"[ERR] generate_multi_file_prompt_extension: {e}")
            return ""


# 🔥 SINGLETON
multi_file_processor = MultiFileQueryProcessor()
