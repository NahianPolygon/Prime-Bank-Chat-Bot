#!/usr/bin/env python3
"""
Comprehensive chatbot test suite with CSV output
Tests all intent types and outputs results to CSV for easy analysis
"""

import csv
import sys
from datetime import datetime
import yaml

sys.path.insert(0, '/app/backend')

from pipelines import CrewPipeline, initialize_rag_tool
from vector_db import initialize_knowledge_base

# Initialize
print("🔧 Initializing chatbot pipeline...")
config = yaml.safe_load(open("/app/backend/config.yaml"))
vector_db = initialize_knowledge_base(config, force_reindex=False)
initialize_rag_tool(vector_db, config["llm"])
pipeline = CrewPipeline()

# Test data organized by category
test_cases = [
    # Group 1: Income + Feature (should be eligibility_matching or product_search_by_income)
    ("G1-Q1", "Income+Feature", "0% EMI with 60k monthly", "Which cards offer 0% interest EMI with my 60,000 BDT monthly salary?", ["product_search_by_income", "eligibility_matching"]),
    ("G1-Q2", "Income+Feature", "Dining with 25k", "Dining benefits cards for 25,000 BDT/month income?", ["product_search_by_income", "eligibility_matching"]),
    ("G1-Q3", "Income+Feature", "Rewards with 80k", "Best rewards card I can get with 80,000 BDT monthly income?", ["product_search_by_income", "eligibility_matching"]),
    ("G1-Q4", "Income+Feature", "Airport with 120k", "Airport benefits with 120,000 BDT annual income?", ["product_search_by_income", "eligibility_matching"]),
    ("G1-Q5", "Income+Feature", "Credit limit with 45k", "Which card has highest credit limit at my 45,000 BDT monthly salary?", ["product_search_by_income", "eligibility_matching"]),
    
    # Group 2: Feature Only (should be feature_inquiry)
    ("G2-Q6", "Feature Inquiry", "EMI period", "What is the interest-free period for JCB Gold?", ["feature_inquiry"]),
    ("G2-Q7", "Feature Inquiry", "Reward points", "How many reward points can I earn with Visa Gold?", ["feature_inquiry"]),
    ("G2-Q8", "Feature Inquiry", "Insurance", "What insurance benefits are included?", ["feature_inquiry"]),
    
    # Group 3: Product Info (should be product_info)
    ("G3-Q9", "Product Info", "Annual fee", "What's the annual fee for Mastercard Platinum?", ["product_info"]),
    
    # Group 4: Eligibility (should be eligibility_check with routing)
    ("G4-Q10", "Eligibility Check", "Application", "How do I apply for a Prime Bank credit card?", ["eligibility_check", "product_info"]),
    
    # Group 5: Comparison  (should be comparison or feature_inquiry)
    ("G5-Q11", "Comparison", "Compare lounge", "Compare lounge access between different cards", ["comparison", "feature_inquiry"]),
    
    # Group 6: Superlatives (should be feature_inquiry)
    ("G6-Q12", "Superlative", "Best dining", "Which card has the best dining benefits?", ["feature_inquiry"]),
    ("G6-Q13", "Superlative", "Highest limit", "What's the highest credit limit available?", ["feature_inquiry"]),
    ("G6-Q14", "Superlative", "EMI duration", "Which card offers 0% EMI for longest duration?", ["feature_inquiry"]),
    
    # Group 7: Income Only (should be product_search_by_income)
    ("G7-Q15", "Income Only", "Cards for 40k", "What credit cards are available for 40,000 BDT/month income?", ["product_search_by_income"]),
    ("G7-Q16", "Income Only", "Premium with 100k", "Best premium card I can qualify for with 100,000 BDT monthly?", ["product_search_by_income"]),
    ("G7-Q17", "Income Only", "Cheapest for 20k", "Cheapest card to qualify for with 20,000 BDT/month?", ["product_search_by_income"]),
    
    # Group 8: Banking Type (should be feature_inquiry with banking_type)
    ("G8-Q18", "Banking Type", "Islamic with lounge", "Islamic banking credit cards with lounge access?", ["feature_inquiry"]),
    ("G8-Q19", "Banking Type", "Conventional dining", "Conventional bank cards with dining benefits?", ["feature_inquiry"]),
    
    # Group 9: Multiple Features (should detect all features)
    ("G9-Q20", "Multiple Features", "Dining+Rewards", "Cards with both dining and rewards benefits", ["feature_inquiry", "eligibility_matching", "product_search_by_income"]),
    ("G9-Q21", "Multiple Features", "EMI+Insurance", "0% EMI with insurance coverage", ["eligibility_matching", "feature_inquiry"]),
]

