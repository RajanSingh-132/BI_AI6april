# Multi-File Relational Analysis Implementation

## Overview
Implemented comprehensive multi-file relationship discovery and cross-file query analysis for the BHI backend.

## New Modules Created

### 1. `data_relationships.py`
**Purpose**: Discover and manage relationships between multiple datasets
**Key Classes**:
- `DataRelationshipManager`: Handles all relationship operations

**Key Methods**:
- `find_shared_columns()`: Discovers common columns between datasets
- `build_relationship_graph()`: Builds complete metadata about dataset relationships
- `join_datasets()`: Joins two datasets on shared columns (inner/left/outer joins)
- `get_relationships()`: Retrieves stored relationship metadata
- `_detect_column_types()`: Auto-detects data types for columns
- `_build_graph()`: Creates adjacency list of connected datasets

**Features**:
- Automatic detection of shared columns across files
- Column type detection (integer, float, string, boolean)
- Graph-based relationship modeling
- MongoDB persistence of relationship metadata
- Support for multiple join types

### 2. `multi_file_queries.py`
**Purpose**: Process queries that span multiple related datasets
**Key Classes**:
- `MultiFileQueryProcessor`: Handles multi-file query analysis

**Key Methods**:
- `is_multi_file_query()`: Detects if query spans multiple files
- `identify_relevant_datasets()`: Identifies which datasets are needed
- `build_analysis_context()`: Builds comprehensive analysis context
- `generate_multi_file_prompt_extension()`: Creates LLM-specific instructions
- `_detect_query_type()`: Categorizes query (comparison, join, correlation, cross_dataset)
- `_suggest_joins()`: Recommends how to join datasets

**Query Type Detection**:
- **comparison**: "compare", "vs", "between", "difference"
- **join**: "join", "merge", "combine", "match"
- **correlation**: "correlation", "relationship", "linked"
- **cross_dataset**: General cross-dataset queries

## Integration Points

### 1. Upload Routes (`routes/upload.py`)
**Changes**:
- Added import for `data_relationships`
- Modified `upload_multiple_json()` to build relationship graph after upload
- Returns relationship metadata in response
- Triggers relationship discovery when len(ACTIVE_DATASETS) > 1

### 2. AI Services (`services/ai_services.py`)
**Changes**:
- Added imports for `multi_file_queries` and `data_relationships`
- Added multi-file query detection logic
- Integrated relationship discovery and analysis context building
- Updated prompt generation with multi-file extensions
- Added multi-file context to all API responses
- Cache check skipped for multi-file queries (fresh analysis)

**New Response Fields**:
- `is_multi_file_analysis`: Boolean flag indicating multi-file query
- `multi_file_context`: Detailed context including:
  - `datasets_involved`: List of datasets used
  - `query_type`: Type of analysis (comparison, join, etc.)
  - `shared_columns`: Common columns for joins
  - `data_summary`: Rows, columns, data types for each file
  - `join_suggestions`: Recommended joins

## Workflow

### Multi-File Upload
```
1. User uploads multiple files
2. Each file processed and stored
3. upload_multiple_json() triggered
4. Relationships discovered (shared columns)
5. New columns, types detected
6. Relationship graph built and saved to MongoDB
7. Response includes relationship metadata
```

### Multi-File Query
```
1. User asks question about multiple files
2. generate_ai_response() called
3. Multi-file detection triggers relationship discovery
4. Relevant datasets identified based on query
5. Analysis context built (shared columns, data types, etc.)
6. Prompt extended with multi-file instructions
7. LLM generates response using all datasets
8. Multi-file context included in response
```

## Smart Features

### 1. Auto-Detection
- Automatically detects if query spans multiple files
- Keywords: "compare", "vs", "between", "join", "from both", "across", etc.
- Supports multiple file name mentions in query

### 2. Relationship Discovery
- Finds shared columns between datasets
- Detects column data types
- Builds joinable relationships
- Suggests optimal joining strategy

### 3. Query Type Classification
- **Comparison**: Side-by-side metric comparison
- **Join**: Cross-dataset relationship analysis
- **Correlation**: Pattern detection across files
- **Cross-dataset**: General multi-dataset queries

### 4. Dynamic Context
- Generates dataset summaries (rows, columns, types)
- Identifies numeric vs categorical columns
- Suggests join paths for unrelated files
- Creates LLM-optimized instructions

## Example Usage

### Upload Multiple Related Files
```json
POST /api/upload-multiple-json
{
  "files": [
    {
      "file_name": "sales_reps.csv",
      "data": [
        {"rep_id": 1, "name": "Rahul", "territory": "North"},
        {"rep_id": 2, "name": "Vikas", "territory": "South"}
      ]
    },
    {
      "file_name": "sales_data.csv",
      "data": [
        {"rep_id": 1, "amount": 50000, "month": "Jan"},
        {"rep_id": 2, "amount": 45000, "month": "Jan"}
      ]
    }
  ]
}
```

Response includes:
```json
{
  "relationships": {
    "shared_columns": {
      "sales_reps.csv_sales_data.csv": ["rep_id"]
    },
    "relationship_graph": {
      "sales_reps.csv": ["sales_data.csv"],
      "sales_data.csv": ["sales_reps.csv"]
    }
  }
}
```

### Query Spanning Multiple Files
```
User: "Compare revenue between Rahul and Vikas"
System: ✓ Detects multi-file query
        ✓ Identifies sales_reps.csv and sales_data.csv
        ✓ Shares rep_id is join key
        ✓ Analyzes revenue by sales rep across files
```

## Benefits

1. **Automatic Relationship Discovery**: No manual configuration needed
2. **Dynamic Analysis**: System adapts to any dataset structure
3. **Smart Joining**: Automatic detection of join keys
4. **Multi-Dataset Formulas**: Same analysis functions work across files
5. **Relationship Context**: LLM understands how files relate
6. **Scalable**: Works with 2+ files and complex relationships

## Files Modified
- `routes/upload.py` - Multi-file upload integration
- `services/ai_services.py` - Query processing integration

## Files Created
- `data_relationships.py` - Relationship discovery and management
- `multi_file_queries.py` - Multi-file query processing

## Next Steps (Optional Enhancements)
1. Automatic foreign key detection (not just matching columns)
2. Nested joins (file1 → file2 → file3)
3. Union operations for data consolidation
4. Time-series correlation analysis
5. Relationship strength scoring
6. Visual relationship diagrams in response
