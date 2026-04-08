#!/usr/bin/env python3
"""Test the new LLM-driven revenue analyzer"""

import sys
from prompt_revenue_llm import RevenueAnalyzer
import pandas as pd
from mongo_client import mongo_client

print("=== Testing LLM-Driven Revenue Analyzer ===\n")

# Get test data from MongoDB
db = mongo_client.db
doc = db['documents'].find_one({'file_name': 'Sales_Revenue_From_Zoho_Leads.xlsx'})

if not doc:
    print("ERROR: Test data not found in MongoDB")
    sys.exit(1)

data = doc.get('data', [])
df = pd.DataFrame(data)

print(f"Dataset: {doc.get('file_name')}")
print(f"Rows: {len(df)}")
print(f"Columns: {list(df.columns)}\n")

# Test the analyzer
analyzer = RevenueAnalyzer()

print("Testing LLM column identification...\n")
result = analyzer.calculate_total_revenue(df, query='What is the total revenue?')

print("Result:")
print(f"  Column identified: {result['revenue_column_identified']}")
print(f"  Total revenue: {result['total_revenue']}")
print(f"  Validation passed: {result['validation_passed']}")
print(f"  Notes: {result['validation_notes']}")

print(f"\n✅ EXPECTED: 1260445")
print(f"✅ GOT: {result['total_revenue']}")

if result['total_revenue'] == 1260445:
    print("\n🎉 SUCCESS! LLM-driven analyzer works correctly!")
    sys.exit(0)
else:
    print("\n❌ ISSUE: Still getting wrong value")
    sys.exit(1)
