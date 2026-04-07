import pandas as pd
from master_prompt import analyze_query

df = pd.read_csv('Zdata/revenue_data_sales_100.csv')

query = 'Show revenue by Lead_Source with lead counts'
result = analyze_query(query, df)

print('\n=== DEBUG TEST 5 ===')
print('Query:', query)
print('\nDetected metrics:', result['_metadata']['semantic_intent']['metrics'])

# What the test expects
group_breakdown = result.get('group_breakdown', [])
metrics = result.get('metrics', {})

print('\nTest checks:')
print('  - len(group_breakdown) > 0:', len(group_breakdown) > 0)
print('  - Number of groups:', len(group_breakdown))

if 'revenue' in metrics:
    total_revenue = metrics['revenue'].get('total', 0)
    print(f'  - total_revenue from metrics: ${total_revenue:,.2f}')
else:
    total_revenue = result.get('total_revenue', 0)
    print(f'  - total_revenue at top level: ${total_revenue:,.2f}')

expected_revenue = float(df['Deal_Value'].sum())
print(f'  - expected_revenue: ${expected_revenue:,.2f}')
print(f'  - match: {abs(total_revenue - expected_revenue) < 0.01}')

print('\nResult structure:')
print('  Top-level keys:', [k for k in result.keys() if not k.startswith('_')][:5])
print('  Has group_breakdown:', 'group_breakdown' in result)
print('  Has metrics:', 'metrics' in result)
if 'metrics' in result:
    print('  Metrics sub-keys:', list(result['metrics'].keys()))
