#!/usr/bin/env python3
"""Debug revenue calculation discrepancy"""

from mongo_client import mongo_client
import json

# Check what collections exist
db = mongo_client.db
print('Collections in database:')
collections = db.list_collection_names()
for col in collections:
    print(f'  - {col}')

print('\n=== Checking documents collection ===')
docs_count = db['documents'].count_documents({})
print(f'Total documents: {docs_count}')

# Get info about uploaded files
file_docs = list(db['documents'].find({'type': 'dataset'}))
print(f'\nDataset documents: {len(file_docs)}')

for doc_idx, doc in enumerate(file_docs):
    print(f'\n--- Document {doc_idx + 1} ---')
    file_name = doc.get('file_name')
    print(f'File name: {file_name}')
    print(f'Rows: {doc.get("rows")}')
    print(f'Columns: {doc.get("columns")}')
    
    # Show first few rows of data
    data = doc.get('data', [])
    if data:
        print(f'\nFirst 3 rows:')
        for i, row in enumerate(data[:3]):
            print(f'  Row {i}: {row}')
        
        # Find numeric columns and sum them
        print(f'\nAnalyzing all {len(data)} rows...')
        numeric_cols = {}
        for row in data:
            for k, v in row.items():
                if isinstance(v, (int, float)):
                    if k not in numeric_cols:
                        numeric_cols[k] = []
                    numeric_cols[k].append(v)
        
        print(f'Numeric columns found: {list(numeric_cols.keys())}')
        for col, values in numeric_cols.items():
            total = sum(values)
            print(f'  {col}:')
            print(f'    SUM = {total}')
            print(f'    COUNT = {len(values)}')
            print(f'    MIN = {min(values)}')
            print(f'    MAX = {max(values)}')
            print(f'    AVG = {total / len(values):.2f}')

print('\n=== Checking what the system thinks is revenue ===')
# Check if there's any cached results
cached = list(db['cache'].find({'file': 'Sales_Revenue_From_Zoho_Leads.xlsx'}).limit(1))
if cached:
    print('Found cached result:')
    print(json.dumps(cached[0], indent=2, default=str))
else:
    print('No cached results found')
