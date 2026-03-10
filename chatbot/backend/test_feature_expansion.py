#!/usr/bin/env python3
"""
Quick test of the feature query expansion fix.
"""

import sys
import yaml
sys.path.insert(0, '/app/backend')

from pipelines.rag.search import rag_search_impl, initialize_rag_tool
from pipelines.rag.feature_expansion import expand_feature_query
from vector_db import initialize_knowledge_base

# Initialize vector DB
print("Initializing Vector DB...")
with open('./config.yaml', 'r') as f:
    config = yaml.safe_load(f)

vector_db = initialize_knowledge_base(config, force_reindex=False)
initialize_rag_tool(vector_db, config["llm"])
print("✓ Vector DB initialized\n")

print("=" * 80)
print("Testing Feature Query Expansion Fix")
print("=" * 80)

# Test cases from failing queries
tests = [
    (["lounge_access"], "Compare lounge access between different cards"),
    (["emi"], "Which card offers 0% EMI for longest duration?"),
    (["dining", "rewards"], "Cards with both dining and rewards benefits"),
    (["emi", "insurance"], "0% EMI with insurance coverage"),
]

for features, original_query in tests:
    print(f"\n{'=' * 80}")
    print(f"Original Query: {original_query}")
    print(f"Features Detected: {features}")
    print("=" * 80)
    
    # Generate optimized query
    optimized_query = expand_feature_query(features)
    print(f"Optimized Query: {optimized_query}\n")
    
    # Test RAG search with optimized query
    print("Testing RAG search...")
    try:
        result = rag_search_impl(optimized_query, banking_type="", tier="", top_k=6)
        if result and result != "NO_PRODUCTS_FOUND":
            product_count = result.count("PRODUCT:")
            print(f"✅ SUCCESS: Found {product_count} products")
            print(f"   Response length: {len(result)} chars")
            # Show preview
            preview = result[:300]
            print(f"   Preview: {preview}...")
        else:
            print(f"❌ FAILED: No products found")
    except Exception as e:
        print(f"❌ ERROR: {e}")

print(f"\n{'=' * 80}")
print("✓ Feature expansion fix tested")
print("=" * 80)
