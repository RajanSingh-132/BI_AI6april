import pandas as pd
from master_prompt import analyze_query

df = pd.read_csv('Zdata/revenue_data_sales_100.csv')

# TEST 5: Revenue-wise Lead Analysis
print('\n=== TEST 5: Revenue-wise Lead Analysis ===')
query = 'Show revenue by Lead_Source with lead counts'
result = analyze_query(query, df)
print('Query:', query)
print('Detected metrics:', result['_metadata']['semantic_intent']['metrics'])
print('Expected: should have both revenue and leads')
print('Has group_breakdown:', 'group_breakdown' in result)
print('Has metrics:', 'metrics' in result)
metrics_keys = list(result.get('metrics', {}).keys())
print('Metrics in result:', metrics_keys if metrics_keys else 'None')
print()

# TEST 7: Semantic Routing
print('=== TEST 7: Semantic Routing ===')
test_queries = [
    ('What is total revenue?', {'revenue'}),
    ('How many leads do we have?', {'leads'}),
    ('Revenue and leads comparison', {'revenue', 'leads'}),
    ('Revenue breakdown by lead source', {'revenue'}),
]

for query, expected in test_queries:
    result = analyze_query(query, df)
    detected = set(result['_metadata']['semantic_intent']['metrics'])
    match = '[OK]' if detected == expected else '[X]'
    print(f'{match} Query: {query}')
    print(f'     Expected: {expected}, Got: {detected}')
