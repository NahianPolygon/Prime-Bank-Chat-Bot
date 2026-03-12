"""
Prime Bank Chatbot - Comprehensive Resilient Test Suite
========================================================

Covers ALL query types found in knowledge_base:
- 8 products (Conventional + Islamic)
- Feature queries (lounge, dining, rewards, insurance, travel)
- Income-based queries (different formats, tiers)
- Banking type queries (conventional vs Islamic)
- Comparison queries
- Eligibility queries
- Application & process queries
- Edge cases (typos, partial names, vague queries)

Evaluation:
1. Intent classification accuracy
2. Entity extraction accuracy  
3. Response appropriateness
4. No data leakage
5. Conversation flow
"""

import json
import csv
import uuid
import time
import sys
import os

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests --break-system-packages -q")
    import requests

BASE_URL = "http://localhost:8000"
RESULTS_DIR = "test_results"
DELAY_BETWEEN_TESTS = 1.5

PASS = "✅"
FAIL = "❌"
INFO = "ℹ️"


# ═══════════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE TEST SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

COMPREHENSIVE_TESTS = [
    # ─────────────────────────────────────────────────────────────────────────
    # PART 1: FEATURE-BASED QUERIES (All product features)
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "FEAT_001",
        "query": "Which cards have lounge access?",
        "expected_intent": "feature_inquiry",
        "expected_features": ["lounge", "access"],
        "expected_products_min": 4,
        "test_type": "feature",
        "severity": "high"
    },
    {
        "id": "FEAT_002",
        "query": "Show me cards with dining benefits",
        "expected_intent": "feature_inquiry",
        "expected_features": ["dining"],
        "expected_products_min": 6,
        "test_type": "feature",
        "severity": "high"
    },
    {
        "id": "FEAT_003",
        "query": "Which card offers the best rewards points?",
        "expected_intent": "feature_inquiry",
        "expected_features": ["rewards"],
        "should_contain": ["Mastercard World", "2 points"],
        "test_type": "feature",
        "severity": "high"
    },
    {
        "id": "FEAT_004",
        "query": "What cards have insurance coverage?",
        "expected_intent": "feature_inquiry",
        "expected_features": ["insurance"],
        "expected_products_min": 8,
        "test_type": "feature",
        "severity": "medium"
    },
    {
        "id": "FEAT_005",
        "query": "Tell me about 0% installment options",
        "expected_intent": "feature_inquiry",
        "expected_features": ["installment"],
        "test_type": "feature",
        "severity": "medium"
    },
    {
        "id": "FEAT_006",
        "query": "Which cards offer BOGO dining?",
        "expected_intent": "feature_inquiry",
        "expected_features": ["dining", "bogo"],
        "expected_products_min": 6,
        "test_type": "feature",
        "severity": "high"
    },
    {
        "id": "FEAT_007",
        "query": "What are cashback benefits?",
        "expected_intent": "feature_inquiry",
        "should_contain": ["reward", "points"],
        "test_type": "feature",
        "severity": "medium"
    },
    {
        "id": "FEAT_008",
        "query": "I need travel benefits - which card?",
        "expected_intent": "feature_inquiry",
        "expected_features": ["travel"],
        "should_contain": ["lounge", "airport"],
        "test_type": "feature",
        "severity": "high"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 2: INCOME-BASED QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "INC_001",
        "query": "I earn 300,000 BDT monthly. What cards can I get?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 3600000},
        "expected_products_min": 2,
        "test_type": "income",
        "severity": "high"
    },
    {
        "id": "INC_002",
        "query": "My annual income is 50 lakh. Suggest a card.",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 5000000},
        "expected_products_min": 4,
        "test_type": "income",
        "severity": "high"
    },
    {
        "id": "INC_003",
        "query": "I have 300k monthly income. What card suits me?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 3600000},
        "test_type": "income",
        "severity": "high"
    },
    {
        "id": "INC_004",
        "query": "My salary is 2 lakh per month. Best card?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 2400000},
        "test_type": "income",
        "severity": "high"
    },
    {
        "id": "INC_005",
        "query": "I earn 500000 annually. Can I get a premium card?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 500000},
        "test_type": "income",
        "severity": "medium"
    },
    {
        "id": "INC_006",
        "query": "Monthly income 100k. Which card?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 1200000},
        "test_type": "income",
        "severity": "medium"
    },
    {
        "id": "INC_007",
        "query": "My income is 50,000 BDT/month and I prefer dining benefits. Recommend?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 600000, "primary_use_case": "dining"},
        "test_type": "income",
        "severity": "high"
    },
    {
        "id": "INC_008",
        "query": "I'm a business owner with annual turnover of 30 lakh. What credit card?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 3000000, "employment_type": "business_owner"},
        "test_type": "income",
        "severity": "high"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 3: BANKING TYPE QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "BANK_001",
        "query": "I want an Islamic credit card",
        "expected_intent": "product_info",
        "should_extract": {"banking_type": "islamic"},
        "should_not_contain": ["conventional"],
        "expected_products_min": 2,
        "test_type": "banking_type",
        "severity": "high"
    },
    {
        "id": "BANK_002",
        "query": "Show me Shariah-compliant cards",
        "expected_intent": "product_info",
        "should_extract": {"banking_type": "islamic"},
        "should_contain": ["Hasanah", "Islamic", "Shariah"],
        "test_type": "banking_type",
        "severity": "high"
    },
    {
        "id": "BANK_003",
        "query": "I need a conventional credit card. What's available?",
        "expected_intent": "product_info",
        "should_extract": {"banking_type": "conventional"},
        "test_type": "banking_type",
        "severity": "high"
    },
    {
        "id": "BANK_004",
        "query": "Compare Islamic vs conventional - which is better?",
        "expected_intent": "comparison",
        "should_contain": ["Islamic", "conventional"],
        "test_type": "banking_type",
        "severity": "medium"
    },
    {
        "id": "BANK_005",
        "query": "Visa Hasanah - is it Riba-free?",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "Visa Hasanah Platinum Credit Card"},
        "should_contain": ["Ujrah", "Islamic", "Shariah"],
        "test_type": "banking_type",
        "severity": "high"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 4: CARD NETWORK QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "NET_001",
        "query": "Which Visa cards do you offer?",
        "expected_intent": "product_info",
        "should_contain": ["Visa"],
        "expected_products_min": 3,
        "test_type": "network",
        "severity": "high"
    },
    {
        "id": "NET_002",
        "query": "Tell me about JCB credit cards",
        "expected_intent": "product_info",
        "should_contain": ["JCB"],
        "expected_products_min": 2,
        "test_type": "network",
        "severity": "high"
    },
    {
        "id": "NET_003",
        "query": "Mastercard options available?",
        "expected_intent": "product_info",
        "should_contain": ["Mastercard"],
        "expected_products_min": 2,
        "test_type": "network",
        "severity": "high"
    },
    {
        "id": "NET_004",
        "query": "Compare Visa vs Mastercard vs JCB",
        "expected_intent": "comparison",
        "should_contain": ["Visa", "Mastercard", "JCB"],
        "test_type": "network",
        "severity": "medium"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 5: TIER-BASED QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "TIER_001",
        "query": "Show me platinum credit cards",
        "expected_intent": "product_info",
        "should_extract": {"preferred_tier": "platinum"},
        "expected_products_min": 4,
        "test_type": "tier",
        "severity": "high"
    },
    {
        "id": "TIER_002",
        "query": "What gold tier cards do you have?",
        "expected_intent": "product_info",
        "should_extract": {"preferred_tier": "gold"},
        "expected_products_min": 3,
        "test_type": "tier",
        "severity": "high"
    },
    {
        "id": "TIER_003",
        "query": "Mastercard World - what tier is it?",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "Mastercard World Credit Card"},
        "should_contain": ["World"],
        "test_type": "tier",
        "severity": "medium"
    },
    {
        "id": "TIER_004",
        "query": "Best card in gold tier with dining?",
        "expected_intent": "product_info",
        "should_extract": {"preferred_tier": "gold"},
        "should_contain": ["dining", "JCB Gold"],
        "test_type": "tier",
        "severity": "high"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 6: COMPARISON QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "CMP_001",
        "query": "Compare Visa Platinum and JCB Platinum",
        "expected_intent": "comparison",
        "should_contain": ["Visa Platinum", "JCB Platinum"],
        "test_type": "comparison",
        "severity": "high"
    },
    {
        "id": "CMP_002",
        "query": "Which is better - JCB Gold or Visa Gold?",
        "expected_intent": "comparison",
        "should_contain": ["JCB Gold", "Visa Gold"],
        "test_type": "comparison",
        "severity": "high"
    },
    {
        "id": "CMP_003",
        "query": "Mastercard World vs Mastercard Platinum - differences?",
        "expected_intent": "comparison",
        "should_contain": ["Mastercard"],
        "test_type": "comparison",
        "severity": "high"
    },
    {
        "id": "CMP_004",
        "query": "Show me a table comparing all platinum cards",
        "expected_intent": "comparison",
        "should_contain": ["platinum"],
        "expected_products_min": 4,
        "test_type": "comparison",
        "severity": "medium"
    },
    {
        "id": "CMP_005",
        "query": "Visa Hasanah Platinum vs Visa Platinum - differences?",
        "expected_intent": "comparison",
        "should_contain": ["Hasanah", "Shariah", "Islamic"],
        "test_type": "comparison",
        "severity": "high"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 7: SPECIFIC PRODUCT QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "PROD_001",
        "query": "Tell me about Visa Platinum Credit Card",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "Visa Platinum Credit Card"},
        "should_contain": ["1,000,000", "50-day", "lounge", "BOGO"],
        "test_type": "product",
        "severity": "high"
    },
    {
        "id": "PROD_002",
        "query": "What are the features of JCB Gold?",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "JCB Gold Credit Card"},
        "should_contain": ["700,000", "50-day", "Balaka"],
        "test_type": "product",
        "severity": "high"
    },
    {
        "id": "PROD_003",
        "query": "Mastercard World credit card - tell me more",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "Mastercard World Credit Card"},
        "should_contain": ["2 points", "reward"],
        "test_type": "product",
        "severity": "high"
    },
    {
        "id": "PROD_004",
        "query": "What's the credit limit on JCB Platinum?",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "JCB Platinum Credit Card"},
        "should_contain": ["1,000,000", "2,500,000"],
        "test_type": "product",
        "severity": "high"
    },
    {
        "id": "PROD_005",
        "query": "How does the Visa Hasanah differ from regular Visa?",
        "expected_intent": "product_info",
        "should_contain": ["Islamic", "Shariah", "Ujrah"],
        "test_type": "product",
        "severity": "high"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 8: ELIGIBILITY QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "ELIG_001",
        "query": "Can I get a platinum card? I earn 3 lakh monthly",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 3600000},
        "should_contain": ["eligible", "platinum"],
        "test_type": "eligibility",
        "severity": "high"
    },
    {
        "id": "ELIG_002",
        "query": "What are the eligibility requirements for Visa Platinum?",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "Visa Platinum Credit Card"},
        "should_contain": ["age", "income", "tenure", "E-TIN"],
        "test_type": "eligibility",
        "severity": "high"
    },
    {
        "id": "ELIG_003",
        "query": "I'm 25 years old, salaried. What card can I apply for?",
        "expected_intent": "product_info",
        "should_extract": {"employment_type": "salaried"},
        "should_contain": ["all cards", "eligible"],
        "test_type": "eligibility",
        "severity": "high"
    },
    {
        "id": "ELIG_004",
        "query": "Am I eligible for Mastercard World? I've been in my job for 4 months",
        "expected_intent": "product_info",
        "should_contain": ["6 months", "tenure"],
        "test_type": "eligibility",
        "severity": "high"
    },
    {
        "id": "ELIG_005",
        "query": "I'm self-employed for 2 years. Can I get Islamic card?",
        "expected_intent": "product_search_by_income",
        "should_extract": {"employment_type": "self_employed", "banking_type": "islamic"},
        "should_contain": ["Hasanah", "3 years"],
        "test_type": "eligibility",
        "severity": "high"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 9: PROCESS QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "PROC_001",
        "query": "How do I apply for a credit card?",
        "expected_intent": "product_info",
        "should_contain": ["application", "apply", "online"],
        "test_type": "process",
        "severity": "medium"
    },
    {
        "id": "PROC_002",
        "query": "What documents do I need for card approval?",
        "expected_intent": "product_info",
        "should_contain": ["E-TIN", "documents", "requirements"],
        "test_type": "process",
        "severity": "medium"
    },
    {
        "id": "PROC_003",
        "query": "How long does approval typically take?",
        "expected_intent": "product_info",
        "should_contain": ["days", "business", "approval", "time"],
        "test_type": "process",
        "severity": "medium"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 10: EDGE CASES & CHALLENGING QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "EDGE_001",
        "query": "visa platinum dining rewards travel balance transfer installment",
        "expected_intent": "feature_inquiry",
        "test_type": "edge",
        "severity": "low",
        "description": "Multiple features in one query"
    },
    {
        "id": "EDGE_002",
        "query": "jcb gold",
        "expected_intent": "product_info",
        "should_extract": {"specific_product": "JCB Gold Credit Card"},
        "test_type": "edge",
        "severity": "medium",
        "description": "Minimal query"
    },
    {
        "id": "EDGE_003",
        "query": "Which card has the most benefits?",
        "expected_intent": "product_info",
        "test_type": "edge",
        "severity": "medium",
        "description": "Vague query requiring clarification"
    },
    {
        "id": "EDGE_004",
        "query": "Conventional cards with dining and lounge, I earn 40 lakh yearly",
        "expected_intent": "product_search_by_income",
        "should_extract": {"banking_type": "conventional", "annual_income": 4000000},
        "test_type": "edge",
        "severity": "high",
        "description": "Complex multi-feature query"
    },
    {
        "id": "EDGE_005",
        "query": "Islamic card, highest rewards, lounge access, 50 lakh income",
        "expected_intent": "feature_inquiry",
        "should_extract": {"banking_type": "islamic", "annual_income": 5000000},
        "test_type": "edge",
        "severity": "high",
        "description": "Multiple features + banking type + income"
    },
    {
        "id": "EDGE_006",
        "query": "mastercard vs visa comparison platinum tier",
        "expected_intent": "comparison",
        "should_contain": ["Mastercard", "Visa"],
        "test_type": "edge",
        "severity": "high",
        "description": "Multi-product comparison with tier filter"
    },
    {
        "id": "EDGE_007",
        "query": "50k monthly I want dining best card traditional banking",
        "expected_intent": "product_search_by_income",
        "should_extract": {"annual_income": 600000, "banking_type": "conventional"},
        "test_type": "edge",
        "severity": "high",
        "description": "Natural language with income + use case + banking type"
    },
    {
        "id": "EDGE_008",
        "query": "Best for international travel Visa only lounge platinum tier 30 lakh income",
        "expected_intent": "feature_inquiry",
        "should_extract": {"annual_income": 3000000},
        "should_contain": ["Visa", "platinum", "lounge"],
        "test_type": "edge",
        "severity": "high",
        "description": "Complex query with all entities"
    },
    
    # ─────────────────────────────────────────────────────────────────────────
    # PART 11: NEGATIVE & OFF-TOPIC QUERIES
    # ─────────────────────────────────────────────────────────────────────────
    
    {
        "id": "NEG_001",
        "query": "What's the weather today?",
        "expected_intent": "off_topic",
        "should_not_contain": ["credit", "card"],
        "test_type": "negative",
        "severity": "medium",
        "description": "Completely off-topic"
    },
    {
        "id": "NEG_002",
        "query": "Tell me a joke",
        "expected_intent": "off_topic",
        "test_type": "negative",
        "severity": "low",
        "description": "Non-banking query"
    },
    {
        "id": "NEG_003",
        "query": "Do you have car loans?",
        "expected_intent": "product_info",
        "should_not_contain": ["credit card"],
        "test_type": "negative",
        "severity": "medium",
        "description": "Different product type"
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

class ComprehensiveTestRunner:
    def __init__(self):
        self.results = []
        self.session = requests.Session()
    
    def run_all_tests(self):
        print("\n" + "="*80)
        print(" PRIME BANK CHATBOT - COMPREHENSIVE TEST SUITE")
        print("="*80 + "\n")
        
        total = len(COMPREHENSIVE_TESTS)
        passed = 0
        failed = 0
        
        # Group by test_type
        by_type = {}
        for test in COMPREHENSIVE_TESTS:
            test_type = test.get("test_type", "unknown")
            if test_type not in by_type:
                by_type[test_type] = []
            by_type[test_type].append(test)
        
        for test_type in sorted(by_type.keys()):
            tests = by_type[test_type]
            print(f"\n📋 {test_type.upper()} TESTS ({len(tests)} total)")
            print("─" * 80)
            
            for test in tests:
                try:
                    result = self.run_single_test(test)
                    self.results.append(result)
                    
                    if result["passed"]:
                        passed += 1
                        print(f"{PASS} {result['test_id']}: {result['query'][:60]}")
                    else:
                        failed += 1
                        print(f"{FAIL} {result['test_id']}: {result['query'][:60]}")
                        print(f"   Reason: {result['failure_reason']}")
                    
                    time.sleep(DELAY_BETWEEN_TESTS)
                except Exception as e:
                    failed += 1
                    print(f"{FAIL} {test['id']}: ERROR - {str(e)[:60]}")
        
        # Summary
        print("\n" + "="*80)
        print(" SUMMARY")
        print("="*80)
        print(f"✅ PASSED: {passed}/{total}")
        print(f"❌ FAILED: {failed}/{total}")
        print(f"📊 PASS RATE: {(passed/total)*100:.1f}%")
        print("="*80 + "\n")
        
        return passed, failed, total
    
    def run_single_test(self, test):
        """Run a single test and return result dict"""
        session_id = str(uuid.uuid4())
        query = test.get("query")
        test_id = test.get("id")
        
        try:
            response = self.session.post(
                f"{BASE_URL}/chat",
                json={"query": query, "session_id": session_id},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Check response structure
            if "detected_intent" not in data:
                return {
                    "test_id": test_id,
                    "query": query,
                    "passed": False,
                    "failure_reason": "Missing 'detected_intent' in response"
                }
            
            # Check intent
            detected_intent = data["detected_intent"].get("intent_type", "unknown")
            expected_intent = test.get("expected_intent", "unknown")
            
            if detected_intent != expected_intent:
                return {
                    "test_id": test_id,
                    "query": query,
                    "passed": False,
                    "failure_reason": f"Expected intent '{expected_intent}', got '{detected_intent}'"
                }
            
            # Check entity extraction
            expected_entities = test.get("should_extract", {})
            for key, expected_val in expected_entities.items():
                actual_val = data["detected_intent"].get(key)
                if isinstance(expected_val, int):
                    # Allow ~5% variance for numeric values
                    tolerance = abs(expected_val * 0.05)
                    if not actual_val or abs(actual_val - expected_val) > tolerance:
                        return {
                            "test_id": test_id,
                            "query": query,
                            "passed": False,
                            "failure_reason": f"Entity '{key}': expected ~{expected_val}, got {actual_val}"
                        }
                elif actual_val != expected_val:
                    return {
                        "test_id": test_id,
                        "query": query,
                        "passed": False,
                        "failure_reason": f"Entity '{key}': expected '{expected_val}', got '{actual_val}'"
                    }
            
            # Check response content (should_contain)
            answer = data.get("answer", "").lower()
            should_contains = test.get("should_contain", [])
            for phrase in should_contains:
                if phrase.lower() not in answer:
                    return {
                        "test_id": test_id,
                        "query": query,
                        "passed": False,
                        "failure_reason": f"Response missing phrase: '{phrase}'"
                    }
            
            # Check response content (should_not_contain)
            should_not_contains = test.get("should_not_contain", [])
            for phrase in should_not_contains:
                if phrase.lower() in answer:
                    return {
                        "test_id": test_id,
                        "query": query,
                        "passed": False,
                        "failure_reason": f"Response contains unwanted phrase: '{phrase}'"
                    }
            
            # Check product count
            products_found = len(data.get("products_found", []))
            expected_min = test.get("expected_products_min", 0)
            if expected_min > 0 and products_found < expected_min:
                return {
                    "test_id": test_id,
                    "query": query,
                    "passed": False,
                    "failure_reason": f"Expected >= {expected_min} products, got {products_found}"
                }
            
            return {
                "test_id": test_id,
                "query": query,
                "passed": True,
                "failure_reason": None,
                "detected_intent": detected_intent,
                "products_found": products_found
            }
        
        except Exception as e:
            return {
                "test_id": test_id,
                "query": query,
                "passed": False,
                "failure_reason": f"Exception: {str(e)[:60]}"
            }


if __name__ == "__main__":
    runner = ComprehensiveTestRunner()
    passed, failed, total = runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)
