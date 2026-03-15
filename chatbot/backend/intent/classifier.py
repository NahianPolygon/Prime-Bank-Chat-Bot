"""
Semantic Intent Classifier for Prime Bank Chatbot
==================================================
Fixes applied:
- banking_type: now returns "islami" (not "islamic") to match ChromaDB filter
- income parse: clearer prompt examples fix "2 lakh/month" and "annual" cases
- income + features: post-process promotes to product_search_by_income
"""

from utils.ollama import ollama_chat, parse_json


class IntentClassifier:

    @staticmethod
    def classify(query: str, history: list, previous_intent: dict) -> dict:

        history_block = ""
        if history:
            recent = history[-4:]
            lines = [f"{m['role'].upper()}: {m['content'][:100]}" for m in recent]
            history_block = "CONVERSATION HISTORY:\n" + "\n".join(lines) + "\n\n"

        prev_context = ""
        if previous_intent and previous_intent.get("intent_type"):
            prev_context = f"PREVIOUS INTENT: {previous_intent.get('intent_type')}\n\n"

        user_prompt = f"""You are a semantic intent classifier for a banking chatbot.
Understand WHAT the customer wants. Output ONLY valid JSON.

{history_block}{prev_context}CURRENT QUERY: "{query}"

INTENT TYPES (choose ONE):
  "greeting"                 — Hello, hi, good morning
  "small_talk"               — Weather, jokes, off-topic chat
  "feature_inquiry"          — Asks about a specific feature, benefit, condition, or service
                               Examples: "cards with dining", "lounge access", "annual fee waiver condition",
                               "airport welcome service", "best rewards", "0% installment", "insurance coverage"
                               NOTE: "conventional" and "Islamic/Shariah" are banking TYPES, not features.
                               NOTE: Brands (Visa, Mastercard, JCB) and Tiers (Gold, Platinum) are CATEGORIES, not features.
                               "I need a conventional card" → product_info, NOT feature_inquiry
                               "Show me Mastercards" → search_by_category, NOT feature_inquiry
  "comparison"               — Comparing 2+ named products
  "eligibility_check"        — Customer asks if THEY personally qualify
  "product_search_by_income" — Customer states their income/salary and wants card recommendations
                               ALWAYS use this when income is mentioned with a card request.
                               Examples:
                               "My annual income is 50 lakh. Suggest a card." → product_search_by_income
                               "My salary is 2 lakh per month. Best card?" → product_search_by_income
                               "I earn 300k monthly, what cards?" → product_search_by_income
                               "Monthly income 100k. Which card?" → product_search_by_income
                               "I make 50k a month, recommend me something" → product_search_by_income
  "search_by_category"       — Customer asks for a list of multiple cards based on a broad category (Brand, Tier, or Type).
                               Brands: Visa, Mastercard, JCB. Tiers: Gold, Platinum, World.
                               Examples: "show me all the mastercards", "list all your gold cards", 
                               "what Islamic cards do you have", "what Visa cards do you offer", "tell me about JCB cards"
  "product_info"             — General single product info, or "I need a credit card"
  "existing_cardholder"      — Questions about their own existing card

ENTITY EXTRACTION:

BANKING TYPE — only if explicitly mentioned:
  "Islamic"/"Shariah"/"Hasanah"/"Riba-free"/"Ujrah" → "islami"
  "conventional"/"traditional"/"regular"             → "conventional"
  Not mentioned                                       → "unknown"
  ALWAYS write "islami" never "islamic"
  IMPORTANT: banking type is NOT a feature. A query like "I need a conventional card"
  has intent_type="product_info" and banking_type="conventional". Do NOT put
  "conventional" or "islamic" into specific_features.

CUSTOMER INCOME — convert to ANNUAL BDT:
  Step 1 — find raw number: "300k"=300000, "2 lakh"=200000, "50 lakh"=5000000
  Step 2 — detect period from words present in query:
    "per month" OR "monthly" OR "/month"          → MONTHLY → multiply by 12
    "per year" OR "annually" OR "annual" OR "yearly" → ANNUAL → do NOT multiply
    no period word at all                          → assume MONTHLY → multiply by 12
  Step 3 — calculate:

  EXAMPLES (memorise these):
    "300k monthly"             → 300000 × 12 = 3600000
    "2 lakh per month"         → 200000 × 12 = 2400000   ← NOT 2000000
    "2 lakh monthly"           → 200000 × 12 = 2400000
    "50 lakh annual"           → 5000000  (no multiply)   ← NOT 60000000
    "30 lakh annual revenue"   → 3000000  (no multiply)   ← NOT 36000000
    "annual income 5 lakh"     → 500000   (no multiply)
    "My annual income is 50 lakh" → 5000000  (no multiply)   ← NOT 60000000
    "100k"                     → 100000 × 12 = 1200000    (no period word → monthly)
    "5 lakh"                   → 500000 × 12 = 6000000    (no period word → monthly)
    "salary is 2 lakh per month" → 200000 × 12 = 2400000  (per month → monthly)
    "50k monthly I want dining" → 50000 × 12 = 600000     (monthly → extract income even mid-sentence)
    IMPORTANT: Extract income even when it appears alongside feature requests.
    "300k monthly, lounge and dining" → customer_income=3600000 AND features=["lounge","dining"]

SPECIFIC FEATURES — list the features the customer is asking about:
  Use short lowercase labels. Examples:
  "lounge","dining","bogo","rewards","cashback","emi","insurance","travel",
  "fee_waiver","airport_welcome","cash_advance","priority_pass","takaful",
  "interest_free","minimum_payment","credit_limit","supplementary_card"
  Be specific: "annual fee waiver condition" → ["fee_waiver"]
               "airport welcome service" → ["airport_welcome"]
               "cash advance" → ["cash_advance"]
               "0% installment" → ["emi"]
               "minimum payment" → ["minimum_payment"]
  Exclude non-credit-card features: "car_loans","mortgage","savings"

SPECIFIC PRODUCT — full name + "Credit Card":
  "Visa Platinum" → "Visa Platinum Credit Card" | not mentioned → ""

COMPARISON PRODUCTS — exactly 2 names (for comparison intent only):
  "Compare Visa vs JCB" → ["Visa Platinum Credit Card","JCB Gold Credit Card"]
  Otherwise → []

PREFERRED TIER: "platinum"|"gold"|"silver"|"unknown"
CARD BRAND: "visa"|"mastercard"|"jcb"|"unknown"

OUTPUT — raw JSON only, no markdown:
{{
  "category": "greeting|small_talk|banking",
  "intent_type": "<intent>",
  "product_type": "credit_card|general",
  "banking_type": "conventional|islami|unknown",
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
"""

        raw_response = ollama_chat(
            system="You are an intent classifier for a bank credit card chatbot. Output ONLY valid JSON. No markdown. No explanations.",
            user=user_prompt,
            temperature=0.0,
            max_tokens=800,
        )

        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split('\n')
            json_lines, in_json = [], False
            for line in lines:
                if line.strip().startswith("```"):
                    if in_json:
                        break
                    in_json = True
                    continue
                if in_json:
                    json_lines.append(line)
            cleaned = '\n'.join(json_lines)

        parsed = parse_json(cleaned)

        if not parsed or "intent_type" not in parsed:
            print(f"⚠️ Intent classification failed. Raw: {raw_response[:300]}")
            return IntentClassifier._fallback_intent(query)

        category    = str(parsed.get("category", "banking")).strip().lower()
        intent_type = str(parsed.get("intent_type", "product_info")).strip().lower()

        if category in ("greeting", "small_talk"):
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

        banking_type     = str(parsed.get("banking_type", "unknown")).strip().lower()
        preferred_tier   = str(parsed.get("preferred_tier", "unknown")).strip().lower()
        card_brand       = str(parsed.get("card_brand", "unknown")).strip().lower()
        specific_product = str(parsed.get("specific_product", "")).strip()

        # Normalise: LLM may return "islamic" despite instructions — force "islami"
        if banking_type == "islamic":
            banking_type = "islami"

        specific_features = parsed.get("specific_features", [])
        if not isinstance(specific_features, list):
            specific_features = []
        specific_features = [str(f).strip().lower() for f in specific_features if f]
        # Remove non-credit-card features the LLM may have hallucinated
        # Only exclude clearly non-credit-card topics
        invalid_features = {"car_loan","mortgage","savings","weather","joke"}
        specific_features = [f for f in specific_features if not any(inv in f for inv in invalid_features)]

        comparison_products = parsed.get("comparison_products", [])
        if not isinstance(comparison_products, list):
            comparison_products = []
        comparison_products = [str(p).strip() for p in comparison_products if p][:2]

        customer_income = parsed.get("customer_income")
        customer_income = int(customer_income) if isinstance(customer_income, (int, float)) and customer_income else None

        customer_age = parsed.get("customer_age")
        customer_age = int(customer_age) if isinstance(customer_age, (int, float)) and customer_age else None

        # ── Intent promotion ──────────────────────────────────────────────────
        # Income + features present → product_search_by_income (income is stronger signal)
        if intent_type == "feature_inquiry" and customer_income:
            intent_type = "product_search_by_income"

        # ── Validation ────────────────────────────────────────────────────────
        needs_clarification = False

        if intent_type == "feature_inquiry" and not specific_features:
            intent_type = "product_info"
            needs_clarification = True

        elif intent_type == "comparison":
            if len(comparison_products) < 2:
                comparison_products = IntentClassifier.extract_comparison_products(query)
            if len(comparison_products) < 2:
                needs_clarification = True

        elif intent_type == "product_search_by_income" and not customer_income:
            needs_clarification = True

        # Enum guards
        if banking_type not in ("conventional", "islami", "unknown"):
            banking_type = "unknown"
        if preferred_tier not in ("platinum", "gold", "silver", "unknown"):
            preferred_tier = "unknown"
        if card_brand not in ("visa", "mastercard", "jcb", "unknown"):
            card_brand = "unknown"

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

        print(f"🎯 Intent: {intent_type} | Income: {customer_income} | Features: {specific_features} | Product: '{specific_product}'")
        return intent

    @staticmethod
    def extract_comparison_products(query: str) -> list:
        raw = ollama_chat(
            system="Extract exactly 2 bank credit card names. Output ONLY a JSON array with 2 strings. No markdown.",
            user=f'''Query: "{query}"
Examples:
"Compare Visa Platinum vs JCB Platinum" → ["Visa Platinum Credit Card", "JCB Platinum Credit Card"]
"Visa Gold or Mastercard World?" → ["Visa Gold Credit Card", "Mastercard World Credit Card"]
Output ONLY the JSON array:''',
            temperature=0.0,
            max_tokens=60,
        )
        parsed = parse_json(raw)
        if isinstance(parsed, list) and len(parsed) == 2:
            return [str(p).strip() for p in parsed if p]
        return []

    @staticmethod
    def _fallback_intent(query: str) -> dict:
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