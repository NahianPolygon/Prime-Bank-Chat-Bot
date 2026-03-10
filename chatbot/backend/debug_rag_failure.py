#!/usr/bin/env python3
"""
Comprehensive diagnostic script to identify RAG retrieval failures.
Tests: classifier → orchestrator → RAG search → crew response
"""

import sys
import json
from datetime import datetime

# Add paths
sys.path.insert(0, '/app/backend')

from intent.classifier import IntentClassifier
from pipelines.rag.search import rag_search_impl, initialize_rag_tool
from vector_db import initialize_knowledge_base
import yaml

# Failing test queries
FAILING_QUERIES = [
    ("Q8", "What insurance benefits are included?", "insurance"),
    ("Q11", "Compare lounge access between different cards", "lounge_access"),
    ("Q12", "Which card has the best dining benefits?", "dining"),
    ("Q13", "What's the highest credit limit available?", "credit_limit"),
    ("Q14", "Which card offers 0% EMI for longest duration?", "emi"),
    ("Q20", "Cards with both dining and rewards benefits", "dining, rewards"),
    ("Q21", "0% EMI with insurance coverage", "emi, insurance"),
]

print("\n" + "=" * 80)
print("🔍 COMPREHENSIVE RAG FAILURE DIAGNOSTIC")
print("=" * 80)

