"""
Test Suite for Revenue Per Lead (RPL) Analysis

Tests:
1. Basic RPL calculation with SugarCRM dataset
2. Column auto-detection
3. Calculation validation
4. Logging output verification
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
import json
import pandas as pd
from prompt_revenue_per_lead import RevenuePerLeadAnalyzer

# Configure logging to show in console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)


def print_test_header(test_num: int, test_name: str):
    """Print a formatted test header."""
    print("\n")
    print("=" * 80)
    print(f"TEST {test_num}: {test_name}")
    print("=" * 80)


def print_test_result(passed: bool, message: str = ""):
    """Print test result."""
    status = "✓ PASSED" if passed else "✗ FAILED"
    print(f"\n{status}")
    if message:
        print(f"  {message}")


def test_1_load_dataset():
    """Test 1: Load and inspect Revenue/Sales dataset."""
    print_test_header(1, "Load Revenue/Sales Dataset")
    
    try:
        dataset_path = project_root / "Zdata" / "revenue_data_sales_100.csv"
        
        if not dataset_path.exists():
            print(f"✗ Dataset not found at {dataset_path}")
            print_test_result(False, "Dataset file missing")
            return None
        
        print(f"Loading: {dataset_path}")
        df = pd.read_csv(dataset_path)
        
        print(f"\nDataset loaded successfully!")
        print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        print(f"  Columns: {list(df.columns)}")
        print(f"\nFirst 3 rows:")
        print(df.head(3).to_string())
        
        print_test_result(True, f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print_test_result(False, str(e))
        return None


def test_2_basic_rpl_analysis(df: pd.DataFrame):
    """Test 2: Run basic RPL analysis with auto-detected columns."""
    print_test_header(2, "Basic RPL Analysis (Auto-detect columns)")
    
    try:
        analyzer = RevenuePerLeadAnalyzer()
        
        # Run analysis with auto-detection
        result = analyzer.analyze_revenue_per_lead(
            dataset=df,
            group_by=None,  # Let it auto-detect
            query="Give me revenue-wise lead analysis"
        )
        
        print("\n\nANALYSIS RESULT:")
        print(json.dumps(result, indent=2, default=str))
        
        # Validate result
        passed = (
            result['validation']['passed'] and
            result['overall_metrics']['total_leads'] > 0 and
            result['overall_metrics']['total_revenue'] > 0
        )
        
        if passed:
            print_test_result(True, f"RPL = {result['overall_metrics']['revenue_per_lead']:,.2f}")
        else:
            print_test_result(False, "Validation failed")
        
        return result
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print_test_result(False, str(e))
        return None


def test_3_rpl_with_grouping(df: pd.DataFrame):
    """Test 3: RPL analysis with source/channel grouping."""
    print_test_header(3, "RPL Analysis with Grouping")
    
    try:
        analyzer = RevenuePerLeadAnalyzer()
        
        # Detect grouping column
        string_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        print(f"Available grouping columns: {string_cols}")
        
        if not string_cols:
            print("No string columns found for grouping")
            print_test_result(True, "Skipped - no grouping columns")
            return None
        
        # Try to use first string column as grouping
        group_col = string_cols[0]
        print(f"\nUsing grouping column: {group_col}")
        
        result = analyzer.analyze_revenue_per_lead(
            dataset=df,
            group_by=group_col,
            query=f"Revenue per lead by {group_col}"
        )
        
        # Validate: number of groups
        print("\n\nGROUPS FOUND:")
        if result['by_group']:
            for group in result['by_group']:
                print(f"  {group['group_value']:<20} Revenue: {group['revenue']:>12,.2f}  " +
                      f"Leads: {group['lead_count']:>5}  RPL: {group['rpl']:>10,.2f}")
        
        passed = (
            result['validation']['passed'] and
            len(result['by_group']) > 0
        )
        
        if passed:
            print_test_result(True, f"{len(result['by_group'])} groups analyzed")
        else:
            print_test_result(False, "Validation failed")
        
        return result
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print_test_result(False, str(e))
        return None


def test_4_calculation_validation(results: list):
    """Test 4: Validate RPL calculation accuracy."""
    print_test_header(4, "Calculation Validation")
    
    try:
        if not results or len(results) < 2:
            print("✗ Not enough previous results for validation")
            print_test_result(False, "Missing test data")
            return
        
        result = results[1]  # Use basic analysis result
        
        overall = result['overall_metrics']
        total_revenue = overall['total_revenue']
        total_leads = overall['total_leads']
        calculated_rpl = overall['revenue_per_lead']
        
        print(f"Overall Metrics:")
        print(f"  Total Revenue:  {total_revenue:,.2f}")
        print(f"  Total Leads:    {total_leads}")
        print(f"  Calculated RPL: {calculated_rpl:,.2f}")
        
        # Manual calculation
        if total_leads > 0:
            manual_rpl = total_revenue / total_leads
            print(f"\nManual Calculation:")
            print(f"  {total_revenue:,.2f} / {total_leads} = {manual_rpl:,.2f}")
            
            # Check if they match
            diff = abs(calculated_rpl - manual_rpl)
            match = diff < 0.01  # Allow for float rounding
            
            if match:
                print(f"\n✓ Calculations match (diff: {diff:.6f})")
            else:
                print(f"\n✗ Calculations don't match (diff: {diff:.2f})")
            
            print_test_result(match, f"RPL validation: {calculated_rpl:,.2f}")
        else:
            print("✗ No leads to validate")
            print_test_result(False, "Zero leads")
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print_test_result(False, str(e))


def test_5_group_validation(results: list):
    """Test 5: Validate group-level calculations."""
    print_test_header(5, "Group-level Calculation Validation")
    
    try:
        if not results or len(results) < 3:
            print("✗ Not enough previous results")
            print_test_result(False, "Missing test data")
            return
        
        result = results[2]  # Use grouped analysis result
        
        if not result['by_group']:
            print("No groups to validate")
            print_test_result(True, "Skipped - no groups")
            return
        
        print(f"Validating {len(result['by_group'])} groups:")
        
        all_passed = True
        
        for group in result['by_group']:
            group_val = group['group_value']
            revenue = group['revenue']
            leads = group['lead_count']
            rpl = group['rpl']
            
            # Check if RPL calculation is correct
            if leads > 0:
                expected_rpl = revenue / leads
                match = abs(rpl - expected_rpl) < 0.01
                
                if match:
                    print(f"  ✓ {group_val:<15} RPL correct: {rpl:,.2f}")
                else:
                    print(f"  ✗ {group_val:<15} RPL mismatch: {rpl:.2f} != {expected_rpl:.2f}")
                    all_passed = False
            else:
                if rpl == 0:
                    print(f"  ✓ {group_val:<15} RPL=0 for 0 leads")
                else:
                    print(f"  ✗ {group_val:<15} RPL should be 0 for 0 leads")
                    all_passed = False
        
        print_test_result(all_passed, "All group calculations validated")
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print_test_result(False, str(e))


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("REVENUE PER LEAD (RPL) ANALYSIS - TEST SUITE")
    print("=" * 80)
    
    results = []
    
    # Test 1: Load dataset
    df = test_1_load_dataset()
    if df is None:
        print("\n✗ Cannot continue - dataset failed to load")
        return
    
    # Test 2: Basic RPL analysis
    result2 = test_2_basic_rpl_analysis(df)
    if result2:
        results.append(result2)
    
    # Test 3: RPL with grouping
    result3 = test_3_rpl_with_grouping(df)
    if result3:
        results.append(result3)
    
    # Test 4: Calculation validation
    test_4_calculation_validation(results)
    
    # Test 5: Group validation
    test_5_group_validation(results)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
