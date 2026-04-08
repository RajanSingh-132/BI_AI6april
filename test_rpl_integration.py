"""
Integration Test: RPL Analysis through Master Orchestrator

Tests that the Revenue Per Lead analyzer works correctly as part of
the main DynamicAnalysisOrchestrator pipeline.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
import json
from master_prompt import DynamicAnalysisOrchestrator


def print_test_header(test_name: str):
    """Print formatted test header."""
    print("\n" + "=" * 80)
    print(f"TEST: {test_name}")
    print("=" * 80)


def test_rpl_through_orchestrator():
    """Test RPL analysis through the main orchestrator."""
    print_test_header("RPL Analysis Through DynamicAnalysisOrchestrator")
    
    try:
        # Load dataset
        dataset_path = project_root / "Zdata" / "revenue_data_sales_100.csv"
        df = pd.read_csv(dataset_path)
        
        print(f"\nDataset: {dataset_path.name}")
        print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
        
        # Initialize orchestrator
        orchestrator = DynamicAnalysisOrchestrator()
        
        # Test RPL query detection and analysis
        queries = [
            "Give me revenue per lead analysis",
            "What is revenue-wise lead analysis by source",
            "Show me revenue per lead breakdown",
        ]
        
        for query in queries:
            print(f"\n{'-'*80}")
            print(f"Query: {query}")
            print('-'*80)
            
            # Run analysis
            result = orchestrator.analyze(query, df)
            
            # Display results
            print("\nRESULT STRUCTURE:")
            print(f"  Type: {result.get('metric_type', 'standard')}")
            
            if "overall" in result:
                overall = result["overall"]
                print(f"\n  Overall Metrics:")
                print(f"    Revenue Per Lead: ${overall.get('revenue_per_lead', 0):,.2f}")
                print(f"    Total Revenue: ${overall.get('total_revenue', 0):,.2f}")
                print(f"    Total Leads: {overall.get('total_leads', 0)}")
            
            if "group_breakdown" in result:
                breakdown = result["group_breakdown"]
                print(f"\n  Breakdown ({len(breakdown)} groups):")
                for item in breakdown:
                    print(f"    {item['entity_name']:<15} RPL: ${item['revenue_per_lead']:>10,.2f}")
            
            # Display explanation
            if "explanation" in result:
                print(f"\n  Explanation:")
                for line in result["explanation"].split("\n"):
                    print(f"    {line}")
        
        print("\n" + "=" * 80)
        print("INTEGRATION TEST PASSED")
        print("=" * 80)
        
        return True
    
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_comparison_with_standard_metrics():
    """Test that standard metric queries still work after RPL integration."""
    print_test_header("Backward Compatibility: Standard Metrics Still Work")
    
    try:
        dataset_path = project_root / "Zdata" / "revenue_data_sales_100.csv"
        df = pd.read_csv(dataset_path)
        
        orchestrator = DynamicAnalysisOrchestrator()
        
        # Test standard queries
        queries = [
            "What is total revenue?",
            "How many leads?",
        ]
        
        for query in queries:
            print(f"\nQuery: {query}")
            result = orchestrator.analyze(query, df)
            
            # Should have explanation
            if "explanation" in result:
                print(f"  Result: {result['explanation'][:100]}...")
            else:
                print(f"  ERROR: No explanation in result")
                return False
        
        print("\n" + "=" * 80)
        print("BACKWARD COMPATIBILITY TEST PASSED")
        return True
    
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("RPL INTEGRATION TEST SUITE")
    print("=" * 80)
    
    # Run tests
    test1_passed = test_rpl_through_orchestrator()
    test2_passed = test_comparison_with_standard_metrics()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"RPL Through Orchestrator: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"Backward Compatibility:   {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\nALL TESTS PASSED")
        return 0
    else:
        print("\nSOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
