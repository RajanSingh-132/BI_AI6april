import pandas as pd
import numpy as np

# Reproducibility
np.random.seed(42)

# Configuration: 12 months of data
months = pd.date_range(start='2024-01-01', periods=20, freq='ME').strftime('%Y-%m')
n = len(months)

data = {
    'Month': months,
    # Financials
    'Revenue_Actual': np.random.randint(45000, 60000, n),
    'Revenue_Target': [55000] * n,
    'Gross_Margin_Pct': np.random.uniform(60, 75, n).round(2),
    # Customer Experience
    'NPS': np.random.randint(30, 60, n),
    'Churn_Rate_Pct': np.random.uniform(2.0, 5.0, n).round(2),
    # Operations
    'Employee_Sat_Score': np.random.uniform(7.0, 9.5, n).round(1),
    'Lead_Response_Time_Hrs': np.random.uniform(1.5, 5.0, n).round(1)
}

df = pd.DataFrame(data)

# Normalize scores to a 0-100 scale
df['Finance_Score'] = ((df['Revenue_Actual'] / df['Revenue_Target']) * 100).clip(upper=100).round(2)
df['Customer_Score'] = (df['NPS'] / 60 * 100).round(2)  # 60 is the internal 'perfect' goal
df['Ops_Score'] = (df['Employee_Sat_Score'] / 10 * 100).round(2)

# Calculate Weighted Business Health Index
# Weights: Finance (40%), Customer (40%), Operations (20%)
df['BHI'] = (
    (df['Finance_Score'] * 0.4) + 
    (df['Customer_Score'] * 0.4) + 
    (df['Ops_Score'] * 0.2)
).round(2)

# Save to CSV
df.to_csv('business_health_data.csv', index=False)
print("CSV generated: 'business_health_data.csv'")
print(df[['Month', 'Revenue_Actual', 'NPS', 'BHI']].head())
