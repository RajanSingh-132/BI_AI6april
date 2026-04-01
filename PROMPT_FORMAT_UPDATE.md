# Prompt Formatting Update - Format Only

Updated the `RESPONSE FORMAT` section in `prompt.py` to provide structured, clean output formatting.

## Changes Made

### Old Format
- Generic HTML tags (`<p>`, `<strong>`, `<ul>`)
- Unstructured layout
- No clear section separation

### New Format

```
ANALYSIS
--------------------------------------------------
Clear explanation of data analysis

FORMULA USED
--------------------------------------------------
1. Formula Name = Formula with columns
2. Formula Name = Formula with columns
3. Formula Name = Formula with columns

KEY INSIGHTS
--------------------------------------------------
• Insight 1 with numbers and context
• Insight 2 with names and values
• Insight 3 with comparisons

RECOMMENDATIONS & ACTION ITEMS
--------------------------------------------------
1. Specific actionable recommendation
2. Strategy based on findings
3. Resource optimization opportunity
```

## Format Requirements

**ANALYSIS Section:**
- Clear explanation of what was calculated
- Business context and key findings
- No markdown or HTML

**FORMULA USED Section:**
- Numbered list of formulas
- Include function names: SUM(), COUNT(), AVERAGE(), MAX(), MIN()
- Show column mappings with currency/units: `expected_revenue_(₹)`
- Include WHERE conditions if applicable

**KEY INSIGHTS Section:**
- Bullet points (•) for each insight
- Include: Owner Name, Industry, Values with currency/percentage
- Quantified findings with business meaning
- Top/Bottom/Best/Worst cases with names

**RECOMMENDATIONS & ACTION ITEMS Section:**
- Numbered list (1., 2., 3.)
- Specific, actionable items
- At least 2-3 recommendations
- Based on data analysis findings

## Cleanliness Rules

✅ No markdown (*bold*, _italic_)  
✅ No HTML tags (<p>, <div>, etc.)  
✅ Use section headers with dashes (---)  
✅ Use bullet points (•) for lists  
✅ Use numbered lists (1.) for actions  

## KPI JSON Structure

```json
{
  "name": "Total Revenue",
  "value": 188827.69,
  "unit": "₹",
  "insight": "Detailed business analysis with context...",
  "owner_name": "Rahul Sharma",
  "formula_used": "SUM(expected_revenue_(₹))"
}
```

## File Modified
- `prompt.py` - Updated RESPONSE FORMAT section (formatting only)

## Result

LLM will now produce responses formatted as:
- Clear section separation
- Visible formulas with function names
- Owner/Person names in insights
- Quantified, actionable recommendations
- No markdown or HTML clutter