# Run tests
print(f"\n{'=' * 80}")
print(f"COMPREHENSIVE CHATBOT TEST SUITE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'=' * 80}\n")

results = []

for test_id, category, description, query, expected_intents in test_cases:
    print(f"Testing {test_id}: {description}...", end=" ")
    
    try:
        # CRITICAL: Use fresh session_id for EACH query to prevent state bleeding
        # (Otherwise eligibility_active flag stays True and blocks all routing)
        session_id = f"test_{test_id}_{datetime.now().strftime('%H%M%S%f')}"
        
        response = pipeline.run(
            query=query,
            conversation_history=[],
            session_id=session_id,
        )
        
        actual_intent = response['detected_intent']['intent_type']
        features = response['detected_intent'].get('specific_features', [])
        income = response['detected_intent'].get('customer_income')
        product = response['detected_intent'].get('specific_product', '')
        bot_response = response.get('response', '').strip()
        
        # Check if actual matches any expected
        intent_match = actual_intent in expected_intents
        status = "✅ PASS" if intent_match else "❌ FAIL"
        
        print(status)
        
        results.append({
            'Test ID': test_id,
            'Category': category,
            'Description': description,
            'Query': query,
            'Expected Intent': ', '.join(expected_intents),
            'Actual Intent': actual_intent,
            'Match': '✅' if intent_match else '❌',
            'Features Detected': ', '.join(features) if features else 'None',
            'Income': income if income else 'None',
            'Product': product if product else 'None',
            'Bot Response': bot_response if bot_response else '(empty)',
            'Response Length': len(bot_response)
        })
        
    except Exception as e:
        print(f"❌ ERROR")
        results.append({
            'Test ID': test_id,
            'Category': category,
            'Description': description,
            'Query': query,
            'Expected Intent': ', '.join(expected_intents),
            'Actual Intent': 'ERROR',
            'Match': '❌',
            'Features Detected': 'N/A',
            'Income': 'N/A',
            'Product': 'N/A',
            'Bot Response': f'ERROR: {str(e)[:100]}',
            'Response Length': 0
        })

# Save to CSV (always overwrites TEST_RESULTS.csv)
csv_filename = '/app/backend/TEST_RESULTS.csv'
print(f"\n{'=' * 80}")
print(f"Saving results to CSV: {csv_filename}")
print(f"Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'=' * 80}\n")

with open(csv_filename, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

# Print statistics
total = len(results)
passed = sum(1 for r in results if r['Match'] == '✅')
failed = total - passed

print(f"\n📊 TEST SUMMARY")
print(f"{'=' * 80}")
print(f"Total Tests:    {total}")
print(f"Passed:         {passed} ({passed*100//total}%)")
print(f"Failed:         {failed} ({failed*100//total}%)")
print(f"CSV Output:     {csv_filename}")
print(f"{'=' * 80}\n")

if failed > 0:
    print("❌ FAILED TESTS:")
    for r in results:
        if r['Match'] == '❌':
            print(f"  - {r['Test ID']}: Expected {r['Expected Intent']}, got {r['Actual Intent']}")
    sys.exit(1)
else:
    print("✅ ALL TESTS PASSED!")
    sys.exit(0)
