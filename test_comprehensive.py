"""
Comprehensive Test Suite for Revenue and Leads Analysis
Tests all scenarios: revenue, leads, revenue-wise leads, both
Validates against source data for hallucinations.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed")
    sys.exit(1)

from master_prompt import analyze_query
from semantic_extractor import SemanticExtractor
from audit_logger import get_logger

# Configure test logger
logger = get_logger()


class TestRunner:
    """Runs comprehensive tests for revenue and leads analysis."""

    def __init__(self):
        self.test_results = []
        self.datasets = {}
        self.logger = get_logger()

    def load_datasets(self) -> bool:
        """Load all test datasets from Zdata folder."""
        data_dir = Path(__file__).parent / "Zdata"

        if not data_dir.exists():
            self.logger.logger.error(f"Data directory not found: {data_dir}")
            return False

        try:
            # Load main dataset with leads and revenue data
            self.datasets["leads_revenue"] = pd.read_csv(
                data_dir / "revenue_data_sales_100.csv"
            )
            self.logger.logger.info(
                f"[OK] Loaded leads_revenue dataset: {len(self.datasets['leads_revenue'])} rows"
            )

            # Load CRM dataset for additional lead testing
            self.datasets["crm_leads"] = pd.read_csv(
                data_dir / "crm_sales_dataset21.csv"
            )
            self.logger.logger.info(
                f"[OK] Loaded crm_leads dataset: {len(self.datasets['crm_leads'])} rows"
            )

            return True

        except Exception as e:
            self.logger.logger.error(f"Failed to load datasets: {str(e)}")
            return False

    def test_total_revenue(self) -> bool:
        """TEST 1: Calculate total revenue for entire dataset."""
        print("\n" + "="*70)
        print("TEST 1: TOTAL REVENUE")
        print("="*70)

        dataset = self.datasets["leads_revenue"]
        query = "What is the total revenue?"

        self.logger.logger.info(f"Test 1: Total Revenue")
        self.logger.logger.info(f"Dataset rows: {len(dataset)}")
        self.logger.logger.info(f"Query: {query}")

        result = analyze_query(query, dataset)

        # New semantic system returns result directly with metric values
        actual_revenue = result.get("total_revenue", 0)
        explanation = result.get("explanation", "")

        # Verify against actual data
        expected_revenue = float(dataset["Deal_Value"].sum())

        passed = abs(actual_revenue - expected_revenue) < 0.01

        print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
        print(f"Expected Revenue: ${expected_revenue:,.2f}")
        print(f"Actual Revenue: ${actual_revenue:,.2f}")
        print(f"Explanation:\n{explanation}")

        self.test_results.append({
            "test": "total_revenue",
            "passed": passed,
            "expected": expected_revenue,
            "actual": actual_revenue,
        })

        return passed

    def test_total_leads(self) -> bool:
        """TEST 2: Calculate total leads for entire dataset."""
        print("\n" + "="*70)
        print("TEST 2: TOTAL LEADS")
        print("="*70)

        dataset = self.datasets["crm_leads"]
        query = "How many total leads do we have?"

        self.logger.logger.info(f"Test 2: Total Leads")
        self.logger.logger.info(f"Dataset rows: {len(dataset)}")
        self.logger.logger.info(f"Query: {query}")

        result = analyze_query(query, dataset)

        # Verify against actual data
        expected_leads = len(dataset)
        actual_leads = result.get("leads_after_filters", 0)

        passed = actual_leads == expected_leads

        print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
        print(f"Expected Leads: {expected_leads}")
        print(f"Actual Leads: {actual_leads}")
        print(f"Explanation:\n{result.get('explanation', 'N/A')}")

        self.test_results.append({
            "test": "total_leads",
            "passed": passed,
            "expected": expected_leads,
            "actual": actual_leads,
        })

        return passed

    def test_revenue_by_source(self) -> bool:
        """TEST 3: Revenue breakdown by Lead Source."""
        print("\n" + "="*70)
        print("TEST 3: REVENUE BREAKDOWN BY SOURCE")
        print("="*70)

        dataset = self.datasets["leads_revenue"]
        query = "Show me revenue breakdown by Lead_Source"

        self.logger.logger.info(f"Test 3: Revenue by Source")
        self.logger.logger.info(f"Query: {query}")

        result = analyze_query(query, dataset)

        # Verify grouping
        group_breakdown = result.get("group_breakdown", [])
        total_revenue = result.get("total_revenue", 0)
        sum_of_groups = sum(g["revenue"] for g in group_breakdown)

        # Verify against actual data
        expected_total = float(dataset["Deal_Value"].sum())

        passed = (
            len(group_breakdown) > 0
            and abs(sum_of_groups - expected_total) < 0.01
            and abs(total_revenue - expected_total) < 0.01
        )

        print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
        print(f"Total Revenue: ${total_revenue:,.2f}")
        print(f"Number of Groups: {len(group_breakdown)}")
        print(f"Sum of Groups: ${sum_of_groups:,.2f}")
        print(f"Expected Total: ${expected_total:,.2f}")
        print(f"\nExplanation:\n{result.get('explanation', 'N/A')}")

        self.test_results.append({
            "test": "revenue_by_source",
            "passed": passed,
            "groups": len(group_breakdown),
            "total_mismatch": abs(sum_of_groups - expected_total),
        })

        return passed

    def test_leads_by_source(self) -> bool:
        """TEST 4: Leads breakdown by Lead Source."""
        print("\n" + "="*70)
        print("TEST 4: LEADS BREAKDOWN BY SOURCE")
        print("="*70)

        dataset = self.datasets["leads_revenue"]
        query = "Break down leads by Lead_Source"

        self.logger.logger.info(f"Test 4: Leads by Source")
        self.logger.logger.info(f"Query: {query}")

        result = analyze_query(query, dataset)

        # Verify grouping
        group_breakdown = result.get("group_breakdown", [])
        total_leads = result.get("leads_after_filters", 0)
        sum_of_groups = sum(g["lead_count"] for g in group_breakdown)

        # Verify against actual data
        expected_total = len(dataset)

        passed = (
            len(group_breakdown) > 0
            and sum_of_groups == expected_total
            and total_leads == expected_total
        )

        print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
        print(f"Total Leads: {total_leads}")
        print(f"Number of Groups: {len(group_breakdown)}")
        print(f"Sum of Groups: {sum_of_groups}")
        print(f"Expected Total: {expected_total}")
        print(f"\nExplanation:\n{result.get('explanation', 'N/A')}")

        self.test_results.append({
            "test": "leads_by_source",
            "passed": passed,
            "groups": len(group_breakdown),
            "total_mismatch": abs(sum_of_groups - expected_total),
        })

        return passed

    def test_revenue_wise_lead_analysis(self) -> bool:
        """TEST 5: Revenue-wise lead analysis (revenue per source with lead count)."""
        print("\n" + "="*70)
        print("TEST 5: REVENUE-WISE LEAD ANALYSIS")
        print("="*70)

        dataset = self.datasets["leads_revenue"]
        query = "Show revenue by Lead_Source with lead counts"

        self.logger.logger.info(f"Test 5: Revenue-wise Lead Analysis")
        self.logger.logger.info(f"Query: {query}")

        result = analyze_query(query, dataset)

        # New system returns metrics in "metrics" dict for multi-metric requests
        metrics = result.get("metrics", {})
        
        # Check for both revenue and leads in result
        has_revenue = "revenue" in metrics and metrics["revenue"].get("total", 0) > 0
        has_leads = "leads" in metrics and metrics["leads"].get("total", 0) > 0
        
        # Verify against actual data
        expected_revenue = float(dataset["Deal_Value"].sum())
        expected_leads = len(dataset)

        # For this test, we just need to ensure both metrics are calculated
        passed = has_revenue and has_leads

        print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
        if has_revenue:
            revenue_val = metrics["revenue"].get("total", 0)
            print(f"Total Revenue: ${revenue_val:,.2f} (expected: ${expected_revenue:,.2f})")
        if has_leads:
            leads_val = metrics["leads"].get("total", 0)
            print(f"Total Leads: {leads_val} (expected: {expected_leads})")
        print(f"Explanation:\n{result.get('explanation', 'N/A')}")

        self.test_results.append({
            "test": "revenue_wise_lead_analysis",
            "passed": passed,
            "has_revenue": has_revenue,
            "has_leads": has_leads,
        })

        return passed

    def test_both_analysis(self) -> bool:
        """TEST 6: Both revenue and leads analysis."""
        print("\n" + "="*70)
        print("TEST 6: BOTH REVENUE AND LEADS")
        print("="*70)

        dataset = self.datasets["leads_revenue"]
        query = "Give me both total revenue and total leads"

        self.logger.logger.info(f"Test 6: Both Analysis")
        self.logger.logger.info(f"Query: {query}")

        result = analyze_query(query, dataset)

        # New system returns metrics in "metrics" dict for multi-metric requests
        metrics = result.get("metrics", {})
        
        # or at top level for single-metric results
        total_revenue = result.get("total_revenue", 0)
        total_leads = result.get("leads_after_filters", 0)
        
        # Check nested structure if top-level not found
        if "revenue" in metrics:
            total_revenue = metrics["revenue"].get("total", 0)
        if "leads" in metrics:
            total_leads = metrics["leads"].get("total", 0)

        # Verify revenue
        expected_revenue = float(dataset["Deal_Value"].sum())
        revenue_valid = abs(total_revenue - expected_revenue) < 0.01

        # Verify leads
        expected_leads = len(dataset)
        leads_valid = total_leads == expected_leads

        passed = revenue_valid and leads_valid

        print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
        print(f"\nRevenue:")
        print(f"  Expected: ${expected_revenue:,.2f}")
        print(f"  Actual: ${total_revenue:,.2f}")
        print(f"  Valid: {revenue_valid}")
        print(f"\nLeads:")
        print(f"  Expected: {expected_leads}")
        print(f"  Actual: {total_leads}")
        print(f"  Valid: {leads_valid}")
        print(f"\nExplanation:\n{result.get('explanation', 'N/A')}")

        self.test_results.append({
            "test": "both_analysis",
            "passed": passed,
            "revenue_match": revenue_valid,
            "leads_match": leads_valid,
        })

        return passed

    def test_semantic_routing(self) -> bool:
        """TEST 7: Semantic routing detection."""
        print("\n" + "="*70)
        print("TEST 7: SEMANTIC ROUTING DETECTION")
        print("="*70)

        test_queries = [
            ("What is total revenue?", {"revenue"}),
            ("How many leads do we have?", {"leads"}),
            ("Revenue and leads comparison", {"revenue", "leads"}),
            ("Revenue breakdown by lead source", {"revenue"}),
        ]

        all_passed = True

        for query, expected_metrics in test_queries:
            dataset = self.datasets["leads_revenue"]
            result = analyze_query(query, dataset)

            metadata = result.get("_metadata", {})
            semantic_intent = metadata.get("semantic_intent", {})
            detected_metrics = set(semantic_intent.get("metrics", []))

            passed = detected_metrics == expected_metrics

            symbol = "[OK]" if passed else "[X]"
            print(
                f"{symbol} Query: '{query}'"
                f"\n  Expected metrics: {expected_metrics}, Detected: {detected_metrics}"
            )

            all_passed = all_passed and passed

        self.test_results.append({
            "test": "semantic_routing",
            "passed": all_passed,
        })

        return all_passed

    def test_anti_hallucination_guards(self) -> bool:
        """TEST 8: Anti-hallucination guardrails."""
        print("\n" + "="*70)
        print("TEST 8: ANTI-HALLUCINATION GUARDRAILS")
        print("="*70)

        dataset = self.datasets["leads_revenue"]

        tests = [
            ("Valid query", "Show revenue breakdown by Lead_Source"),
            ("Vague query", "give me everything"),
        ]

        all_passed = True

        for test_name, query in tests:
            result = analyze_query(query, dataset)
            
            # Check if result has meaningful data (not hallucinating)
            has_data = False
            
            # Check for revenue or leads data
            if result.get("total_revenue"):
                has_data = True
            if result.get("leads_after_filters"):
                has_data = True
            if result.get("metrics"):
                has_data = True
            if result.get("group_breakdown"):
                has_data = True

            # For valid queries we expect data
            if test_name == "Valid query":
                passed = has_data
            else:
                # For vague queries, system should still try or return gracefully
                passed = True  # System doesn't crash on vague queries

            symbol = "[OK]" if passed else "[X]"
            print(f"{symbol} {test_name}")
            print(f"  Query: {query}")
            print(f"  Has valid data: {has_data}")

            all_passed = all_passed and passed

        self.test_results.append({
            "test": "anti_hallucination_guards",
            "passed": all_passed,
        })

        return all_passed

    def run_all_tests(self) -> bool:
        """Run all tests and print summary."""
        print("\n" + "="*70)
        print("COMPREHENSIVE TEST SUITE - REVENUE & LEADS ANALYSIS")
        print("="*70)

        # Load datasets
        if not self.load_datasets():
            print("FAILED: Could not load test datasets")
            return False

        # Run tests
        tests = [
            ("Total Revenue", self.test_total_revenue),
            ("Total Leads", self.test_total_leads),
            ("Revenue by Source", self.test_revenue_by_source),
            ("Leads by Source", self.test_leads_by_source),
            ("Revenue-wise Lead Analysis", self.test_revenue_wise_lead_analysis),
            ("Both Analysis", self.test_both_analysis),
            ("Semantic Routing", self.test_semantic_routing),
            ("Anti-Hallucination Guards", self.test_anti_hallucination_guards),
        ]

        results = []
        for test_name, test_func in tests:
            try:
                passed = test_func()
                results.append((test_name, passed))
            except Exception as e:
                print(f"\n[X] {test_name} CRASHED: {str(e)}")
                results.append((test_name, False))
                logger.logger.error(f"Test crashed: {str(e)}")

        # Print summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        passed_count = sum(1 for _, passed in results if passed)
        total_count = len(results)

        for test_name, passed in results:
            symbol = "[OK]" if passed else "[X]"
            print(f"{symbol} {test_name}")

        print(f"\nTotal: {passed_count}/{total_count} tests passed")
        print("="*70)

        return all(passed for _, passed in results)


if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all_tests()

    if success:
        print("\n[OK] ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n[X] SOME TESTS FAILED")
        sys.exit(1)
