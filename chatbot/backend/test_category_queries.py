import csv
import time
import requests
import os
import sys
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

CATEGORY_QUERIES = [
    # Card Networks (Brands)
    "Show me all the Mastercards you have",
    "What Visa cards do you offer?",
    "Tell me about your JCB credit cards",
    "List all your Mastercards",
    "I want to see all your Visa credit cards",
    
    # Card Tiers
    "Show me all the gold cards",
    "What platinum cards are available?",
    "Show me your World credit cards",
    "List all gold tier cards",
    "Do you have any premium platinum cards?",
    
    # Banking Type
    "Show me all the Islamic cards",
    "What Shariah compliant cards do you offer?",
    "Show me all conventional credit cards",
    "I want to see all Islamic Hasanah cards",
    
    # Combinations (Tier + Network + Type)
    "Show me all Visa Platinum cards",
    "Do you have any Mastercard Gold cards?",
    "Show me Islamic Platinum cards",
    "Conventional gold credit cards",
    "Islamic Mastercard options",
    "JCB Platinum cards list",
    "Visa Gold credit cards",
    "Mastercard World cards"
]

def run_test(num_queries=None):
    """Run category query tests and save to CSV"""
    
    queries = CATEGORY_QUERIES[:num_queries] if num_queries else CATEGORY_QUERIES
    
    csv_filename = f"category_query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    print(f"\n📊 CATEGORY QUERY TEST")
    print(f"{'='*80}")
    print(f"Running {len(queries)} category queries")
    print(f"Saving to: {csv_filename}\n")
    
    passed = 0
    failed = 0
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['customer_query', 'intent_detected', 'full_bot_response', 'rag_chunks']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        
        with requests.Session() as session:
            for i, query in enumerate(queries, 1):
                try:
                    print(f"[{i:2d}/{len(queries)}] {query[:55]:55s} ", end="", flush=True)
                    
                    response = session.post(
                        f"{BASE_URL}/chat",
                        json={"query": query, "session_id": f"cat-{i}"},
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
                    
                    answer = data.get("answer", "")
                    intent_dict = data.get("detected_intent", {})
                    intent_type = intent_dict.get("intent_type", "unknown") if intent_dict else "unknown"
                    
                    rag_chunks = ""
                    if data.get("products_found"):
                        rag_chunks = " | ".join(data.get("products_found", []))
                    
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
    
    print(f"\n{'='*80}")
    print(f"✅ PASSED: {passed}/{len(queries)}")
    print(f"❌ FAILED: {failed}/{len(queries)}")
    print(f"📊 Success Rate: {100 * passed // len(queries) if len(queries) else 0}%")
    print(f"📄 Results saved: {csv_filename}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    num_queries = None
    if len(sys.argv) > 1:
        try:
            num_queries = int(sys.argv[1])
        except ValueError:
            print("Please provide a valid number of queries to run.")
            sys.exit(1)
            
    run_test(num_queries)
