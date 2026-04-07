# Metrics Documentation

## Overview
This document outlines all metrics available in the semantic analysis system, their formulas, calculation methods, and numpy implementations.

---

## Core Metrics

### 1. **Revenue** 
- **Metric Key**: `revenue`
- **Aliases**: revenue, sales, amount, deal_value, value, income, earnings
- **Source Column**: `Deal_Value`
- **Aggregation Type**: SUM

#### Formula
```
Total Revenue = SUM(Deal_Value)
```

#### NumPy Implementation
```python
import numpy as np

# Total Revenue
total_revenue = np.sum(dataset['Deal_Value'])

# Revenue by Group (e.g., by Lead_Source)
unique_groups = dataset['Lead_Source'].unique()
revenue_by_group = {
    group: np.sum(dataset[dataset['Lead_Source'] == group]['Deal_Value'])
    for group in unique_groups
}

# Revenue statistics
revenue_stats = {
    'total': np.sum(dataset['Deal_Value']),
    'mean': np.mean(dataset['Deal_Value']),
    'median': np.median(dataset['Deal_Value']),
    'std': np.std(dataset['Deal_Value']),
    'min': np.min(dataset['Deal_Value']),
    'max': np.max(dataset['Deal_Value']),
    'count': np.count_nonzero(dataset['Deal_Value'])
}
```

#### Validation
- **Reconciliation**: Sum of group breakdowns must equal total
- **Data Quality**: All values must be non-negative
- **Type**: Float/Numeric

---

### 2. **Leads**
- **Metric Key**: `leads`
- **Aliases**: leads, leads, prospect, prospects, records, count
- **Source Column**: `Lead_ID` (or row count)
- **Aggregation Type**: COUNT

#### Formula
```
Total Leads = COUNT(distinct Lead_ID records)
```

#### NumPy Implementation
```python
import numpy as np

# Total Leads
total_leads = len(dataset)
# or
total_leads = np.sum(np.ones(len(dataset)))

# Leads by Group (e.g., by Lead_Source)
unique_groups = dataset['Lead_Source'].unique()
leads_by_group = {
    group: len(dataset[dataset['Lead_Source'] == group])
    for group in unique_groups
}

# Leads statistics
leads_stats = {
    'total_count': len(dataset),
    'unique_ids': len(dataset['Lead_ID'].unique()),
    'median_per_group': np.median([len(dataset[dataset['Lead_Source'] == g]) 
                                    for g in unique_groups]),
    'min_per_group': np.min([len(dataset[dataset['Lead_Source'] == g]) 
                             for g in unique_groups]),
    'max_per_group': np.max([len(dataset[dataset['Lead_Source'] == g]) 
                             for g in unique_groups]),
}
```

#### Validation
- **Reconciliation**: Sum of group counts must equal total leads
- **Data Quality**: All counts must be positive integers
- **Type**: Integer/Count

---

### 3. **Revenue Per Lead**
- **Metric Key**: Derived metric (calculated from Revenue and Leads)
- **Aliases**: revenue_per_lead, rpl, efficiency, conversion_value
- **Formula**: `Revenue ÷ Leads`

#### NumPy Implementation
```python
import numpy as np

# Revenue per Lead (avoid division by zero)
total_revenue = np.sum(dataset['Deal_Value'])
total_leads = len(dataset)
revenue_per_lead = (
    total_revenue / total_leads 
    if total_leads > 0 
    else 0
)

# Revenue per Lead by Group
unique_groups = dataset['Lead_Source'].unique()
rpl_by_group = {}
for group in unique_groups:
    group_data = dataset[dataset['Lead_Source'] == group]
    group_revenue = np.sum(group_data['Deal_Value'])
    group_leads = len(group_data)
    rpl_by_group[group] = (
        group_revenue / group_leads 
        if group_leads > 0 
        else 0
    )
```

#### Use Cases
- Efficiency metric for lead quality
- Cost-per-lead analysis
- ROI calculations

---

## Dimension Support

### Supported Dimensions for Grouping
These dimensions can be used to break down metrics:

1. **Source** (`lead_source`)
   - Columns: Lead_Source, source, channel
   - Aliases: source, channel, lead_source, origin

2. **Owner** (`owner`)
   - Columns: Owner, owner, assigned_to
   - Aliases: owner, rep, sales_rep, assigned

