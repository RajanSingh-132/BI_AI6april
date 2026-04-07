#!/usr/bin/env python3
"""Test fixed revenue analyzer"""

from prompt_revenue import RevenueAnalyzer
import pandas as pd
from mongo_client import mongo_client

# Get the Sales_Revenue file from MongoDB
db = mongo_client.db
doc = db['documents'].find_one({'file_name': 'Sales_Revenue_From_Zoho_Leads.xlsx'})

if doc:
    data = doc.get('data', [])
    df = pd.DataFrame(data)
    
    print('=== TESTING FIXED REVENUE ANALYZER ===\n')
    print(f'Columns in dataset: {list(df.columns)}\n')
    
    analyzer = RevenueAnalyzer()
    result = analyzer.calculate_total_revenue(df, query='What is total revenue?')
    
    print('Result:')
    print(f'  Column identified: {result["revenue_column_identified"]}')
    print(f'  Total revenue: {result["total_revenue"]}')
    print(f'  Validation passed: {result["validation_passed"]}')
    
    print(f'\n✅ EXPECTED: 1260445')
    print(f'✅ GOT: {result["total_revenue"]}')
    print(f'✅ MATCH: {result["total_revenue"] == 1260445}')
    
    if result["total_revenue"] == 1260445:
        print('\n🎉 SUCCESS! The fix works correctly!')
    else:
        print('\n❌ ISSUE: Still getting wrong value')
else:
    print('File not found in MongoDB')
