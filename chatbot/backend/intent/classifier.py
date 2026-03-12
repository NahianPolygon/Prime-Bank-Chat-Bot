"""
Semantic Intent Classifier for Prime Bank Chatbot
==================================================
This classifier understands WHAT the user wants, not just keywords.
Uses LLM-based semantic understanding with strict validation.

Key Principles:
1. Detect user's TRUE intent (comparison, feature search, eligibility, etc.)
2. Extract entities accurately (income, features, products, banking type)
3. No keyword matching - pure semantic understanding
4. Clear, unambiguous intent categories
"""

from utils.ollama import ollama_chat, parse_json


class IntentClassifier:
    """
    Semantic intent classifier that understands user goals.
    
    Intent Types:
    - greeting: Social greeting
    - small_talk: Casual conversation
    - feature_inquiry: Asking about specific features (dining, lounge, etc.)
    - comparison: Comparing 2+ products
    - eligibility_check: Asking if they qualify for a product
    - product_search_by_income: Showing products based on income
    - eligibility_matching: Income + feature combination
    - product_info: General product information
    - existing_cardholder: Questions about their existing card
    """

    @staticmethod
    def classify(query: str, history: list, previous_intent: dict) -> dict:
        """
        Classify user intent using semantic understanding.
        
        Args:
            query: User's current message
            history: Conversation history (list of dicts with 'role' and 'content')
            previous_intent: Previously detected intent (for context)
            
        Returns:
            Intent dict with detected intent_type, entities, and metadata
        """
        
        # Build conversation context
        history_block = ""
        if history and len(history) > 0:
            recent_history = history[-4:]  # Last 2 exchanges
            history_lines = [
                f"{msg['role'].upper()}: {msg['content'][:100]}" 
                for msg in recent_history
            ]
            history_block = "CONVERSATION HISTORY:\n" + "\n".join(history_lines) + "\n\n"
        
        # Build previous context
        prev_context = ""
        if previous_intent and previous_intent.get("intent_type"):
            prev_context = f"PREVIOUS INTENT: {previous_intent.get('intent_type')}\n\n"
        
        # Create semantic classification prompt
        system_prompt = """You are an intent classifier for a bank credit card chatbot.
Output ONLY valid JSON. No markdown. No explanations."""

        user_prompt = f"""You are a semantic intent classifier for a banking chatbot.

Your job: Understand WHAT the customer wants, not just match keywords.

Output ONLY valid JSON. No markdown. No explanations. Just the JSON object.

{history_block}{prev_context}CURRENT QUERY: "{query}"

═══════════════════════════════════════════════════════════════════
SEMANTIC INTENT CLASSIFICATION
═══════════════════════════════════════════════════════════════════

Read the query and understand what the customer is trying to accomplish.

═══════════════════════════════════════════════════════════════════
INTENT TYPES (Choose ONE):
═══════════════════════════════════════════════════════════════════

1. "greeting"
   When: Customer is greeting, saying hello, starting conversation
   Examples: "Hello", "Hi there", "Good morning", "Hey"

2. "small_talk"
   When: Casual conversation not about banking
   Examples: "How are you?", "What's the weather?", "Tell me a joke"

3. "feature_inquiry"
   When: Customer asks about cards with SPECIFIC features
   Examples:
   - "Which cards have dining benefits?"
   - "Cards with lounge access"
   - "I want rewards points"
   Must extract: specific_features (list of features mentioned)

4. "comparison"
   When: Customer wants to compare 2 or more specific products
   Examples:
   - "Compare Visa Platinum vs JCB Gold"
   - "Which is better: Mastercard or Visa?"
   - "Visa Platinum or JCB Platinum?"
   Must extract: comparison_products (list of 2 product names)

5. "eligibility_check"
   When: Customer asks if THEY qualify or are eligible
   Examples:
   - "Am I eligible for Visa Platinum?"
   - "Do I qualify for this card?"
   - "Can I get a credit card?"
   Must extract: specific_product (if mentioned)

6. "product_search_by_income"
   When: Customer mentions their income/salary and asks what they can get
   Examples:
   - "I earn 300k monthly, what cards?"
   - "Cards for 50k salary"
   - "What can I get with 5 lakh income?"
   Must extract: customer_income (in annual BDT)

7. "eligibility_matching"
   When: Customer gives BOTH income AND specific feature
   Examples:
   - "300k salary + lounge access"
   - "Cards with dining for 50k monthly income"
   Must extract: customer_income AND specific_features

8. "product_info"
   When: Customer asks about general product information
   Examples:
   - "Tell me about Visa Platinum"
   - "What credit cards do you have?"
   - "I need a credit card"
   May extract: specific_product (if mentioned)

9. "existing_cardholder"
   When: Customer asks about THEIR existing card
   Examples:
   - "What offers do I get?"
   - "My card is lost"
   - "Check my bill"

═══════════════════════════════════════════════════════════════════
ENTITY EXTRACTION RULES
═══════════════════════════════════════════════════════════════════

1. BANKING TYPE:
   Only extract if EXPLICITLY mentioned:
   - "Islamic", "Shariah", "Hasanah" → "islamic"
   - "Conventional", "traditional", "regular" → "conventional"
   - Not mentioned → "unknown"

2. CUSTOMER INCOME (CRITICAL - Calculate Annual):
   Extract number AND convert to ANNUAL BDT:

   STEP 1: Find the number
   - "300k" → 300,000
   - "5 lakh" → 500,000
   - "300000" → 300,000

   STEP 2: Determine if monthly or annual
   - Has "monthly", "per month", "/month" → MONTHLY
   - Has "annual", "yearly", "per year" → ANNUAL
   - Just a number in income context → assume MONTHLY

   STEP 3: Convert to annual
   - If MONTHLY: number × 12
   - If ANNUAL: number as-is

   Examples:
   - "300k monthly" → 300,000 × 12 = 3,600,000
   - "300k per month" → 300,000 × 12 = 3,600,000
   - "5 lakh" → 500,000 (no multiplication)
   - "50 lakh annual" → 5,000,000 (no multiplication)

   Output: Annual amount in BDT or null

3. SPECIFIC FEATURES:
   Extract list of features customer wants:
   - "dining", "lounge", "travel", "rewards", "cashback", "emi", "insurance"

   Examples:
   - "cards with dining" → ["dining"]
   - "lounge and rewards" → ["lounge", "rewards"]
   - "I want travel benefits" → ["travel"]

4. SPECIFIC PRODUCT:
   Extract FULL product name with "Credit Card" suffix:
   - "Visa Platinum" → "Visa Platinum Credit Card"
   - "JCB Gold" → "JCB Gold Credit Card"
   - Not mentioned → ""

5. COMPARISON PRODUCTS:
   Extract 2 product names for comparison:
   - "Compare Visa vs JCB" → ["Visa Platinum Credit Card", "JCB Gold Credit Card"]
   - Must be exactly 2 products
   - Empty list if not comparison

6. PREFERRED TIER:
   Only if explicitly mentioned:
   - "platinum", "gold", "silver" → extract that tier
   - Not mentioned → "unknown"

7. CARD BRAND:
   Only if explicitly mentioned:
   - "visa", "mastercard", "jcb" → extract that brand
   - Not mentioned → "unknown"

═══════════════════════════════════════════════════════════════════
VALIDATION RULES
═══════════════════════════════════════════════════════════════════

1. If intent_type = "feature_inquiry", must have specific_features list
2. If intent_type = "comparison", must have 2 comparison_products
3. If intent_type = "eligibility_matching", must have customer_income AND specific_features
4. If intent_type = "product_search_by_income", must have customer_income

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════

Return ONLY this JSON structure (no markdown, no explanations):

{{
  "category": "greeting|small_talk|banking",
  "intent_type": "<one of the 9 intent types>",
  "product_type": "credit_card|general",
  "banking_type": "conventional|islamic|unknown",
  "preferred_tier": "platinum|gold|silver|unknown",
  "card_brand": "visa|mastercard|jcb|unknown",
  "specific_product": "",
  "comparison_products": [],
  "specific_features": [],
  "customer_income": null,
  "customer_age": null,
  "search_dimension": "relevance",
  "needs_clarification": false,
  "relevance_score": 85,
  "is_off_topic": false
}}

CRITICAL JSON RULES - AVOID THESE ERRORS:
- ❌ WRONG: "card_brand": "visa" | "jcb"  (pipe operator breaks JSON)
- ✅ RIGHT: "card_brand": "unknown"  (use single value)
- ❌ WRONG: ```json {{ ... }}```  (no markdown blocks)
- ✅ RIGHT: {{ ... }}  (raw JSON only)

Output ONLY the JSON object. No text. No markdown. No explanations.
"""


        # Call LLM for classification
        raw_response = ollama_chat(
            system=system_prompt,
            user=user_prompt,
            temperature=0.0,  # Zero temperature for deterministic output
            max_tokens=800,
        )
        
        # Clean response - remove any markdown or extra text
        cleaned_response = raw_response.strip()
        
        # Remove markdown code blocks if present
        if cleaned_response.startswith("```"):
            # Extract JSON from markdown
            lines = cleaned_response.split('\n')
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    if in_json:
                        break
                    in_json = True
                    continue
                if in_json:
                    json_lines.append(line)
            cleaned_response = '\n'.join(json_lines)
        
        # Parse JSON response
        parsed = parse_json(cleaned_response)
        
        if not parsed or "intent_type" not in parsed:
            print(f"⚠️ Intent classification failed. Raw response:")
            print(f"   {raw_response[:500]}")
            print(f"⚠️ Using fallback intent for query: {query[:100]}")
            return IntentClassifier._fallback_intent(query)
        
        # Extract and validate fields
        category = str(parsed.get("category", "banking")).strip().lower()
        intent_type = str(parsed.get("intent_type", "product_info")).strip().lower()
        
        # Social queries (greeting, small_talk) get simplified response
        is_social = category in ("greeting", "small_talk")
        
        if is_social:
            return {
                "category": category,
                "intent_type": intent_type,
                "product_type": "general",
                "banking_type": "unknown",
                "preferred_tier": "unknown",
                "card_brand": "unknown",
                "specific_product": "",
                "comparison_products": [],
                "specific_features": [],
                "search_dimension": "relevance",
                "needs_clarification": False,
                "clarification_question": "",
                "customer_age": None,
                "customer_income": None,
                "customer_tenure_months": None,
                "relevance_score": 100,
                "is_off_topic": False,
            }
        
        # Extract banking queries
        banking_type = str(parsed.get("banking_type", "unknown")).strip().lower()
        preferred_tier = str(parsed.get("preferred_tier", "unknown")).strip().lower()
        card_brand = str(parsed.get("card_brand", "unknown")).strip().lower()
        specific_product = str(parsed.get("specific_product", "")).strip()
        
        # Extract lists
        specific_features = parsed.get("specific_features", [])
        if not isinstance(specific_features, list):
            specific_features = []
        specific_features = [str(f).strip().lower() for f in specific_features if f]
        
        comparison_products = parsed.get("comparison_products", [])
        if not isinstance(comparison_products, list):
            comparison_products = []
        comparison_products = [str(p).strip() for p in comparison_products if p][:2]
        
        # Extract numeric fields
        customer_income = parsed.get("customer_income")
        if customer_income and isinstance(customer_income, (int, float)):
            customer_income = int(customer_income)
        else:
            customer_income = None
        
        customer_age = parsed.get("customer_age")
        if customer_age and isinstance(customer_age, (int, float)):
            customer_age = int(customer_age)
        else:
            customer_age = None
        
        # Validate based on intent type
        needs_clarification = False
        
        if intent_type == "feature_inquiry":
            if not specific_features:
                # No features extracted - this shouldn't be feature_inquiry
                intent_type = "product_info"
                needs_clarification = True
        
        elif intent_type == "comparison":
            # If comparison intent but no products extracted, run dedicated extractor
            if len(comparison_products) < 2:
                comparison_products = IntentClassifier.extract_comparison_products(query)
            
            if len(comparison_products) < 2:
                # Still no 2 products after extraction attempt
                needs_clarification = True
        
        elif intent_type == "eligibility_matching":
            if not (customer_income and specific_features):
                # Need both income and features
                needs_clarification = True
        
        elif intent_type == "product_search_by_income":
            if not customer_income:
                # Need income for income search
                needs_clarification = True
        
        # Validate enum values
        if banking_type not in ("conventional", "islamic", "unknown"):
            banking_type = "unknown"
        
        if preferred_tier not in ("platinum", "gold", "silver", "unknown"):
            preferred_tier = "unknown"
        
        if card_brand not in ("visa", "mastercard", "jcb", "unknown"):
            card_brand = "unknown"
        
        # Build final intent object
        intent = {
            "category": "banking",
            "intent_type": intent_type,
            "product_type": "credit_card",
            "banking_type": banking_type,
            "preferred_tier": preferred_tier,
            "card_brand": card_brand,
            "specific_product": specific_product,
            "comparison_products": comparison_products,
            "specific_features": specific_features,
            "search_dimension": str(parsed.get("search_dimension", "relevance")).strip(),
            "needs_clarification": needs_clarification,
            "clarification_question": "" if not needs_clarification else "Could you tell me more about what you're looking for?",
            "customer_age": customer_age,
            "customer_income": customer_income,
            "customer_tenure_months": None,
            "relevance_score": int(parsed.get("relevance_score", 85)),
            "is_off_topic": bool(parsed.get("is_off_topic", False)),
        }
        
        # Debug logging
        print(f"🎯 Intent: {intent_type} | Income: {customer_income} | Features: {specific_features} | Product: '{specific_product}'")
        
        return intent
    
    @staticmethod
    def extract_comparison_products(query: str) -> list:
        """
        Dedicated micro-prompt for extracting exactly 2 product names from comparison queries.
        Runs only when comparison intent is detected but products weren't extracted.
        
        Args:
            query: User's query mentioning products to compare
            
        Returns:
            List of 2 product names with "Credit Card" suffix, or empty list if extraction fails
        """
        system_prompt = "Extract exactly 2 bank credit card names from the query. Output ONLY a JSON array with 2 strings. No markdown."
        
        user_prompt = f"""Query: "{query}"

Examples:
"Compare Visa Platinum vs JCB Platinum" → ["Visa Platinum Credit Card", "JCB Platinum Credit Card"]
"Visa Gold or Mastercard World?" → ["Visa Gold Credit Card", "Mastercard World Credit Card"]
"which is better mastercard platinum or jcb gold" → ["Mastercard Platinum Credit Card", "JCB Gold Credit Card"]

Output ONLY the JSON array:"""
        
        raw = ollama_chat(
            system=system_prompt,
            user=user_prompt,
            temperature=0.0,
            max_tokens=60,
        )
        
        parsed = parse_json(raw)
        if isinstance(parsed, list) and len(parsed) == 2:
            return [str(p).strip() for p in parsed if p]
        
        return []
    
    @staticmethod
    def _fallback_intent(query: str) -> dict:
        """
        Fallback intent when classification fails.
        Assumes generic product inquiry with clarification needed.
        """
        return {
            "category": "banking",
            "intent_type": "product_info",
            "product_type": "credit_card",
            "banking_type": "unknown",
            "preferred_tier": "unknown",
            "card_brand": "unknown",
            "specific_product": "",
            "comparison_products": [],
            "specific_features": [],
            "search_dimension": "relevance",
            "needs_clarification": True,
            "clarification_question": "Could you tell me more about what you're looking for?",
            "customer_age": None,
            "customer_income": None,
            "customer_tenure_months": None,
            "relevance_score": 50,
            "is_off_topic": False,
        }