print("\n📦 Initializing Vector DB...")
try:
    # Load config
    with open('./config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    vector_db = initialize_knowledge_base(config, force_reindex=False)
    initialize_rag_tool(vector_db, config["llm"])
    print("✓ Vector DB initialized")
except Exception as e:
    print(f"❌ Failed to initialize Vector DB: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

results = []

for test_id, query, expected_features in FAILING_QUERIES:
    print(f"\n{'=' * 80}")
    print(f"TEST: {test_id} - {query}")
    print(f"Expected Features: {expected_features}")
    print("=" * 80)

    # STEP 1: Test Classifier
    print(f"\n1️⃣ TESTING CLASSIFIER FEATURE EXTRACTION")
    print("-" * 80)
    try:
        intent = IntentClassifier.classify(query, [], {})
        print(f"✓ Classifier output:")
        print(f"  Intent Type: {intent.get('intent_type')}")
        print(f"  Features Detected: {intent.get('specific_features', [])}")
        print(f"  Banking Type: {intent.get('banking_type')}")
        print(f"  Income: {intent.get('income')}")
        
        classifier_features = intent.get('specific_features', [])
        classifier_intent = intent.get('intent_type', 'unknown')
    except Exception as e:
        print(f"❌ Classifier failed: {e}")
        classifier_features = []
        classifier_intent = "ERROR"

    # STEP 2: Test RAG Search - No Filters
    print(f"\n2️⃣ TESTING RAG SEARCH - No Filters (search all products)")
    print("-" * 80)
    try:
        rag_result_all = rag_search_impl(query, banking_type="", tier="", top_k=10)
        if rag_result_all and rag_result_all != "NO_PRODUCTS_FOUND":
            print(f"✓ RAG found {len(rag_result_all)} chars of product data")
            # Show first 500 chars
            preview = rag_result_all[:500]
            print(f"  Preview:\n{preview}...\n")
            rag_all_success = True
        else:
            print(f"❌ RAG returned NO products for this query")
            rag_all_success = False
    except Exception as e:
        print(f"❌ RAG search failed: {e}")
        rag_all_success = False

    # STEP 3: Test RAG Search - With Feature Keywords
    print(f"\n3️⃣ TESTING RAG SEARCH - Direct Feature Keywords")
    print("-" * 80)
    feature_queries = {
        "insurance": "triple benefit insurance takaful",
        "lounge_access": "balaka vip lounge access loungekey",
        "dining": "dining bogo restaurants year-round",
        "credit_limit": "credit limit unsecured collateralized",
        "emi": "0% emi installment 36 months",
        "rewards": "reward points 50 taka",
    }
    
    for feature in [expected_features.split(", ")[0]]:  # Test first feature
        if feature in feature_queries:
            feature_query = feature_queries[feature]
            print(f"  Feature: {feature}")
            print(f"  Search query: {feature_query}")
            try:
                rag_feature = rag_search_impl(feature_query, banking_type="", tier="", top_k=10)
                if rag_feature and rag_feature != "NO_PRODUCTS_FOUND":
                    print(f"  ✓ Found {len(rag_feature)} chars with feature keywords")
                    rag_feature_success = True
                else:
                    print(f"  ❌ NO products found with feature keywords")
                    rag_feature_success = False
            except Exception as e:
                print(f"  ❌ Feature search failed: {e}")
                rag_feature_success = False

    # STEP 4: Search KB directly - Check what's indexed
    print(f"\n4️⃣ TESTING KB INDEX - Direct product lookup")
    print("-" * 80)
    try:
        kb_search = rag_search_impl("visa gold jcb mastercard platinum", banking_type="", tier="", top_k=10)
        if kb_search and kb_search != "NO_PRODUCTS_FOUND":
            print(f"✓ Found product data for direct product names")
            # Count products in response
            product_count = kb_search.count("PRODUCT:")
            print(f"  Products found: {product_count}")
        else:
            print(f"❌ Could not find products even with direct names")
    except Exception as e:
        print(f"❌ KB direct lookup failed: {e}")

    # STEP 5: Vector DB Stats
    print(f"\n5️⃣ VECTOR DB STATS")
    print("-" * 80)
    try:
        # Get collection count
        collection_count = vector_db.collection.count()
        print(f"✓ Total chunks in KB: {collection_count}")
    except Exception as e:
        print(f"⚠️ Could not get DB stats: {e}")

    # Store result
    results.append({
        "test_id": test_id,
        "query": query,
        "expected_features": expected_features,
        "classifier_features": classifier_features,
        "classifier_intent": classifier_intent,
        "rag_all_success": rag_all_success,
        "rag_feature_success": rag_feature_success if 'rag_feature_success' in locals() else False,
    })

# SUMMARY
print(f"\n\n{'=' * 80}")
print("📊 DIAGNOSTIC SUMMARY")
print("=" * 80)

print("\n✓ Test Results:")
for r in results:
    print(f"\n{r['test_id']}: {r['query']}")
    print(f"  Classifier found: {r['classifier_features'] if r['classifier_features'] else '(none)'}")
    print(f"  RAG (general): {'✓' if r['rag_all_success'] else '❌'}")
    print(f"  RAG (feature keywords): {'✓' if r['rag_feature_success'] else '❌'}")

# Analysis
print("\n\n🔬 FAILURE ANALYSIS:")
print("-" * 80)

classifier_failures = [r for r in results if not r['classifier_features']]
if classifier_failures:
    print(f"\n❌ {len(classifier_failures)} queries: Classifier NOT detecting features:")
    for r in classifier_failures:
        print(f"   {r['test_id']}: {r['query']}")

rag_failures = [r for r in results if r['rag_all_success'] == False]
if rag_failures:
    print(f"\n❌ {len(rag_failures)} queries: RAG NOT retrieving products:")
    for r in rag_failures:
        print(f"   {r['test_id']}: {r['query']}")

success_count = sum(1 for r in results if r['rag_all_success'])
print(f"\n✓ {success_count}/{len(results)} queries can retrieve RAG data")

print("\n\n💡 LIKELY ROOT CAUSES:")
print("-" * 80)
if any(not r['classifier_features'] for r in results):
    print("1. CLASSIFIER: Not detecting features (empty array)")
    print("   → Prompts may need adjustment to extract features for feature-inquiry")
    
if any(not r['rag_all_success'] for r in results):
    print("2. RAG SEARCH: Not finding matching products")
    print("   → Query may not match KB content, or embeddings not optimized")
    print("   → Vector DB may have few chunks for feature-based searches")
    
print("3. ORCHESTRATOR: May not be calling RAG for feature_inquiry intents")
print("   → Check if feature_inquiry is in RAG trigger conditions (line 63)")

print(f"\n✓ Diagnostic complete: {datetime.now()}")
print("=" * 80)