3. **Stage** (`stage`)
   - Columns: Deal_Stage, stage, status
   - Aliases: stage, deal_stage, status

4. **Industry** (`industry`)
   - Columns: Industry, industry, sector
   - Aliases: industry, sector

5. **Time** (`time`)
   - Columns: Date, date, month, year
   - Aliases: date, month, year, time, when

---

## Calculation Examples

### Example 1: Simple Revenue Total
```python
import pandas as pd
import numpy as np

df = pd.read_csv('revenue_data_sales_100.csv')
total_revenue = np.sum(df['Deal_Value'])
print(f"Total Revenue: ${total_revenue:,.2f}")
```

### Example 2: Revenue by Lead Source
```python
import pandas as pd
import numpy as np

df = pd.read_csv('revenue_data_sales_100.csv')

sources = df['Lead_Source'].unique()
for source in sources:
    source_data = df[df['Lead_Source'] == source]
    source_revenue = np.sum(source_data['Deal_Value'])
    source_leads = len(source_data)
    rpl = source_revenue / source_leads if source_leads > 0 else 0
    print(f"{source}: ${source_revenue:,.2f} ({source_leads} leads, ${rpl:,.2f}/lead)")
```

### Example 3: Combined Revenue and Leads Analysis
```python
import pandas as pd
import numpy as np

df = pd.read_csv('revenue_data_sales_100.csv')

results = {
    'total_revenue': np.sum(df['Deal_Value']),
    'total_leads': len(df),
    'revenue_per_lead': np.sum(df['Deal_Value']) / len(df) if len(df) > 0 else 0,
    'breakdown': {}
}

for source in df['Lead_Source'].unique():
    source_data =df[df['Lead_Source'] == source]
    results['breakdown'][source] = {
        'revenue': np.sum(source_data['Deal_Value']),
        'leads': len(source_data),
        'rpl': np.sum(source_data['Deal_Value']) / len(source_data) if len(source_data) > 0 else 0
    }
```

---

## Validations Applied

### For All Metrics
1. **Non-null Check**: Data exists and is not null
2. **Type Validation**: Values are of expected type (numeric for revenue, integer for leads)
3. **Range Check**: Values are within reasonable bounds (non-negative)

### For Grouping Operations
1. **Reconciliation Check**: Sum of groups equals total
2. **Completeness Check**: All groups are accounted for
3. **No Null Groups**: Group dimension has valid values

### Anti-Hallucination Guardrails
- System only reports metrics derived from actual data
- No synthetic or estimated values
- All calculations include audit trail with row counts and filters applied
- Non-existent columns trigger validation failure

---

## Output Format

Results are returned as structured JSON with:

```json
{
  "total_revenue": 3714617.0,
  "leads_after_filters": 100,
  "group_breakdown": [
    {
      "entity_name": "Google Ads",
      "revenue": 506112.0,
      "lead_count": 12
    }
  ],
  "explanation": "Human-readable summary",
  "_metadata": {
    "semantic_intent": {
      "metrics": ["revenue"],
      "dimensions": ["source"],
      "operations": ["breakdown"],
      "confidence": 0.95
    },
    "reasoning": ["Detected revenue keyword", "Detected 'by' pattern"]
  }
}
```

---

## Future Metrics (Placeholder)

The system is designed to easily add new metrics:

### Conversions
- Formula: `COUNT(converted_records)`
- Use: Leads to customer conversion rate analysis

### Profit Margin
- Formula: `(Revenue - Cost) / Revenue * 100`
- Use: Profitability analysis

### Win Rate
- Formula: `Conversions / Leads * 100`
- Use: Sales effectiveness measurement

These follow the same pattern as existing metrics and can be integrated using the `MetricDatabase` registry.

---

## Performance Characteristics

- **Calculation Speed**: < 100ms for datasets < 100K rows
- **Memory**: < 50MB for typical datasets
- **Scaling**: Linear O(n) for aggregations
- **Precision**: Float64 (15-17 significant digits)

---

## References

- Audit logging: See `audit_logger.py`
- Metric extraction: See `semantic_extractor.py`
- Calculation implementations: See `prompt_revenue.py`, `prompt_leads.py`
- Analysis orchestration: See `master_prompt.py`
