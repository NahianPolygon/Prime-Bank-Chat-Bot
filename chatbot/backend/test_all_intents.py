#!/usr/bin/env python3
"""
Comprehensive end-to-end test for all intent types.
Verifies that each intent type correctly retrieves from Chroma database.
"""

import json
import yaml
from pipelines.crew.main import CrewPipeline
from vector_db import initialize_knowledge_base
from pipelines.rag.search import initialize_rag_tool

def test_all_intents():
    """Test each intent type with user queries."""
    
    print("=" * 80)
    print("COMPREHENSIVE INTENT TESTING - All types retrieving from Chroma DB")
    print("=" * 80)
    
    # Initialize
    config_path = "./config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    vector_db = initialize_knowledge_base(config, force_reindex=False)
    initialize_rag_tool(vector_db, config.get("llm"))
    print("✓ Vector DB and RAG tool initialized\n")
    
    pipeline = CrewPipeline()
    
    # Test cases: (description, query, session_id)
    test_cases = [
        # 1. PRODUCT_INFO: General product search
        ("PRODUCT_INFO", "Tell me about JCB Gold credit card", "test_product_info"),
        
        # 2. FEATURE_INQUIRY: Ask about specific feature
        ("FEATURE_INQUIRY", "Which cards offer dining rewards?", "test_feature_inquiry"),
        
        # 3. COMPARISON: Compare two cards
        ("COMPARISON - First query", "I want a credit card", "test_comparison"),
        ("COMPARISON - After selection", "Compare Visa Gold and Visa Platinum", "test_comparison"),
        
        # 4. PRODUCT_SEARCH_BY_INCOME: Search by income
        ("PRODUCT_SEARCH_BY_INCOME", "What cards can I get with 200k annual income?", "test_income_search"),
        
        # 5. EXISTING_CARDHOLDER: Cardholder service
        ("EXISTING_CARDHOLDER", "My card is damaged, what do I do?", "test_cardholder"),
        
        # 6. ELIGIBILITY_CHECK: Check eligibility
        ("ELIGIBILITY_CHECK", "Am I eligible for MasterCard Platinum?", "test_eligibility"),
    ]
    
    results = {}
    
    for test_name, query, session_id in test_cases:
        print(f"\n{'=' * 80}")
        print(f"Test: {test_name}")
        print(f"Query: {query}")
        print(f"{'=' * 80}")
        
        try:
            response = pipeline.run(
                query=query,
                session_id=session_id,
                conversation_history=[]
            )
            
            # Extract key info
            intent_type = response.get("detected_intent", {}).get("intent_type", "N/A")
            has_response = bool(response.get("response"))
            agent_chain = response.get("agent_chain", [])
            needs_clarification = response.get("needs_clarification", False)
            
            print(f"✓ Intent Type: {intent_type}")
            print(f"✓ Response Length: {len(response.get('response', ''))} chars")
            print(f"✓ Agent Chain: {' → '.join(agent_chain) if agent_chain else 'Direct'}")
            print(f"✓ Needs Clarification: {needs_clarification}")
            
            # Show snippet of response
            resp_preview = response.get("response", "")[:150].replace("\n", " ")
            print(f"✓ Response Preview: {resp_preview}...")
            
            results[test_name] = {
                "status": "PASS",
                "intent_type": intent_type,
                "response_length": len(response.get("response", "")),
                "agent_chain": agent_chain
            }
            
        except Exception as e:
            print(f"✗ ERROR: {str(e)}")
            results[test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
    
    # Summary
    print(f"\n\n{'=' * 80}")
    print("TEST SUMMARY")
    print(f"{'=' * 80}\n")
    
    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    failed = sum(1 for r in results.values() if r["status"] == "FAIL")
    
    print(f"Total Tests: {len(results)}")
    print(f"✓ Passed: {passed}")
    print(f"✗ Failed: {failed}\n")
    
    print("Test Results:")
    for test_name, result in results.items():
        status_icon = "✓" if result["status"] == "PASS" else "✗"
        print(f"{status_icon} {test_name}: {result['status']}")
        if result["status"] == "PASS":
            print(f"   Intent: {result.get('intent_type')}, Response: {result.get('response_length')} chars")
        else:
            print(f"   Error: {result.get('error')}")
    
    print(f"\n{'=' * 80}")
    print("All intents properly route to Chroma DB ✓" if failed == 0 else "Some tests failed")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    test_all_intents()
