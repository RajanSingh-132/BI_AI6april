#!/usr/bin/env python3
"""
Quick test of the new semantic-based analysis system.
Tests that semantic extraction works correctly without hardcoded types.
"""

import pandas as pd
from master_prompt import analyze_query
from pathlib import Path

# Load sample data
data_path = Path('Zdata') / 'revenue_data_sales_100.csv'
df = pd.read_csv(data_path)

print("[TEST] New Semantic-Based Analysis System\n")
print("=" * 70)

# Test 1: Simple total revenue
print("\n[TEST 1] Total Revenue Query")
print("-" * 70)
try:
    result = analyze_query('What is the total revenue?', df)
    print(f"[OK] Query executed successfully")
    print(f"  - Total Revenue: ${result.get('total_revenue', 'N/A'):,.2f}")
    intent = result['_metadata']['semantic_intent']
    print(f"  - Detected Metrics: {intent['metrics']}")
    print(f"  - Detected Operations: {intent['operations']}")
    print(f"  - Confidence: {result['_metadata']['confidence']:.1%}")
except Exception as e:
    print(f"[FAIL] {e}")

# Test 2: Revenue breakdown
print("\n[TEST 2] Revenue Breakdown Query")
print("-" * 70)
try:
    result = analyze_query('Show me revenue breakdown by Lead_Source', df)
    print(f"[OK] Query executed successfully")
    if 'group_breakdown' in result:
        print(f"  - Breakdown items: {len(result['group_breakdown'])}")
        for item in result['group_breakdown'][:3]:
            print(f"    * {item['entity_name']}: ${item['revenue']:,.2f}")
    intent = result['_metadata']['semantic_intent']
    print(f"  - Detected Metrics: {intent['metrics']}")
    print(f"  - Detected Dimensions: {intent['dimensions']}")
    print(f"  - Detected Operations: {intent['operations']}")
except Exception as e:
    print(f"[FAIL] {e}")

# Test 3: Total leads
print("\n[TEST 3] Total Leads Query")
print("-" * 70)
try:
    result = analyze_query('How many leads do we have?', df)
    print(f"[OK] Query executed successfully")
    print(f"  - Total Leads: {result.get('leads_after_filters', 'N/A')}")
    intent = result['_metadata']['semantic_intent']
    print(f"  - Detected Metrics: {intent['metrics']}")
    print(f"  - Detected Operations: {intent['operations']}")
except Exception as e:
    print(f"[FAIL] {e}")

# Test 4: Leads breakdown
print("\n[TEST 4] Leads Breakdown Query")
print("-" * 70)
try:
    result = analyze_query('Leads by source', df)
    print(f"[OK] Query executed successfully")
    if 'group_breakdown' in result:
        print(f"  - Breakdown items: {len(result['group_breakdown'])}")
        for item in result['group_breakdown'][:3]:
            print(f"    * {item['entity_name']}: {item['lead_count']} leads")
    intent = result['_metadata']['semantic_intent']
    print(f"  - Detected Dimensions: {intent['dimensions']}")
except Exception as e:
    print(f"[FAIL] {e}")

# Test 5: Combined analysis (both metrics)
print("\n[TEST 5] Combined Analysis Query")
print("-" * 70)
try:
    result = analyze_query('Show revenue and leads', df)
    print(f"[OK] Query executed successfully")
    if 'metrics' in result:
        print(f"  - Metrics in result: {list(result['metrics'].keys())}")
        for metric_key, data in result['metrics'].items():
            print(f"    * {metric_key}: {data.get('total', 'N/A')}")
    intent = result['_metadata']['semantic_intent']
    print(f"  - Detected Metrics: {intent['metrics']}")
    print(f"  - Is Combined: {intent['is_combined']}")
except Exception as e:
    print(f"[FAIL] {e}")

print("\n" + "=" * 70)
print("[SUMMARY] Dynamic semantic routing tests completed")
