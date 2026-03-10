#!/usr/bin/env python3
"""Test vague queries vs feature queries classification."""

from intent.classifier import IntentClassifier

def test_queries():
    # Test 1: Vague query - should ask clarification
    query1 = "i want to know which credit card will be best for me"
    intent1 = IntentClassifier.classify(query1, [], None)
    
    print("\n===== TEST 1: VAGUE QUERY (should ask clarification) =====")
    print(f"Query: {query1}")
    print(f"Intent Type: {intent1['intent_type']}")
    print(f"Features Detected: {intent1['specific_features']}")
    print(f"Needs Clarification: {intent1['needs_clarification']}")
    print(f"Banking Type: {intent1['banking_type']}")
    assert intent1['intent_type'] == 'product_info', f"Expected product_info, got {intent1['intent_type']}"
    assert intent1['needs_clarification'] == True, f"Expected clarification needed"
    assert intent1['specific_features'] == [], f"Expected no features, got {intent1['specific_features']}"
    print("✅ PASS")
    
    # Test 2: Actual feature query - has product + feature
    query2 = "Tell me the reward points system of Visa Gold credit card"
    intent2 = IntentClassifier.classify(query2, [], None)
    
    print("\n===== TEST 2: ACTUAL FEATURE QUERY (Visa Gold + rewards) =====")
    print(f"Query: {query2}")
    print(f"Intent Type: {intent2['intent_type']}")
    print(f"Specific Product: {intent2['specific_product']}")
    print(f"Features Detected: {intent2['specific_features']}")
    print(f"Needs Clarification: {intent2['needs_clarification']}")
    assert intent2['intent_type'] == 'feature_inquiry', f"Expected feature_inquiry, got {intent2['intent_type']}"
    assert 'visa gold' in intent2['specific_product'].lower(), f"Expected Visa Gold in product, got {intent2['specific_product']}"
    assert 'rewards' in intent2['specific_features'], f"Expected rewards in features, got {intent2['specific_features']}"
    assert intent2['needs_clarification'] == False, f"Should not need clarification for feature query"
    print("✅ PASS")
    
    # Test 3: Generic feature mention without product
    query3 = "which cards have the best reward points?"
    intent3 = IntentClassifier.classify(query3, [], None)
    
    print("\n===== TEST 3: FEATURE WITHOUT SPECIFIC PRODUCT (vague) =====")
    print(f"Query: {query3}")
    print(f"Intent Type: {intent3['intent_type']}")
    print(f"Specific Product: {intent3['specific_product']}")
    print(f"Features Detected: {intent3['specific_features']}")
    # Could be feature_inquiry (search for rewards) or product_info (vague find)
    # Either way, should detect rewards feature
    assert 'rewards' in intent3['specific_features'], f"Expected rewards detected, got {intent3['specific_features']}"
    print("✅ PASS")
    
    # Test 4: Income-only query 
    query4 = "I earn 50,000 per month, what cards can I get?"
    intent4 = IntentClassifier.classify(query4, [], None)
    
    print("\n===== TEST 4: INCOME ONLY (product_search_by_income) =====")
    print(f"Query: {query4}")
    print(f"Intent Type: {intent4['intent_type']}")
    print(f"Features: {intent4['specific_features']}")
    print(f"Income: {intent4['customer_income']}")
    assert intent4['intent_type'] == 'product_search_by_income', f"Expected product_search_by_income, got {intent4['intent_type']}"
    assert intent4['customer_income'] == 600000, f"Expected income 600000, got {intent4['customer_income']}"
    print("✅ PASS")

if __name__ == "__main__":
    test_queries()
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
