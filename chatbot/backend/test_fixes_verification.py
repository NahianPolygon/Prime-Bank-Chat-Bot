#!/usr/bin/env python3
"""Test to verify the fixes for vague vs feature queries."""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_query(session_id, query, test_name):
    """Test a single query and return the response."""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"{'='*70}")
    print(f"Query: {query}")
    
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"session_id": session_id, "query": query}
    )
    
    data = response.json()
    answer = data.get("answer", "")
    agents = data.get("agent_chain", [])
    
    print(f"Agents: {agents}")
    print(f"Response: {answer[:250]}...")
    
    return data

# Test 1: Vague query - should ask clarification with smart profiler
test_query(
    "test_vague_" + str(__import__('time').time()),
    "i want to know which credit card will be best for me",
    "VAGUE QUERY - Should ask clarification questions"
)

# Test 2: Feature query with specific product - should answer directly
test_query(
    "test_feature_" + str(__import__('time').time()),
    "Tell me the reward points system of Visa Gold credit card",
    "FEATURE QUERY - Should answer about specific feature"
)

# Test 3: Income+ question - no feature - might ask clarification or show results
test_query(
    "test_income_" + str(__import__('time').time()),
    "I earn 100,000 per month, what cards can I qualify for?",
    "INCOME QUERY - Should show matching cards or ask for banking type"
)

print(f"\n{'='*70}")
print("✅ All tests completed!")
print(f"{'='*70}\n")
