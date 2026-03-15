"""
Feature Query Test - Real-time CSV output
4 columns: customer_query, intent_detected, full_bot_response, rag_chunks
"""

import csv
import time
import requests
import os
import sys
from datetime import datetime

# Inside Docker, use 127.0.0.1 because test script is running in the same container
BASE_URL = "http://127.0.0.1:8000"

FEATURE_QUERIES = [
    # Lounge Access
    "Which cards offer airport lounge access?",
    "Do you have any cards with VIP lounge benefits?",
    "What cards include Balaka lounge access?",
    "I need a card with priority lounge access",
    "LoungeKey feature - which cards have it?",
    
    # Dining
    "Cards with dining discounts?",
    "Which credit cards have buy one get one dining offer?",
    "I want a card with year-round dining benefits",
    "Do any cards offer restaurant cashback?",
    "Best card for restaurant BOGO offers?",
    
    # Rewards
    "What's the best rewards card?",
    "Cards with high reward points rate?",
    "Which card gives maximum cashback?",
    "I want rewards on every purchase",
    "2 points per BDT 50 spending - which cards?",
    
    # EMI/Installments
    "Cards with 0% EMI facility?",
    "Which cards offer interest-free installments?",
    "Do you have cards with easy EMI options?",
    "How long can I get 0% EMI for?",
    "36-month EMI options on cards?",
    
    # Insurance Coverage
    "Which cards have insurance coverage?",
    "Do any cards include travel insurance?",
    "Cards with accidental death benefit?",
    "I need a card with comprehensive insurance",
    "Takaful insurance on credit cards?",
    
    # Fee Waiver
    "Annual fee waiver condition?",
    "Which cards waive annual fees?",
    "Are there cards with no annual fee?",
    "What's the fee waiver requirement?",
    "How to get annual fee waived?",
    
    # Travel Benefits
    "Cards with travel benefits?",
    "Which cards offer flight discounts?",
    "Do any cards include hotel booking benefits?",
    "I want a travel-friendly credit card",
    "Airport welcome service on cards?",
    
    # Fuel Discount
    "Cards with fuel discount?",
    "Which cards give petrol cashback?",
    "Do you have cards for fuel purchase?",
    "Best card for fuel expenses?",
    "Fuel surcharge waiver cards?",
    
    # Supplementary Card
    "Can I get supplementary cards?",
    "Which cards allow multiple supplementary cards?",
    "Supplementary card fee?",
    "Do all cards have supplementary options?",
    "Free supplementary card?",
    
    # Contactless
    "Cards with contactless payment?",
    "Which cards support NFC payment?",
    "Do you have contactless credit cards?",
    "I need a card with tap-to-pay feature",
    "Mobile payment enabled cards?",
    
    # Interest-Free Period
    "Cards with 50-day interest-free period?",
    "Longest interest-free credit period?",
    "Interest-free purchase cards?",
    "Which card has maximum grace period?",
    "Interest-free EMI cards?",
    
    # Islamic/Shariah
    "Islamic credit cards?",
    "Do you have Shariah-compliant cards?",
    "Which cards are interest-free?",
    "I need a Takaful insurance card",
    "Hasanah credit card benefits?",
    
    # Minimum Payment
    "What is minimum payment on credit cards?",
    "Minimum payment percentage?",
    "How much minimum payment required?",
    "Which card has lowest minimum payment?",
    
    # Credit Limit
    "Unsecured credit limit on cards?",
    "Maximum credit limit available?",
    "Which card offers highest limit?",
    "BDT 700,000 credit limit cards?",
    "Can I increase credit limit?",
    
    # Combination Queries
    "Islamic card with lounge access?",
    "Rewards card with 0% EMI?",
    "Card with dining and travel benefits?",
    "Lounge access plus rewards card?",
    "Islamic BOGO dining card?",
]

def run_test(num_queries=None):
    """Run feature query tests and save to CSV"""
    
    queries_to_run = FEATURE_QUERIES[:num_queries] if num_queries else FEATURE_QUERIES
    
    csv_filename = f"feature_query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    print(f"\n📊 FEATURE QUERY TEST")
    print(f"{'='*80}")
    print(f"Running {len(queries_to_run)} feature queries")
    print(f"Saving to: {csv_filename}\n")
    
    passed = 0
    failed = 0
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['customer_query', 'intent_detected', 'full_bot_response', 'rag_chunks']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        
        with requests.Session() as session:
            for i, query in enumerate(queries_to_run, 1):
                try:
                    print(f"[{i:2d}/{len(queries_to_run)}] {query[:55]:55s} ", end="", flush=True)
                    
                    response = session.post(
                        f"{BASE_URL}/chat",
                        json={"query": query, "session_id": f"feat-{i}"},
                        timeout=30
                    )
                
                if response.status_code != 200:
                    print(f"❌ HTTP {response.status_code}")
                    failed += 1
                    writer.writerow({
                        'customer_query': query,
                        'intent_detected': f'ERROR_{response.status_code}',
                        'full_bot_response': f'HTTP Error {response.status_code}',
                        'rag_chunks': ''
                    })
                    csvfile.flush()
                    continue
                
                data = response.json()
                
                # Extract fields
                answer = data.get("answer", "")
                intent_dict = data.get("detected_intent", {})
                intent_type = intent_dict.get("intent_type", "unknown") if intent_dict else "unknown"
                
                # Extract RAG products found
                rag_chunks = ""
                if data.get("products_found"):
                    rag_chunks = " | ".join(data.get("products_found", []))
                
                # Write row
                writer.writerow({
                    'customer_query': query,
                    'intent_detected': intent_type,
                    'full_bot_response': answer,
                    'rag_chunks': rag_chunks
                })
                csvfile.flush()
                
                passed += 1
                print(f"✅ {intent_type:20s}")
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ {str(e)[:40]}")
                failed += 1
                writer.writerow({
                    'customer_query': query,
                    'intent_detected': 'ERROR',
                    'full_bot_response': str(e),
                    'rag_chunks': ''
                })
                csvfile.flush()
    
    total = passed + failed
    pct = 100 * passed // total if total else 0
    
    print(f"\n{'='*80}")
    print(f"✅ PASSED: {passed}/{total}")
    print(f"❌ FAILED: {failed}/{total}")
    print(f"📊 Success Rate: {pct}%")
    print(f"📄 Results saved: {csv_filename}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    import sys
    num_queries = None
    if len(sys.argv) > 1:
        try:
            num_queries = int(sys.argv[1])
        except ValueError:
            print("Please provide a valid number of queries to run.")
            sys.exit(1)
            
    run_test(num_queries)

