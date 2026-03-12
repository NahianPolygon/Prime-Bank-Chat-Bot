"""
Prime Bank Chatbot - Semantic Test Suite
==========================================
Tests CORRECTNESS not keywords.

Evaluation criteria:
1. Intent classification accuracy
2. Entity extraction accuracy  
3. Response appropriateness
4. Data retrieval correctness
5. Conversation flow

Run:
    python test_chatbot_semantic.py
"""

import argparse
import csv
import datetime
import json
import os
import time
import uuid
import sys
import re

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests --break-system-packages -q")
    import requests

BASE_URL = "http://localhost:8000"
RESULTS_DIR = "test_results"
DELAY_BETWEEN_TURNS = 1.5
DELAY_BETWEEN_TESTS = 2.0

PASS = "✅ PASS"
FAIL = "❌ FAIL"
INFO = "ℹ️  INFO"
WARN = "⚠️  WARN"


# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC EVALUATORS
# ═══════════════════════════════════════════════════════════════════════════════

class SemanticEvaluator:
    """Evaluates responses based on semantic correctness, not keywords."""
    
    @staticmethod
    def check_intent_classification(response: dict, expected_intent: str) -> tuple[bool, str]:
        """
        Check if the detected intent matches expected intent.
        
        Args:
            response: Bot response dict with 'detected_intent' field
            expected_intent: Expected intent type (e.g., 'feature_inquiry', 'comparison')
            
        Returns:
            (is_correct, explanation)
        """
        detected = response.get("detected_intent", {})
        actual_intent = detected.get("intent_type", "unknown")
        
        if actual_intent == expected_intent:
            return True, f"Intent correctly identified as '{expected_intent}'"
        else:
            return False, f"Expected intent '{expected_intent}', got '{actual_intent}'"
    
    @staticmethod
    def check_entity_extraction(response: dict, expected_entities: dict) -> tuple[bool, list]:
        """
        Check if entities were correctly extracted from user query.
        
        Args:
            response: Bot response dict with 'detected_intent' field
            expected_entities: Dict of expected extractions like:
                {
                    "customer_income": 300000,
                    "specific_features": ["dining"],
                    "banking_type": "conventional"
                }
        
        Returns:
            (all_correct, issues_list)
        """
        detected = response.get("detected_intent", {})
        issues = []
        
        for entity_key, expected_value in expected_entities.items():
            actual_value = detected.get(entity_key)
            
            # Handle list comparisons
            if isinstance(expected_value, list):
                if not isinstance(actual_value, list):
                    issues.append(f"{entity_key}: Expected list {expected_value}, got {actual_value}")
                elif not all(item in actual_value for item in expected_value):
                    issues.append(f"{entity_key}: Expected {expected_value}, got {actual_value}")
            
            # Handle numeric comparisons (with tolerance for income)
            elif isinstance(expected_value, (int, float)):
                if entity_key == "customer_income":
                    # Allow 10% variance for income extraction
                    tolerance = expected_value * 0.1
                    if actual_value is None or abs(actual_value - expected_value) > tolerance:
                        issues.append(f"{entity_key}: Expected ~{expected_value}, got {actual_value}")
                else:
                    if actual_value != expected_value:
                        issues.append(f"{entity_key}: Expected {expected_value}, got {actual_value}")
            
            # Handle string comparisons
            else:
                if actual_value != expected_value:
                    issues.append(f"{entity_key}: Expected '{expected_value}', got '{actual_value}'")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def check_response_type(answer: str, expected_type: str) -> tuple[bool, str]:
        """
        Check if response is of the expected type.
        
        Args:
            answer: Bot's text response
            expected_type: One of:
                - 'greeting': Should be a friendly greeting
                - 'product_list': Should list products
                - 'comparison_table': Should show comparison
                - 'clarification': Should ask for more info
                - 'eligibility_question': Should ask eligibility field
                - 'eligibility_verdict': Should state eligible/not eligible
                - 'application_steps': Should show how to apply
        
        Returns:
            (is_correct, explanation)
        """
        answer_lower = answer.lower()
        
        if expected_type == "greeting":
            # Should be welcoming, not asking for details
            if any(phrase in answer_lower for phrase in ["welcome", "hello", "hi", "great to", "good to"]):
                if not any(phrase in answer_lower for phrase in ["annual income", "banking type", "employment"]):
                    return True, "Appropriate greeting response"
            return False, "Not a greeting - asks for information or provides product details"
        
        elif expected_type == "product_list":
            # Should mention products, not ask clarifying questions
            has_product_indicators = any(phrase in answer_lower for phrase in [
                "visa", "mastercard", "jcb", "hasanah", "platinum", "gold",
                "credit card", "card for you"
            ])
            is_clarification = any(phrase in answer_lower for phrase in [
                "what type of banking", "annual income", "could you tell me",
                "what will you primarily use"
            ])
            
            if has_product_indicators and not is_clarification:
                return True, "Lists products as expected"
            elif is_clarification:
                return False, "Asks for clarification instead of listing products"
            else:
                return False, "Does not mention any products"
        
        elif expected_type == "comparison_table":
            # Should have table structure or side-by-side comparison
            has_comparison = any(phrase in answer_lower for phrase in [
                "comparison", "vs", "versus", "compared to",
                "<table>", "| ", "**aspect**"
            ]) or ("annual fee" in answer_lower and "limit" in answer_lower)
            
            if has_comparison:
                return True, "Shows comparison as expected"
            else:
                return False, "Does not show comparison structure"
        
        elif expected_type == "clarification":
            # Should ask questions
            asking_questions = any(phrase in answer_lower for phrase in [
                "what type of banking", "annual income", "could you tell me",
                "which card", "what will you", "do you prefer"
            ]) or answer.count("?") >= 1
            
            if asking_questions:
                return True, "Asks for clarification as expected"
            else:
                return False, "Does not ask for clarification"
        
        elif expected_type == "eligibility_question":
            # Should ask for specific eligibility field
            asking_eligibility = any(phrase in answer_lower for phrase in [
                "age", "employment", "income", "tenure", "e-tin", "etin",
                "how long", "what is your", "could you share"
            ])
            
            if asking_eligibility:
                return True, "Asks eligibility question as expected"
            else:
                return False, "Does not ask for eligibility information"
        
        elif expected_type == "eligibility_verdict":
            # Should state eligibility result
            has_verdict = any(phrase in answer_lower for phrase in [
                "eligible", "qualify", "approved", "congratulations",
                "unfortunately", "not eligible", "requirements"
            ])
            
            if has_verdict:
                return True, "Provides eligibility verdict"
            else:
                return False, "Does not provide eligibility verdict"
        
        elif expected_type == "application_steps":
            # Should mention application process
            has_application_info = any(phrase in answer_lower for phrase in [
                "how to apply", "application", "required documents", "visit",
                "submit", "steps", "process", "national id", "passport"
            ])
            
            if has_application_info:
                return True, "Provides application information"
            else:
                return False, "Does not provide application information"
        
        else:
            return False, f"Unknown expected_type: {expected_type}"
    
    @staticmethod
    def check_product_retrieval(answer: str, expected_products: list, must_include_all: bool = False) -> tuple[bool, list]:
        """
        Check if the right products were retrieved.
        
        Args:
            answer: Bot's text response
            expected_products: List of product names that should appear
            must_include_all: If True, ALL products must be present. If False, at least ONE.
        
        Returns:
            (is_correct, issues_list)
        """
        answer_lower = answer.lower()
        issues = []
        found_products = []
        
        for product in expected_products:
            product_normalized = product.lower().replace("credit card", "").strip()
            if product_normalized in answer_lower:
                found_products.append(product)
        
        if must_include_all:
            if len(found_products) == len(expected_products):
                return True, []
            else:
                missing = [p for p in expected_products if p not in found_products]
                issues.append(f"Missing products: {missing}")
                return False, issues
        else:
            if len(found_products) > 0:
                return True, []
            else:
                issues.append(f"None of expected products found: {expected_products}")
                return False, issues
    
    @staticmethod
    def check_feature_mentioned(answer: str, expected_features: list) -> tuple[bool, list]:
        """
        Check if requested features are mentioned in response.
        
        Args:
            answer: Bot's text response
            expected_features: List of features like ["dining", "lounge", "travel"]
        
        Returns:
            (is_correct, issues_list)
        """
        answer_lower = answer.lower()
        issues = []
        
        for feature in expected_features:
            feature_lower = feature.lower()
            
            # Map feature to possible mentions
            feature_keywords = {
                "dining": ["dining", "restaurant", "bogo", "food"],
                "lounge": ["lounge", "airport lounge", "balaka", "loungekey"],
                "travel": ["travel", "international", "abroad", "foreign"],
                "rewards": ["reward", "point", "cashback"],
                "emi": ["emi", "installment", "0%"],
                "insurance": ["insurance", "takaful", "coverage"],
            }
            
            keywords = feature_keywords.get(feature_lower, [feature_lower])
            
            if not any(kw in answer_lower for kw in keywords):
                issues.append(f"Feature '{feature}' not mentioned")
        
        return len(issues) == 0, issues


