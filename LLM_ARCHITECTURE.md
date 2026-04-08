

# LLM-Driven Semantic Analysis Architecture

## Overview
This system uses a **two-stage approach**:

1. **Query Intent Extraction** (SemanticExtractor): Uses regex + semantic keyword matching to understand what the user is asking for
2. **LLM-Driven Column Identification** (Analyzers): Uses Gemini LLM to intelligently select the right columns from any dataset schema

## Key Principle
**No Hardcoded Column Lists** - The LLM understands dataset schemas and makes intelligent decisions about which columns to use.

---

## Architecture Flow

```
User Query
    ↓
[SemanticExtractor] → Extracts Query Intent (regex + keyword matching)
    ↓
QueryIntent {
    requested_metrics: ["revenue", "leads"],
    requested_dimensions: ["source", "owner"],
    requested_operations: ["total", "breakdown"],
    is_asking_for_total: true,
    is_asking_for_breakdown: true,
    ...
}
    ↓
[DynamicAnalysisOrchestrator] → Routes to appropriate analyzer
    ↓
[RevenueAnalyzer/LeadsAnalyzer] → LLM identifies correct columns
    ↓
[Gemini LLM] → "Given this schema, which column represents revenue?"
    ↓
[Analyzer] → Performs calculation on identified column
    ↓
Result JSON with explanation
```

---

## Components

### 1. `semantic_extractor.py` - Query Intent Analysis
**Purpose**: Understand what the user is asking for (NOT which columns to use)

**Uses**: Regex + keyword matching on query text
**Returns**: `QueryIntent` object with:
- `requested_metrics`: ["revenue", "leads", etc.]
- `requested_dimensions`: ["source", "owner", etc.]
- `requested_operations`: ["sum", "count", "breakdown", "compare"]
- Boolean flags: `is_asking_for_total`, `is_asking_for_breakdown`, etc.

**Key Point**: This layer makes NO decisions about column names. It only understands user intent.

### 2. `prompt_revenue_llm.py` - LLM-Driven Revenue Analysis
**Purpose**: Calculate revenue by intelligently identifying the revenue column

**Architecture**:
1. Receives dataset and query
2. Extracts dataset schema (column names, types, sample values)
3. Sends schema to Gemini LLM with `COLUMN_IDENTIFICATION_PROMPT`
4. LLM analyzes schema and returns chosen column
5. Performs calculation on that column

**Column Selection Logic (LLM decides)**:
- Prefers "revenue_earned" over "deal_amount" (understands semantic difference)
- Considers column names, data types, sample values
- Falls back to regex matching if LLM unavailable

**Fallback**: If Gemini unavailable, uses regex pattern matching on column names

### 3. `prompt_leads_llm.py` - LLM-Driven Leads Analysis
**Purpose**: Calculate leads by intelligently identifying the lead count method

**Architecture**: Same as revenue analyzer
**Lead Counting Methods**:
- Count distinct values in a "lead_id" column
- Count total rows (if each row = one lead)
- LLM decides which method based on schema

### 4. `master_prompt.py` - Orchestration
**Purpose**: Route queries to appropriate analyzer based on semantic intent

**Flow**:
1. Extract query intent using `SemanticExtractor`
2. Identify which metrics are requested
3. Route to `RevenueAnalyzer` for revenue
4. Route to `LeadsAnalyzer` for leads
5. Combine results if multiple metrics requested

---

## Key Design Decisions

### Why Two Stages?

| Stage | Tool | Purpose | Why? |
|-------|------|---------|------|
| Query Intent | Regex + Semantic | What is user asking? | Fast, deterministic, no API calls |
| Column ID | LLM | Which columns represent that? | Flexible, adapts to any schema, understands semantics |

### Why LLM for Column Identification?

1. **Flexibility**: Works with ANY dataset schema, not just predefined columns
2. **Semantic Understanding**: Knows "revenue_earned" ≠ "deal_amount" (actual vs potential)
3. **Scalability**: New column names don't require code changes
4. **Context Aware**: Can make intelligent choices based on data patterns

### Fallback Strategy

