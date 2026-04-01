"""
Multi-File Relationship Discovery & Management
Handles relationships between multiple uploaded datasets
"""

import logging
from typing import List, Dict, Any, Set
from mongo_client import MongoDBClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class DataRelationshipManager:
    """Discover and manage relationships between multiple datasets"""
    
    def __init__(self, mongo_client: MongoDBClient = None):
        self.mongo_client = mongo_client or MongoDBClient()
        self.db = self.mongo_client.db
    
    # ===================================
    # 🔥 DISCOVER SHARED COLUMNS
    # ===================================
    def find_shared_columns(self, file_names: List[str]) -> Dict[str, Set[str]]:
        """
        Find common columns between datasets
        Returns: {
            "file1_file2": {"col1", "col2"},
            "file2_file3": {"colA"},
        }
        """
        try:
            # Fetch all datasets
            datasets = {}
            for fname in file_names:
                doc = self.db["documents"].find_one({
                    "type": "dataset",
                    "file_name": fname
                })
                if doc:
                    datasets[fname] = set(doc.get("columns", []))
            
            if not datasets:
                logger.warning("[RELATIONSHIPS] No datasets found")
                return {}
            
            # Find shared columns between each pair
            shared = {}
            file_list = list(datasets.keys())
            
            for i in range(len(file_list)):
                for j in range(i + 1, len(file_list)):
                    f1, f2 = file_list[i], file_list[j]
                    common = datasets[f1] & datasets[f2]
                    
                    if common:
                        key = f"{f1}_{f2}"
                        shared[key] = sorted(list(common))
                        logger.info(f"[SHARED] {f1} <-> {f2}: {common}")
            
            return shared
        
        except Exception as e:
            logger.error(f"[ERR] find_shared_columns: {e}")
            return {}
    
    # ===================================
    # 🔥 BUILD RELATIONSHIP METADATA
    # ===================================
    def build_relationship_graph(self, file_names: List[str]) -> Dict[str, Any]:
        """
        Build complete relationship metadata for all datasets
        """
        try:
            shared_cols = self.find_shared_columns(file_names)
            
            # Get column details
            datasets_info = {}
            for fname in file_names:
                doc = self.db["documents"].find_one({
                    "type": "dataset",
                    "file_name": fname
                })
                if doc:
                    datasets_info[fname] = {
                        "columns": doc.get("columns", []),
                        "rows": doc.get("rows", 0),
                        "types": self._detect_column_types(doc.get("data", []))
                    }
            
            relationship_meta = {
                "_id": "dataset_relationships",
                "datasets": file_names,
                "datasets_info": datasets_info,
                "shared_columns": shared_cols,
                "relationship_graph": self._build_graph(file_names, shared_cols),
                "timestamp": __import__('datetime').datetime.utcnow()
            }
            
            # Save to MongoDB
            self.db["metadata"].update_one(
                {"_id": "dataset_relationships"},
                {"$set": relationship_meta},
                upsert=True
            )
            
            logger.info(f"[RELATIONSHIPS] Graph built: {len(file_names)} datasets, {len(shared_cols)} connections")
            return relationship_meta
        
        except Exception as e:
            logger.error(f"[ERR] build_relationship_graph: {e}")
            return {}
    
    # ===================================
    # 🔥 DETECT COLUMN DATA TYPES
    # ===================================
    def _detect_column_types(self, data: List[Dict]) -> Dict[str, str]:
        """Detect data type for each column"""
        try:
            if not data:
                return {}
            
            types = {}
            first_row = data[0]
            
            for col, val in first_row.items():
                if isinstance(val, bool):
                    types[col] = "boolean"
                elif isinstance(val, int):
                    types[col] = "integer"
                elif isinstance(val, float):
                    types[col] = "float"
                elif isinstance(val, str):
                    types[col] = "string"
                else:
                    types[col] = "unknown"
            
            return types
        except Exception as e:
            logger.error(f"[ERR] _detect_column_types: {e}")
            return {}
    
    # ===================================
    # 🔥 BUILD RELATIONSHIP GRAPH
    # ===================================
    def _build_graph(self, file_names: List[str], shared_cols: Dict) -> Dict[str, List[str]]:
        """Build adjacency list of connected datasets"""
        graph = {fname: [] for fname in file_names}
        
        for pair, cols in shared_cols.items():
            if cols:  # Only if there are shared columns
                f1, f2 = pair.split("_", 1)
                graph[f1].append(f2)
                graph.get(f2, []).append(f1)
        
        return graph
    
    # ===================================
    # 🔥 JOIN DATASETS
    # ===================================
    def join_datasets(
        self,
        file1: str,
        file2: str,
        join_on: List[str] = None,
        join_type: str = "inner"
    ) -> List[Dict[str, Any]]:
        """
        Join two datasets on shared columns
        join_type: "inner", "left", "outer"
        """
        try:
            # Fetch datasets
            doc1 = self.db["documents"].find_one({
                "type": "dataset",
                "file_name": file1
            })
            doc2 = self.db["documents"].find_one({
                "type": "dataset",
                "file_name": file2
            })
            
            if not doc1 or not doc2:
                logger.warning(f"[JOIN] One or both datasets not found")
                return []
            
            data1 = doc1.get("data", [])
            data2 = doc2.get("data", [])
            
            # Auto-detect join columns if not specified
            if not join_on:
                cols1 = set(doc1.get("columns", []))
                cols2 = set(doc2.get("columns", []))
                join_on = list(cols1 & cols2)
            
            if not join_on:
                logger.warning(f"[JOIN] No common columns found between {file1} and {file2}")
                return data1  # Return first dataset as fallback
            
            logger.info(f"[JOIN] Joining {file1} and {file2} on {join_on}")
            
            # Perform join
            joined = []
            used_indices_2 = set()
            
            for row1 in data1:
                for idx2, row2 in enumerate(data2):
                    
                    # Check if join condition matches
                    match = all(
                        row1.get(col) == row2.get(col) 
                        for col in join_on
                    )
                    
                    if match:
                        # Merge rows
                        merged = {**row1, **row2}
                        joined.append(merged)
                        used_indices_2.add(idx2)
            
            # Handle outer join
            if join_type == "outer":
                for idx2, row2 in enumerate(data2):
                    if idx2 not in used_indices_2:
                        merged = {**row2}
                        joined.append(merged)
            
            logger.info(f"[JOIN] Result: {len(joined)} rows")
            return joined
        
        except Exception as e:
            logger.error(f"[ERR] join_datasets: {e}")
            return []
    
    # ===================================
    # 🔥 GET RELATIONSHIP METADATA
    # ===================================
    def get_relationships(self) -> Dict[str, Any]:
        """Retrieve stored relationship metadata"""
        try:
            meta = self.db["metadata"].find_one({"_id": "dataset_relationships"})
            return meta or {}
        except Exception as e:
            logger.error(f"[ERR] get_relationships: {e}")
            return {}


# 🔥 SINGLETON
relationship_manager = DataRelationshipManager()