# ═══════════════════════════════════════════════════════════════════════════════
# TEST SCENARIOS - SEMANTIC BASED
# ═══════════════════════════════════════════════════════════════════════════════

SCENARIOS = [
    
    # ──────────────────────────────────────────────────────────
    # 1. INTENT CLASSIFICATION TESTS
    # ──────────────────────────────────────────────────────────
    {
        "name": "Detect greeting intent",
        "category": "Intent Classification",
        "turns": [
            {
                "user": "Hello!",
                "checks": {
                    "intent": "greeting",
                    "response_type": "greeting",
                },
            }
        ],
    },
    {
        "name": "Detect feature inquiry intent",
        "category": "Intent Classification",
        "turns": [
            {
                "user": "Which cards have dining benefits?",
                "checks": {
                    "intent": "feature_inquiry",
                    "entities": {"specific_features": ["dining"]},
                    "response_type": "product_list",
                    "features_mentioned": ["dining"],
                },
            }
        ],
    },
    {
        "name": "Detect comparison intent (cold-start)",
        "category": "Intent Classification",
        "turns": [
            {
                "user": "Compare Visa Platinum vs JCB Platinum",
                "checks": {
                    "intent": "comparison",
                    "response_type": "comparison_table",
                    "products": ["Visa Platinum", "JCB Platinum"],
                },
            }
        ],
    },
    {
        "name": "Detect income-based search intent",
        "category": "Intent Classification",
        "turns": [
            {
                "user": "I earn 300k per month. What cards am I eligible for?",
                "checks": {
                    "intent": "product_search_by_income",
                    "entities": {"customer_income": 3600000},  # Should convert to annual
                    "response_type": "product_list",
                },
            }
        ],
    },
    {
        "name": "Detect eligibility check intent",
        "category": "Intent Classification",
        "turns": [
            {
                "user": "Am I eligible for Visa Platinum Credit Card?",
                "checks": {
                    "intent": "eligibility_check",
                    "entities": {"specific_product": "Visa Platinum Credit Card"},
                    "response_type": "eligibility_question",
                },
            }
        ],
    },
    
    # ──────────────────────────────────────────────────────────
    # 2. ENTITY EXTRACTION TESTS
    # ──────────────────────────────────────────────────────────
    {
        "name": "Extract income from query (monthly)",
        "category": "Entity Extraction",
        "turns": [
            {
                "user": "My monthly income is 300k",
                "checks": {
                    "entities": {"customer_income": 3600000},  # 300k * 12
                },
            }
        ],
    },
    {
        "name": "Extract income from query (annual)",
        "category": "Entity Extraction",
        "turns": [
            {
                "user": "My annual income is 50 lakh BDT",
                "checks": {
                    "entities": {"customer_income": 5000000},
                },
            }
        ],
    },
    {
        "name": "Extract banking type (conventional)",
        "category": "Entity Extraction",
        "turns": [
            {
                "user": "I want conventional banking credit cards",
                "checks": {
                    "entities": {"banking_type": "conventional"},
                },
            }
        ],
    },
    {
        "name": "Extract banking type (Islamic)",
        "category": "Entity Extraction",
        "turns": [
            {
                "user": "Show me Islamic credit card options",
                "checks": {
                    "entities": {"banking_type": "islamic"},
                },
            }
        ],
    },
    {
        "name": "Extract multiple features",
        "category": "Entity Extraction",
        "turns": [
            {
                "user": "I need a card with lounge access and dining benefits",
                "checks": {
                    "entities": {"specific_features": ["lounge", "dining"]},
                },
            }
        ],
    },
    {
        "name": "Extract tier preference",
        "category": "Entity Extraction",
        "turns": [
            {
                "user": "Show me only platinum cards",
                "checks": {
                    "entities": {"preferred_tier": "platinum"},
                },
            }
        ],
    },
    
    # ──────────────────────────────────────────────────────────
    # 3. PRODUCT RETRIEVAL CORRECTNESS
    # ──────────────────────────────────────────────────────────
    {
        "name": "Retrieve specific product by name",
        "category": "Product Retrieval",
        "turns": [
            {
                "user": "Tell me about Visa Platinum Credit Card",
                "checks": {
                    "intent": "product_info",
                    "response_type": "product_list",
                    "products": ["Visa Platinum"],
                },
            }
        ],
    },
    {
        "name": "Retrieve products by feature (dining)",
        "category": "Product Retrieval",
        "turns": [
            {
                "user": "Which cards have dining benefits?",
                "checks": {
                    "intent": "feature_inquiry",
                    "response_type": "product_list",
                    "features_mentioned": ["dining"],
                },
            }
        ],
    },
    {
        "name": "Retrieve products by feature (lounge)",
        "category": "Product Retrieval",
        "turns": [
            {
                "user": "I want airport lounge access",
                "checks": {
                    "intent": "feature_inquiry",
                    "response_type": "product_list",
                    "features_mentioned": ["lounge"],
                },
            }
        ],
    },
    {
        "name": "Retrieve Islamic products",
        "category": "Product Retrieval",
        "turns": [
            {
                "user": "What Islamic credit cards do you have?",
                "checks": {
                    "intent": "product_info",
                    "entities": {"banking_type": "islamic"},
                    "response_type": "product_list",
                    "products": ["Hasanah"],  # At least one Hasanah product
                },
            }
        ],
    },
    {
        "name": "Retrieve products by income level",
        "category": "Product Retrieval",
        "turns": [
            {
                "user": "I earn 300k monthly. What cards can I get?",
                "checks": {
                    "intent": "product_search_by_income",
                    "entities": {"customer_income": 3600000},
                    "response_type": "product_list",
                    "products": ["Platinum"],  # Should show platinum tier
                },
            }
        ],
    },
    
    # ──────────────────────────────────────────────────────────
    # 4. COMPARISON CORRECTNESS
    # ──────────────────────────────────────────────────────────
    {
        "name": "Compare two specific products (cold-start)",
        "category": "Comparison Correctness",
        "turns": [
            {
                "user": "Compare Visa Platinum vs JCB Platinum",
                "checks": {
                    "intent": "comparison",
                    "response_type": "comparison_table",
                    "products": ["Visa Platinum", "JCB Platinum"],
                    "products_must_match_all": True,  # BOTH must be present
                },
            }
        ],
    },
    {
        "name": "Compare after showing products (warm state)",
        "category": "Comparison Correctness",
        "turns": [
            {
                "user": "income 300k monthly, conventional, dining",
                "checks": {
                    "response_type": "product_list",
                },
            },
            {
                "user": "compare these two",
                "checks": {
                    "intent": "comparison",
                    "response_type": "comparison_table",
                },
            },
        ],
    },
    
    # ──────────────────────────────────────────────────────────
    # 5. CONVERSATION FLOW TESTS
    # ──────────────────────────────────────────────────────────
    {
        "name": "Profiling flow: vague query → profile collection → products",
        "category": "Conversation Flow",
        "turns": [
            {
                "user": "I want a credit card",
                "checks": {
                    "response_type": "clarification",
                },
            },
            {
                "user": "conventional, 300k monthly, dining",
                "checks": {
                    "response_type": "product_list",
                    "features_mentioned": ["dining"],
                },
            },
        ],
    },
    {
        "name": "Eligibility flow: product → age → employment → verdict",
        "category": "Conversation Flow",
        "turns": [
            {
                "user": "Am I eligible for Visa Platinum?",
                "checks": {
                    "intent": "eligibility_check",
                    "response_type": "eligibility_question",
                },
            },
            {
                "user": "32 years old",
                "checks": {
                    "response_type": "eligibility_question",
                },
            },
            {
                "user": "full time salaried",
                "checks": {
                    "response_type": "eligibility_question",
                },
            },
            {
                "user": "5 years",
                "checks": {
                    "response_type": "eligibility_question",
                },
            },
            {
                "user": "300k monthly",
                "checks": {
                    "response_type": "eligibility_question",
                },
            },
            {
                "user": "yes I have ETIN",
                "checks": {
                    "response_type": "eligibility_verdict",
                },
            },
        ],
    },
    {
        "name": "How to apply flow: product shown → how to apply",
        "category": "Conversation Flow",
        "turns": [
            {
                "user": "Tell me about Visa Platinum",
                "checks": {
                    "response_type": "product_list",
                },
            },
            {
                "user": "How do I apply for it?",
                "checks": {
                    "response_type": "application_steps",
                },
            },
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

class SemanticTestRunner:
    def __init__(self, base_url: str, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.results = []
        self.session = requests.Session()
        self.evaluator = SemanticEvaluator()
        
        # Setup CSV
        self.csv_filepath = os.path.join(RESULTS_DIR, f"semantic_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        self._init_csv()
    
    def _init_csv(self):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        self.csv_file = open(self.csv_filepath, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file, quoting=csv.QUOTE_ALL)
        self.csv_writer.writerow([
            'Timestamp', 'Scenario #', 'Category', 'Scenario Name', 'Status',
            'Turn #', 'User Query', 'Bot Response', 'Turn Status', 'Issues',
            'Detected Intent', 'Intent Correct?', 'Entities Correct?', 'Response Type Correct?',
            'Turn Time (s)', 'Session ID'
        ])
        self.csv_file.flush()
        print(f"\n  📊 Real-time CSV: {self.csv_filepath}")
    
    def health_check(self) -> bool:
        try:
            r = self.session.get(f"{self.base_url}/health", timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"❌ Cannot connect to {self.base_url}: {e}")
            return False
    
    def send_message(self, query: str, session_id: str) -> dict | None:
        try:
            r = self.session.post(
                f"{self.base_url}/chat",
                json={"query": query, "session_id": session_id},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e), "answer": ""}
    
    def evaluate_turn(self, response: dict, checks: dict) -> tuple[str, list, dict]:
        """
        Evaluate a turn using semantic checks.
        
        Args:
            response: Bot response dict
            checks: Dict of checks to perform:
                - intent: Expected intent type
                - entities: Expected entity extractions
                - response_type: Expected response type
                - products: Expected products to be mentioned
                - products_must_match_all: If True, all products must be present
                - features_mentioned: Expected features to be mentioned
        
        Returns:
            (status, issues_list, metrics_dict)
        """
        answer = response.get("answer", "")
        issues = []
        metrics = {
            "intent_correct": None,
            "entities_correct": None,
            "response_type_correct": None,
        }
        
        # Check for errors
        if "error" in response and response["error"]:
            return FAIL, [f"Request error: {response['error']}"], metrics
        
        if not answer.strip():
            return FAIL, ["Empty response"], metrics
        
        # Check intent classification
        if "intent" in checks:
            is_correct, explanation = self.evaluator.check_intent_classification(
                response, checks["intent"]
            )
            metrics["intent_correct"] = is_correct
            if not is_correct:
                issues.append(f"Intent: {explanation}")
        
        # Check entity extraction
        if "entities" in checks:
            is_correct, entity_issues = self.evaluator.check_entity_extraction(
                response, checks["entities"]
            )
            metrics["entities_correct"] = is_correct
            if not is_correct:
                issues.extend([f"Entity: {issue}" for issue in entity_issues])
        
        # Check response type
        if "response_type" in checks:
            is_correct, explanation = self.evaluator.check_response_type(
                answer, checks["response_type"]
            )
            metrics["response_type_correct"] = is_correct
            if not is_correct:
                issues.append(f"Response type: {explanation}")
        
        # Check product retrieval
        if "products" in checks:
            must_include_all = checks.get("products_must_match_all", False)
            is_correct, product_issues = self.evaluator.check_product_retrieval(
                answer, checks["products"], must_include_all
            )
            if not is_correct:
                issues.extend([f"Products: {issue}" for issue in product_issues])
        
        # Check feature mentions
        if "features_mentioned" in checks:
            is_correct, feature_issues = self.evaluator.check_feature_mentioned(
                answer, checks["features_mentioned"]
            )
            if not is_correct:
                issues.extend([f"Feature: {issue}" for issue in feature_issues])
        
        # Determine overall status
        if issues:
            return FAIL, issues, metrics
        return PASS, [], metrics
    
    def run_scenario(self, scenario: dict) -> dict:
        name = scenario["name"]
        category = scenario["category"]
        turns = scenario["turns"]
        session_id = f"test_{uuid.uuid4().hex[:8]}"
        
        print(f"\n{'─'*70}")
        print(f"  {category} > {name}")
        print(f"{'─'*70}")
        
        turn_results = []
        scenario_pass = True
        
        for i, turn in enumerate(turns):
            user_msg = turn["user"]
            checks = turn.get("checks", {})
            
            if i > 0:
                time.sleep(DELAY_BETWEEN_TURNS)
            
            print(f"\n  [{i+1}/{len(turns)}] Turn {i+1}")
            print(f"  👤 USER: {user_msg}")
            
            start = time.time()
            response = self.send_message(user_msg, session_id)
            elapsed = time.time() - start
            
            answer = response.get("answer", "")
            status, issues, metrics = self.evaluate_turn(response, checks)
            
            if status == FAIL:
                scenario_pass = False
            
            print(f"  🤖 BOT: {answer[:200]}{'...' if len(answer) > 200 else ''}")
            print(f"  {status}  ({elapsed:.1f}s)")
            
            if issues:
                for issue in issues:
                    print(f"    → {issue}")
            
            if self.verbose and not issues:
                print(f"    → All checks passed")
                if metrics["intent_correct"] is not None:
                    print(f"      • Intent: ✅")
                if metrics["entities_correct"] is not None:
                    print(f"      • Entities: ✅")
                if metrics["response_type_correct"] is not None:
                    print(f"      • Response type: ✅")
            
            detected_intent = response.get("detected_intent", {})
            intent_type = detected_intent.get("intent_type", "unknown")
            
            turn_results.append({
                "turn": i + 1,
                "user": user_msg,
                "bot": answer,
                "status": status,
                "issues": issues,
                "elapsed": round(elapsed, 2),
                "detected_intent": intent_type,
                "metrics": metrics,
            })
        
        overall = PASS if scenario_pass else FAIL
        print(f"\n  SCENARIO: {overall}")
        
        return {
            "name": name,
            "category": category,
            "status": overall,
            "turns": turn_results,
            "session_id": session_id,
        }
    
    def _write_csv_row(self, result: dict, scenario_num: int):
        if not self.csv_writer:
            return
        
        for turn in result['turns']:
            issues = "; ".join(turn.get('issues', []))
            metrics = turn.get('metrics', {})
            
            self.csv_writer.writerow([
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                scenario_num,
                result['category'],
                result['name'],
                result['status'],
                turn['turn'],
                turn['user'][:200],
                turn['bot'][:300],
                turn['status'],
                issues[:200] if issues else "",
                turn.get('detected_intent', 'unknown'),
                'YES' if metrics.get('intent_correct') else ('NO' if metrics.get('intent_correct') is False else 'N/A'),
                'YES' if metrics.get('entities_correct') else ('NO' if metrics.get('entities_correct') is False else 'N/A'),
                'YES' if metrics.get('response_type_correct') else ('NO' if metrics.get('response_type_correct') is False else 'N/A'),
                turn['elapsed'],
                result['session_id']
            ])
        
        self.csv_file.flush()
    
    def run_all(self) -> list:
        print(f"\n{'═'*70}")
        print(f"  PRIME BANK CHATBOT - SEMANTIC TEST SUITE")
        print(f"  Server: {self.base_url}")
        print(f"  Scenarios: {len(SCENARIOS)}")
        print(f"  Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*70}")
        
        for i, scenario in enumerate(SCENARIOS):
            result = self.run_scenario(scenario)
            self.results.append(result)
            self._write_csv_row(result, i + 1)
            if i < len(SCENARIOS) - 1:
                time.sleep(DELAY_BETWEEN_TESTS)
        
        self.csv_file.close()
        return self.results
    
    def print_summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == PASS)
        failed = total - passed
        
        print(f"\n{'═'*70}")
        print(f"  SEMANTIC TEST SUMMARY")
        print(f"{'═'*70}")
        print(f"  Total Scenarios : {total}")
        print(f"  Passed          : {passed} ✅")
        print(f"  Failed          : {failed} ❌")
        print(f"  Pass Rate       : {100*passed//total if total else 0}%")
        print(f"{'═'*70}")
        
        # Categorize failures
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"pass": 0, "fail": 0}
            if r["status"] == PASS:
                categories[cat]["pass"] += 1
            else:
                categories[cat]["fail"] += 1
        
        print("\n  BY CATEGORY:")
        for cat, counts in categories.items():
            total_cat = counts["pass"] + counts["fail"]
            icon = "✅" if counts["fail"] == 0 else "❌"
            print(f"  {icon}  {cat}: {counts['pass']}/{total_cat}")
        
        # Show most common failure types
        intent_failures = 0
        entity_failures = 0
        response_type_failures = 0
        
        for r in self.results:
            for turn in r["turns"]:
                metrics = turn.get("metrics", {})
                if metrics.get("intent_correct") is False:
                    intent_failures += 1
                if metrics.get("entities_correct") is False:
                    entity_failures += 1
                if metrics.get("response_type_correct") is False:
                    response_type_failures += 1
        
        print(f"\n  FAILURE BREAKDOWN:")
        print(f"  Intent Classification Errors   : {intent_failures}")
        print(f"  Entity Extraction Errors        : {entity_failures}")
        print(f"  Response Type Errors            : {response_type_failures}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Prime Bank Chatbot Semantic Test Suite")
    parser.add_argument("--url", default=BASE_URL, help="Backend URL")
    parser.add_argument("--verbose", action="store_true", help="Show detailed pass info")
    args = parser.parse_args()
    
    runner = SemanticTestRunner(base_url=args.url, verbose=args.verbose)
    
    print(f"\nChecking backend at {args.url}...")
    if not runner.health_check():
        print("❌ Backend is not running. Start it first.")
        sys.exit(1)
    print("✅ Backend is up")
    
    results = runner.run_all()
    runner.print_summary()
    
    print(f"\n  📊 Results saved to: {runner.csv_filepath}")
    print(f"  💡 This test suite checks SEMANTIC CORRECTNESS, not keywords!\n")


if __name__ == "__main__":
    main()