```
Try LLM → Fails or unavailable?
    ↓
Use Regex Pattern Matching
    ↓
Still fails?
    ↓
Return error with helpful message
```

---

## Column Identification Prompts

### Revenue Column Identification
```
AI can understand:
- Column naming conventions
- Data types (should be numeric)
- Sample values
- Column context ("deal_amount" vs "revenue_earned")
```

### Example: Multiple Numeric Columns
Dataset has:
- `deal_amount_(₹)` = 7,391,705 (deal potential)
- `revenue_earned_(₹)` = 1,260,445 (actual earned)

**LLM decides**: Use `revenue_earned_(₹)` because:
-  Contains "earned" keyword (indicates actual, not potential)
- Semantically matches user query "total revenue"
- More accurate for business analysis

---

## Query Flow Example

**User**: "What is total revenue by source?"

**Step 1: Query Intent Extraction**
```python
SemanticExtractor.extract_intent("What is total revenue by source?")
→ QueryIntent {
    requested_metrics: {"revenue"},
    requested_dimensions: {"source"},
    is_asking_for_total: true,
    is_asking_for_breakdown: true
  }
```

**Step 2: Routing**
```
Metrics = ["revenue"] 
→ Route to RevenueAnalyzer
Dimension = "source"
→ Add GROUP BY instruction
```

**Step 3: LLM Column Identification**
```
RevenueAnalyzer sends schema to Gemini:
  "Given this dataset with columns: deal_amount_(₹), revenue_earned_(₹), ...
   which represents revenue?"
   
Gemini response: "revenue_earned_(₹)" 
  Reasoning: "Contains explicit 'earned' keyword, semantic match for actual revenue"
```

**Step 4: Calculation**
```python
revenue_analyzer.calculate_total_revenue(dataset)
→ SUM(revenue_earned_(₹)) by source
→ Return grouped breakdown
```

---

## Error Handling

### When Column Cannot Be Identified
1. **LLM fails**: Log attempt, fall back to regex
2. **Regex fails**: Return error with schema info
3. **Schema analysis fails**: Return helpful message about required data structure

### When Calculation Fails
1. Log error with context
2. Return validation error
3. Provide notes about what went wrong

---

## Testing the System

### Test 1: LLM Column Identification  
```python
from prompt_revenue_llm import RevenueAnalyzer

analyzer = RevenueAnalyzer()
result = analyzer.calculate_total_revenue(dataset_with_complex_columns)

# System should correctly identify revenue_earned
assert result["revenue_column_identified"] == "revenue_earned_(₹)"
assert result["total_revenue"] == 1260445
```

### Test 2: Fallback to Regex
```python
# Disable LLM (set GEMINI_API_KEY to empty)
# System should still work using regex patterns

result = analyzer.calculate_total_revenue(dataset)
# Should fall back to keyword matching
```

### Test 3: Query Intent
```python
from semantic_extractor import SemanticExtractor

extractor = SemanticExtractor()
intent = extractor.extract_intent("Compare revenue and leads by owner")

assert "revenue" in intent.requested_metrics
assert "leads" in intent.requested_metrics
assert "owner" in intent.requested_dimensions
assert intent.is_asking_for_comparison == true
```

---

## Future Enhancements

1. **Multi-Dataset Analysis**: LLM joins columns across datasets
2. **Formula Validation**: LLM verifies calculations match business logic
3. **Insight Generation**: LLM explains patterns found in data
4. **Custom Metrics**: LLM can identify composite metrics (e.g., revenue per lead)

---

## Configuration

### Environment Variables
```bash
GEMINI_API_KEY=your_api_key  # Required for LLM column identification
```

### Fallback Behavior
- If `GEMINI_API_KEY` not set: Uses regex + fallback keyword matching
- If Gemini API fails: Retries up to 2 times, then falls back
- If all fail: Returns error with available columns for user to specify

---

## Summary

This architecture achieves **true semantic understanding**:
- ✅ Query intent is extracted via fast regex + keywords
- ✅ Column identification is intelligent via LLM
- ✅ No hardcoded columns lists in analyzers
- ✅ Adapts to any dataset schema automatically
- ✅ Provides fallback when LLM unavailable

The system is **flexible, scalable, and maintainable**.
