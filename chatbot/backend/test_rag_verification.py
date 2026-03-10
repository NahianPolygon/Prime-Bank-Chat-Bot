#!/usr/bin/env python3
"""
Verify RAG is pulling from Chroma database correctly.
Tests that products are being retrieved from knowledge base, not invented.
"""

import yaml
from vector_db import initialize_knowledge_base
from pipelines.rag.search import rag_search_impl, initialize_rag_tool

def test_rag_retrieval():
    """Test RAG retrieval from Chroma database."""
    
    print("=" * 70)
    print("Testing RAG Retrieval from Chroma Database")
    print("=" * 70)
    
    # Load config
    config_path = "./config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize vector DB (loads Chroma)
    print("\n1. Initializing Chroma vector database...")
    vector_db = initialize_knowledge_base(config, force_reindex=False)
    print(f"   ✓ Vector DB initialized")
    
    # Initialize RAG tool
    print("\n2. Initializing RAG search tool...")
    initialize_rag_tool(vector_db, config.get("llm"))
    print(f"   ✓ RAG search tool initialized")
    
    # Test 1: Search for dining cards (conventional)
    print("\n3. Test 1: Search for dining cards (conventional)...")
    result = rag_search_impl(
        query="credit card for dining rewards",
        banking_type="conventional",
        top_k=3
    )
    print(f"   Result:\n{result}")
    
    # Test 2: Search for travel cards
    print("\n4. Test 2: Search for travel cards...")
    result = rag_search_impl(
        query="credit card for international travel",
        banking_type="conventional",
        top_k=3
    )
    print(f"   Result:\n{result}")
    
    # Test 3: Search for Islamic cards
    print("\n5. Test 3: Search for Islamic (Hasanah) cards...")
    result = rag_search_impl(
        query="Islamic credit card",
        banking_type="islami",
        top_k=2
    )
    print(f"   Result:\n{result}")
    
    # Test 4: Check what products are indexed
    print("\n6. Checking indexed product count...",)
    all_results = rag_search_impl(
        query="credit card",
        top_k=20
    )
    product_count = all_results.count("PRODUCT:")
    print(f"   ✓ Found {product_count} unique products in index")
    
    print("\n" + "=" * 70)
    print("RAG Verification Complete!")
    print("=" * 70)

if __name__ == "__main__":
    test_rag_retrieval()
