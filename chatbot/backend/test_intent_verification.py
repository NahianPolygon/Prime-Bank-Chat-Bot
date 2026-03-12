"""
Quick Intent Classification Verification Script
================================================
Tests the new semantic intent classifier with sample queries.

Usage:
    python test_intent_verification.py
"""

import sys
import os

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intent.classifier import IntentClassifier


# Test cases with expected results
TEST_CASES = [
    {
        "query": "Hello!",
        "expected_intent": "greeting",
        "expected_category": "greeting",
    },
    {
        "query": "Which cards have dining benefits?",
        "expected_intent": "feature_inquiry",
        "expected_features": ["dining"],
    },
    {
        "query": "Compare Visa Platinum vs JCB Platinum",
        "expected_intent": "comparison",
        "expected_products": 2,
    },
    {
        "query": "I earn 300k per month. What cards am I eligible for?",
        "expected_intent": "product_search_by_income",
        "expected_income": 3600000,  # 300k * 12
    },
    {
        "query": "Am I eligible for Visa Platinum Credit Card?",
        "expected_intent": "eligibility_check",
        "expected_product": "Visa Platinum Credit Card",
    },
    {
        "query": "My monthly income is 300k",
        "expected_income": 3600000,  # Should extract and convert
    },
    {
        "query": "I want conventional banking credit cards",
        "expected_banking_type": "conventional",
    },
    {
        "query": "Show me Islamic credit card options",
        "expected_banking_type": "islamic",
    },
    {
        "query": "I need a card with lounge access and dining benefits",
        "expected_features": ["lounge", "dining"],
    },
    {
        "query": "Show me only platinum cards",
        "expected_tier": "platinum",
    },
]


def test_intent_classifier():
    """Run all test cases and report results."""
    
    print("=" * 70)
    print("INTENT CLASSIFIER VERIFICATION TEST")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_CASES, 1):
        query = test["query"]
        print(f"\n[Test {i}] Query: \"{query}\"")
        
        # IMPORTANT: Use empty history for each test to prevent state bleeding
        # Each test should be independent with no conversation context
        result = IntentClassifier.classify(query, [], {})
        
        # Check expectations
        test_passed = True
        issues = []
        
        # Check intent type
        if "expected_intent" in test:
            if result["intent_type"] != test["expected_intent"]:
                issues.append(f"Intent: expected '{test['expected_intent']}', got '{result['intent_type']}'")
                test_passed = False
        
        # Check category
        if "expected_category" in test:
            if result["category"] != test["expected_category"]:
                issues.append(f"Category: expected '{test['expected_category']}', got '{result['category']}'")
                test_passed = False
        
        # Check features
        if "expected_features" in test:
            expected_features = test["expected_features"]
            actual_features = result.get("specific_features", [])
            if not all(f in actual_features for f in expected_features):
                issues.append(f"Features: expected {expected_features}, got {actual_features}")
                test_passed = False
        
        # Check income
        if "expected_income" in test:
            expected_income = test["expected_income"]
            actual_income = result.get("customer_income")
            if actual_income is None:
                issues.append(f"Income: expected {expected_income}, got None")
                test_passed = False
            elif abs(actual_income - expected_income) > expected_income * 0.1:  # 10% tolerance
                issues.append(f"Income: expected ~{expected_income}, got {actual_income}")
                test_passed = False
        
        # Check banking type
        if "expected_banking_type" in test:
            expected = test["expected_banking_type"]
            actual = result.get("banking_type")
            if actual != expected:
                issues.append(f"Banking type: expected '{expected}', got '{actual}'")
                test_passed = False
        
        # Check tier
        if "expected_tier" in test:
            expected = test["expected_tier"]
            actual = result.get("preferred_tier")
            if actual != expected:
                issues.append(f"Tier: expected '{expected}', got '{actual}'")
                test_passed = False
        
        # Check product
        if "expected_product" in test:
            expected = test["expected_product"]
            actual = result.get("specific_product")
            if actual != expected:
                issues.append(f"Product: expected '{expected}', got '{actual}'")
                test_passed = False
        
        # Check comparison products count
        if "expected_products" in test:
            expected_count = test["expected_products"]
            actual_count = len(result.get("comparison_products", []))
            if actual_count != expected_count:
                issues.append(f"Products: expected {expected_count}, got {actual_count}")
                test_passed = False
        
        # Print result
        if test_passed:
            print(f"  ✅ PASS")
            print(f"     Intent: {result['intent_type']}")
            if result.get("specific_features"):
                print(f"     Features: {result['specific_features']}")
            if result.get("customer_income"):
                print(f"     Income: {result['customer_income']:,} BDT")
            if result.get("banking_type") != "unknown":
                print(f"     Banking: {result['banking_type']}")
            passed += 1
        else:
            print(f"  ❌ FAIL")
            for issue in issues:
                print(f"     - {issue}")
            print(f"     Full result: {result}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total tests: {len(TEST_CASES)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Pass rate: {100 * passed // len(TEST_CASES)}%")
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 All tests passed! Intent classifier is working correctly.")
        return True
    else:
        print(f"\n⚠️  {failed} tests failed. Review the classifier prompts.")
        return False


if __name__ == "__main__":
    success = test_intent_classifier()
    sys.exit(0 if success else 1)