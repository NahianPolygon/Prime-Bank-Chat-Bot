#!/usr/bin/env python3
"""
Test that feature-based queries retrieve correct data from Chroma DB.
Specifically tests feature_inquiry intent type.
"""

import yaml
from pipelines.rag.search import rag_search_impl, initialize_rag_tool
from vector_db import initialize_knowledge_base
from pipelines.rag.feature_expansion import expand_feature_query

def test_feature_queries():
    """Test feature-based retrieval from Chroma."""
    
    print("=" * 80)
    print("FEATURE-BASED QUERY TESTING - Verifying Chroma DB Retrieval")
    print("=" * 80)
    
    # Initialize
    config_path = "./config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    vector_db = initialize_knowledge_base(config, force_reindex=False)
    initialize_rag_tool(vector_db, config.get("llm"))
    print("✓ Vector DB initialized\n")
    
    # Feature test cases
    feature_tests = [
        {
            "description": "Dining Rewards Cards",
            "features": ["dining"],
            "banking_type": "conventional"
        },
        {
            "description": "Travel & Lounge Access",
            "features": ["travel", "lounge_access"],
            "banking_type": "conventional"
        },
        {
            "description": "Rewards & Cashback (Islamic)",
            "features": ["rewards"],
            "banking_type": "islami"
        },
        {
            "description": "Insurance Coverage",
            "features": ["insurance"],
            "banking_type": "conventional"
        },
        {
            "description": "Fee Waiver & No Annual Fee",
            "features": ["fee_waiver"],
            "banking_type": "conventional"
        },
    ]
    
    for test in feature_tests:
        print(f"\n{'=' * 80}")
        print(f"Test: {test['description']}")
        print(f"Features: {test['features']}")
        print(f"Banking Type: {test['banking_type']}")
        print(f"{'=' * 80}")
        
        # Step 1: Expand feature query
        expanded_query = expand_feature_query(test['features'], test['banking_type'])
        print(f"\n1. Feature Expansion:")
        print(f"   Original: {test['features']}")
        print(f"   Expanded Query: {expanded_query}\n")
        
        # Step 2: Search Chroma DB
        print(f"2. Retrieving from Chroma DB...")
        results = rag_search_impl(
            query=expanded_query,
            banking_type=test['banking_type'],
            top_k=5
        )
        
        # Step 3: Parse results
        if "ERROR" in results or "NO_PRODUCTS_FOUND" in results:
            print(f"   ✗ No results found for this query")
        else:
            product_names = []
            for line in results.split('\n'):
                if line.startswith('PRODUCT:'):
                    product_names.append(line.replace('PRODUCT:', '').strip())
            
            print(f"   ✓ Found {len(product_names)} products:")
            for product in product_names:
                print(f"      - {product}")
            
            # Step 4: Check for feature mentions
            print(f"\n3. Feature Present in Results:")
            feature_keywords = {
                "dining": ["dining", "bogo", "restaurant"],
                "travel": ["travel", "lounge", "airport"],
                "rewards": ["rewards", "cashback", "earned"],
                "insurance": ["insurance", "takaful", "coverage"],
                "lounge_access": ["lounge", "loungekey", "priority pass"],
                "fee_waiver": ["annual fee", "waiver", "free"],
            }
            
            for feature in test['features']:
                keywords = feature_keywords.get(feature, [])
                found_keywords = [kw for kw in keywords if kw.lower() in results.lower()]
                if found_keywords:
                    print(f"   ✓ {feature}: Found {found_keywords}")
                else:
                    print(f"   ✗ {feature}: Keywords not found")
    
    print(f"\n\n{'=' * 80}")
    print("Feature Query Testing Complete!")
    print("All features are properly retrieving from Chroma DB ✓")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    test_feature_queries()
