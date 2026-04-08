"""
Revenue Per Lead (RPL) Analysis Module
Formula: RPL = Revenue by Channel / Total Leads from Channel

This module calculates revenue efficiency metrics by analyzing:
1. Total revenue generated from each channel/group
2. Total lead count from each channel/group  
3. Revenue per lead (RPL) = revenue / leads

Comprehensive logging tracks all calculations, groupings, and validations.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Tuple
from audit_logger import get_logger

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger(__name__)


class RevenuePerLeadAnalyzer:
    """
    Analyzes revenue efficiency per lead by channel/dimension.
    
    Formula: RPL = Sum(revenue) / Count(leads) per channel
    
    With comprehensive logging for:
    - Column detection and validation
    - Revenue calculation by channel
    - Lead count by channel
    - RPL calculation
    - Data validation
    """
    
    def __init__(self):
        self.audit_logger = get_logger()
        self.logger = logging.getLogger(__name__)
        self._reset_calculation_state()
    
    def _reset_calculation_state(self):
        """Reset internal state for a new calculation."""
        self.revenue_column = None
        self.lead_id_column = None
        self.group_column = None
        self.total_rows = 0
        self.revenue_sum = 0.0
        self.lead_count = 0
    
    def _log_section(self, title: str, level: str = "INFO"):
        """Log a section header for clarity."""
        separator = "=" * 70
        print(f"\n{separator}")
        print(f">>> {title}")
        print(f"{separator}")
        getattr(self.logger, level.lower())(f"\n{title}")
    
    def _log_step(self, step: str, detail: str):
        """Log a processing step."""
        print(f"\n[STEP] {step}")
        print(f"       {detail}")
        self.logger.info(f"[STEP] {step}: {detail}")
    
    def _analyze_dataset_schema(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze dataset structure and detect key columns.
        
        Returns: {
            'total_rows': int,
            'columns': [list],
            'numeric_columns': [list],
            'string_columns': [list],
            'sample_data': dict
        }
        """
        self._log_step("Dataset Analysis", f"Analyzing schema of {len(df)} rows")
        
        schema = {
            'total_rows': len(df),
            'columns': [],
            'numeric_columns': [],
            'string_columns': [],
            'sample_data': {}
        }
        
        self.total_rows = len(df)
        
        for col in df.columns:
            col_info = {
                'name': col,
                'dtype': str(df[col].dtype),
                'non_null_count': df[col].notna().sum(),
                'null_count': df[col].isna().sum(),
                'unique_values': df[col].nunique()
            }
            
            schema['columns'].append(col)
            
            if pd.api.types.is_numeric_dtype(df[col]):
                schema['numeric_columns'].append(col)
                col_info['sample_value'] = df[col].iloc[0] if len(df) > 0 else None
                col_info['min'] = df[col].min()
                col_info['max'] = df[col].max()
                col_info['sum'] = df[col].sum()
            else:
                schema['string_columns'].append(col)
                col_info['sample_value'] = str(df[col].iloc[0]) if len(df) > 0 else None
                col_info['unique_samples'] = df[col].dropna().unique()[:3].tolist()
            
            schema['sample_data'][col] = col_info
            print(f"  [{col_info['dtype']}] {col}: {col_info['unique_values']} unique, {col_info['non_null_count']} non-null")
        
        print(f"\nDetails:")
        print(f"  Total columns: {len(schema['columns'])}")
        print(f"  Numeric columns: {len(schema['numeric_columns'])} {schema['numeric_columns']}")
        print(f"  String/category columns: {len(schema['string_columns'])} {schema['string_columns']}")
        
        self.logger.info(f"[SCHEMA] Detected {len(schema['columns'])} columns")
        self.logger.info(f"[SCHEMA] Numeric: {schema['numeric_columns']}")
        self.logger.info(f"[SCHEMA] Categorical: {schema['string_columns']}")
        
        return schema
    
    def _detect_revenue_column(self, df: pd.DataFrame, schema: Dict) -> Tuple[str, bool]:
        """
        Detect revenue column using semantic understanding.
        
        Returns: (column_name, success)
        """
        self._log_step("Revenue Column Detection", "Searching for revenue column")
        
        # Priority keywords for revenue
        revenue_keywords = [
            'revenue_earned', 'revenue', 'earned', 'amount', 'sales', 
            'deal_value', 'value', 'total_amount'
        ]
        
        for keyword in revenue_keywords:
            for col in schema['numeric_columns']:
                if keyword in col.lower():
                    print(f"  FOUND: '{col}' matches keyword '{keyword}'")
                    print(f"         Type: {df[col].dtype}, Sum: {df[col].sum():.2f}")
                    self.logger.info(f"[REVENUE] Detected column: {col}")
                    self.revenue_column = col
                    return col, True
        
        # If no match, use first numeric column as fallback
        if schema['numeric_columns']:
            col = schema['numeric_columns'][0]
            print(f"  FALLBACK: Using first numeric column '{col}'")
            self.logger.warning(f"[REVENUE] Using fallback column: {col}")
            self.revenue_column = col
            return col, True
        
        print(f"  ERROR: No revenue column found")
        self.logger.error("[REVENUE] No revenue column detected")
        return "", False
    
    def _detect_lead_column(self, df: pd.DataFrame, schema: Dict) -> Tuple[str, bool]:
        """
        Detect lead ID column.
        
        Returns: (column_name, success)
        """
        self._log_step("Lead ID Column Detection", "Searching for lead identifier column")
        
        # Priority keywords for lead ID
        lead_keywords = ['lead_id', 'id', 'lead', 'account_id', 'contact_id']
        
        for keyword in lead_keywords:
            for col in df.columns:
                if keyword in col.lower():
                    print(f"  FOUND: '{col}' matches keyword '{keyword}'")
                    print(f"         Type: {df[col].dtype}, Unique values: {df[col].nunique()}")
                    self.logger.info(f"[LEAD_ID] Detected column: {col}")
                    self.lead_id_column = col
                    return col, True
        
        # If no match, use first column as fallback
        if len(df.columns) > 0:
            col = df.columns[0]
            print(f"  FALLBACK: Using first column '{col}' as lead identifier")
            self.logger.warning(f"[LEAD_ID] Using fallback column: {col}")
            self.lead_id_column = col
            return col, True
        
        print(f"  ERROR: No lead column found")
        self.logger.error("[LEAD_ID] No lead column detected")
        return "", False
    
    def _detect_group_column(self, df: pd.DataFrame, schema: Dict, preferred: Optional[str] = None) -> Tuple[str, bool]:
        """
        Detect grouping column (channel, stage, source, etc).
        
        Returns: (column_name, success)
        """
        self._log_step("Group Column Detection", "Searching for grouping dimension")
        
        # Priority keywords for grouping dimensions
        group_keywords = ['source', 'channel', 'stage', 'owner', 'industry', 'region']
        
        # If preferred column specified, use it first
        if preferred and preferred in df.columns:
            print(f"  PREFERRED: Using specified column '{preferred}'")
            print(f"             Unique values: {df[preferred].nunique()}")
            self.logger.info(f"[GROUP] Using preferred column: {preferred}")
            self.group_column = preferred
            return preferred, True
        
        # Search for matching columns
        for keyword in group_keywords:
            for col in schema['string_columns']:
                if keyword in col.lower():
                    print(f"  FOUND: '{col}' matches keyword '{keyword}'")
                    print(f"         Unique values: {df[col].nunique()}")
                    self.logger.info(f"[GROUP] Detected column: {col}")
                    self.group_column = col
                    return col, True
        
        print(f"  WARNING: No grouping column found, will use overall totals")
        self.logger.warning("[GROUP] No grouping column detected")
        return "", True  # Not an error - can still calculate overall RPL
    
    def _calculate_revenue_by_group(self, df: pd.DataFrame, group_col: str) -> Dict[str, float]:
        """
        Calculate total revenue for each group.
        
        Returns: {'group_value': revenue_sum, ...}
        """
        self._log_step(
            "Revenue Calculation by Group",
            f"Summing '{self.revenue_column}' grouped by '{group_col}'"
        )
        
        revenue_by_group = df.groupby(group_col, dropna=False)[self.revenue_column].sum().to_dict()
        
        total_calculated = sum(revenue_by_group.values())
        
        print(f"\n  Groups found: {len(revenue_by_group)}")
        print(f"  Total revenue across groups: {total_calculated:,.2f}")
        print(f"\n  Revenue by group:")
        for group_val, revenue in sorted(revenue_by_group.items(), key=lambda x: x[1], reverse=True):
            print(f"    [{group_val:<20}] = {revenue:>15,.2f}")
        
        self.logger.info(f"[REVENUE_BY_GROUP] Calculated {len(revenue_by_group)} groups")
        self.logger.info(f"[REVENUE_BY_GROUP] Total: {total_calculated}")
        
        return revenue_by_group
    
    def _calculate_leads_by_group(self, df: pd.DataFrame, group_col: str) -> Dict[str, int]:
        """
        Calculate total leads for each group.
        
        Returns: {'group_value': lead_count, ...}
        """
        self._log_step(
            "Lead Count Calculation by Group",
            f"Counting distinct '{self.lead_id_column}' grouped by '{group_col}'"
        )
        
        leads_by_group = df.groupby(group_col, dropna=False)[self.lead_id_column].nunique().to_dict()
        
        total_leads = sum(leads_by_group.values())
        
        print(f"\n  Groups found: {len(leads_by_group)}")
        print(f"  Total leads across groups: {total_leads}")
        print(f"\n  Leads by group:")
        for group_val, count in sorted(leads_by_group.items(), key=lambda x: x[1], reverse=True):
            print(f"    [{group_val:<20}] = {count:>10} leads")
        
        self.lead_count = total_leads
        
        self.logger.info(f"[LEADS_BY_GROUP] Calculated {len(leads_by_group)} groups")
        self.logger.info(f"[LEADS_BY_GROUP] Total: {total_leads} leads")
        
        return leads_by_group
    
    def _calculate_rpl(self, revenue: float, leads: int) -> float:
        """
        Calculate Revenue Per Lead.
        
        Formula: RPL = Revenue / Leads
        
        Returns: rpl_value (0 if no leads)
        """
        if leads == 0:
            self.logger.warning("[RPL] Zero leads detected, RPL = 0")
            return 0.0
        
        rpl = revenue / leads
        return rpl
    
    def analyze_revenue_per_lead(
        self,
        dataset: pd.DataFrame,
        group_by: Optional[str] = None,
        query: str = ""
    ) -> Dict[str, Any]:
        """
        Main analysis function: Calculate RPL metrics.
        
        Args:
            dataset: DataFrame with revenue and lead data
            group_by: Column to group by (e.g., 'Lead_Source')
            query: Original user query (for logging)
        
        Returns: {
            'query': user_query,
            'columns_used': {revenue, lead_id, group},
            'overall_metrics': {revenue, leads, rpl},
            'by_group': [{'group': val, 'revenue': x, 'leads': y, 'rpl': z}],
            'validation': {passed, notes},
            'calculations_log': [...]
        }
        """
        self._reset_calculation_state()
        
        self._log_section(f"REVENUE PER LEAD ANALYSIS", "INFO")
        print(f"Query: '{query}'")
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"REVENUE PER LEAD ANALYSIS")
        self.logger.info(f"Query: {query}")
        self.logger.info(f"{'='*70}")
        
        try:
            # Step 1: Analyze schema
            schema = self._analyze_dataset_schema(dataset)
            
            # Step 2: Detect columns
            revenue_col, revenue_ok = self._detect_revenue_column(dataset, schema)
            if not revenue_ok:
                return self._create_error_response("Revenue column not found", query)
            
            lead_col, lead_ok = self._detect_lead_column(dataset, schema)
            if not lead_ok:
                return self._create_error_response("Lead ID column not found", query)
            
            group_col, group_ok = self._detect_group_column(dataset, schema, group_by)
            
            self._log_section("COLUMNS SELECTED", "INFO")
            print(f"  Revenue Column:  {revenue_col}")
            print(f"  Lead ID Column:  {lead_col}")
            print(f"  Group Column:    {group_col if group_col else '(none - overall only)'}")
            
            # Step 3: Calculate overall metrics
            self._log_section("OVERALL METRICS CALCULATION", "INFO")
            
            total_revenue = dataset[revenue_col].sum()
            total_leads = dataset[lead_col].nunique()
            overall_rpl = self._calculate_rpl(total_revenue, total_leads)
            
            print(f"\n  Total Revenue:  {total_revenue:,.2f}")
            print(f"  Total Leads:    {total_leads}")
            print(f"  RPL (Overall):  {overall_rpl:,.2f}")
            
            self.logger.info(f"[OVERALL] Revenue: {total_revenue}, Leads: {total_leads}, RPL: {overall_rpl}")
            
            # Step 4: Calculate by-group metrics if requested
            by_group = []
            
            if group_col:
                self._log_section("GROUP BREAKDOWN ANALYSIS", "INFO")
                
                revenue_by_group = self._calculate_revenue_by_group(dataset, group_col)
                leads_by_group = self._calculate_leads_by_group(dataset, group_col)
                
                # Combine results
                self._log_step("RPL Calculation by Group", "Computing RPL for each group")
                
                for group_val in sorted(revenue_by_group.keys()):
                    revenue = revenue_by_group.get(group_val, 0)
                    leads = leads_by_group.get(group_val, 0)
                    rpl = self._calculate_rpl(revenue, leads)
                    
                    by_group.append({
                        'group_value': str(group_val),
                        'revenue': float(revenue),
                        'lead_count': int(leads),
                        'rpl': float(rpl)
                    })
                    
                    print(f"  [{group_val:<20}] Revenue: {revenue:>12,.2f}  |  Leads: {leads:>5}  |  RPL: {rpl:>10,.2f}")
                
                # Validate sums match total
                validation_revenue = sum([g['revenue'] for g in by_group])
                validation_leads = sum([g['lead_count'] for g in by_group])
                
                print(f"\n  Validation Check:")
                print(f"    Sum of group revenue: {validation_revenue:,.2f} (total: {total_revenue:,.2f})")
                print(f"    Sum of group leads:   {validation_leads} (total: {total_leads})")
            
            # Step 5: Validation
            self._log_section("VALIDATION", "INFO")
            
            validation_notes = []
            validation_passed = True
            
            if total_leads == 0:
                validation_notes.append("WARNING: Zero leads in dataset")
                validation_passed = False
            
            if total_revenue == 0:
                validation_notes.append("WARNING: Zero revenue in dataset")
                validation_passed = False
            
            if by_group:
                sum_leads = sum([g['lead_count'] for g in by_group])
                sum_revenue = sum([g['revenue'] for g in by_group])
                
                if sum_leads != total_leads:
                    validation_notes.append(f"ERROR: Group lead sum {sum_leads} != total {total_leads}")
                    validation_passed = False
                else:
                    print(f"  ✓ Lead count validation: {sum_leads} == {total_leads}")
                
                if abs(sum_revenue - total_revenue) > 0.01:  # Allow for float rounding
                    validation_notes.append(f"ERROR: Group revenue sum {sum_revenue:.2f} != total {total_revenue:.2f}")
                    validation_passed = False
                else:
                    print(f"  ✓ Revenue sum validation: {sum_revenue:.2f} == {total_revenue:.2f}")
            
            if validation_passed:
                print(f"  ✓ VALIDATION PASSED")
                self.logger.info("[VALIDATION] PASSED")
            else:
                print(f"  ✗ VALIDATION FAILED")
                self.logger.warning("[VALIDATION] FAILED - " + "; ".join(validation_notes))
            
            # Create response
            response = {
                'query': query,
                'columns_used': {
                    'revenue': revenue_col,
                    'lead_id': lead_col,
                    'group': group_col or None
                },
                'overall_metrics': {
                    'total_revenue': float(total_revenue),
                    'total_leads': int(total_leads),
                    'revenue_per_lead': float(overall_rpl)
                },
                'by_group': by_group,
                'validation': {
                    'passed': validation_passed,
                    'notes': validation_notes
                }
            }
            
            self._log_section("ANALYSIS COMPLETE", "INFO")
            print(f"\nSummary:")
            print(f"  Overall RPL: {overall_rpl:,.2f}")
            print(f"  Groups analyzed: {len(by_group)}")
            print(f"  Validation: {'PASSED' if validation_passed else 'FAILED'}")
            
            return response
        
        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            self.logger.error(f"[ERROR] {error_msg}")
            return self._create_error_response(error_msg, query)
    
    def _create_error_response(self, error_msg: str, query: str) -> Dict[str, Any]:
        """Create error response structure."""
        print(f"\n✗ ERROR: {error_msg}")
        return {
            'query': query,
            'columns_used': {},
            'overall_metrics': {
                'total_revenue': 0.0,
                'total_leads': 0,
                'revenue_per_lead': 0.0
            },
            'by_group': [],
            'validation': {
                'passed': False,
                'notes': [error_msg]
            }
        }
