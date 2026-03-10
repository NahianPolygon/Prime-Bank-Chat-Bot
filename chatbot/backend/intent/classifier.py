from utils.ollama import ollama_chat, parse_json


class IntentClassifier:

    @staticmethod
    def classify(query: str, history: list, previous_intent: dict) -> dict:
        history_block = ""
        if history:
            lines = [f"{m['role'].upper()}: {m['content']}" for m in history[-6:]]
            history_block = "Conversation:\n" + "\n".join(lines) + "\n\n"

        prev_block = ""
        if previous_intent and previous_intent.get("intent_type"):
            prev_block = (
                f"Previous: product_type={previous_intent.get('product_type', 'unknown')}, "
                f"banking_type={previous_intent.get('banking_type', 'unknown')}, "
                f"tier={previous_intent.get('tier', 'unknown')}\n\n"
            )

        prompt_system = "You are an intent classifier. Output only valid JSON. No explanation."

        prompt_user = f"""{history_block}{prev_block}TASK: Analyze and classify customer banking query.

QUERY: "{query}"

DYNAMIC INTENT CLASSIFICATION:
Determine the PRIMARY REQUEST TYPE:

0. Is customer asking about THEIR OWN EXISTING CARD or card services (not looking to GET a card)?
   Examples: "What offers do I get?", "My card is damaged", "How to activate my card", "Bill payment", "Check transaction history", "Lost card", "Reward points"
   Key distinction: "What dining offers do I GET?" (existing card) vs "Cards WITH dining offers?" (looking to buy)
   → intent_type: "existing_cardholder" (Route to cardholder service agent - they already have a card)

CONTEXT CHECK - RECENT PRODUCT RECOMMENDATION:
If the conversation history shows a recently recommended product (e.g., "Visa Gold Credit Card", "JCB Platinum", "Mastercard World"),
and the customer asks "how to apply?", "how do I apply?", "let me apply", or similar application words:
→ Identify the recommended product and classify as intent_type: "product_info" with specific_product set to the card name.
Example: "here are the best credit cards for you: Visa Gold Credit Card..." → User: "how to apply?" 
→ specific_product: "Visa Gold Credit Card", intent_type: "product_info"

MAIN INTENT CLASSIFICATION (for customers looking to GET/BUY products):
1. Does customer ask about a SPECIFIC FEATURE of a SPECIFIC PRODUCT?
   Example: "Tell me the reward points system of Visa Gold credit card" (product="Visa Gold", feature="rewards")
   → intent_type: "feature_inquiry" (Answer question about specific product feature)
   
2. Does customer compare 2+ named products (e.g., "Compare X vs Y" or "X vs Y which is better")?
   → intent_type: "comparison" (Compare specific products on features)
   
3. Does customer mention BOTH a feature AND an income/salary?
   Example: "cards with lounge access for 50k salary" (feature="lounge", income=600k)
   → intent_type: "eligibility_matching" (Find products matching feature + income)
   
4. Does customer mention ONLY an income/salary (no features, no specific products)?
   → intent_type: "product_search_by_income" (Show qualifying cards at that income level)
   
5. Does customer ask "how to apply" WITHOUT naming a specific product?
   EXCEPTION: If recent history shows a recommended product (e.g., "Visa Gold Credit Card"),
   treat "how to apply?" as product_info (retrieve that product's details).
   Otherwise, if it's a general question about application/documents/eligibility:
   Example: "What documents do I need?" or "Am I eligible for a credit card?"
   → intent_type: "eligibility_check" (Provide requirement/eligibility info)
   
6. Does customer ask about a SPECIFIC product's application details?
   Example: "How do I apply for Visa Gold?" or just "how to apply?" (after being shown Visa Gold)
   → intent_type: "product_info" (Retrieve that product's How to Apply section)
   
7. VAGUE/GENERIC queries without enough profile context (even if they say "which is best"):
   Example: "which credit card is best for me?", "recommend me a card", "I need a credit card"
   → intent_type: "product_info" + needs_clarification: true (Needs profiling questions)
   
8. DEFAULT (anything else product-related):
   → intent_type: "product_info" (Generic product search via RAG)

OUTPUT FIELDS (JSON):
1. category: "banking" | "greeting" | "small_talk"
2. intent_type: "existing_cardholder" | "eligibility_matching" | "product_search_by_income" | "feature_inquiry" | "comparison" | "eligibility_check" | "product_info"
3. product_type: "credit_card" | "loan" | "account" | "general"
4. banking_type: "conventional" | "islamic" | "unknown"
   STRICT RULE: ONLY output "conventional" or "islamic" if customer EXPLICITLY mentions preferences.
   If customer says "I want a credit card" or any vague query WITHOUT specifying banking type preference,
   you MUST output "unknown" (even though conventional is common, don't assume/default to it).
   Examples:
     "I want a card" → banking_type: "unknown" (NOT "conventional"!)
     "I prefer conventional" → banking_type: "conventional"
     "Give me an Islamic card" → banking_type: "islamic"
     "Which is best for me?" → banking_type: "unknown" (NOT "conventional"!)
5. specific_product: product name if named (e.g., "Visa Gold", "JCB Platinum"), else ""
6. specific_features: ARRAY of detected features ONLY if explicitly mentioned (e.g., ["dining", "rewards"]), or empty array []. 
   NOTE: ONLY include features with explicit keywords. "business" is NOT a feature keyword (it describes use case, not feature)
7. customer_income: ONLY if explicitly mentioned with number AND income keyword. Otherwise null. DO NOT INVENT.
8. customer_age: number if mentioned, else null
9. customer_tenure_months: number if mentioned, else null
10. search_dimension: if superlative query ("highest credit limit", "lowest fee"), what to rank by, else "relevance"
11. needs_clarification: true ONLY if query is vague and needs profiling. false otherwise.
12. clarification_question: ""

FEATURE DETECTION - STRICT, EXPLICIT ONLY:
Only return features that are EXPLICITLY MENTIONED in the query text.
DO NOT INFER or HALLUCINATE features based on assumptions.
"Business" is NOT a feature - it's just a use case description.
Only return features if their keywords appear in the query:
- Lounge: "lounge", "vip lounge", "lounge access", "priority pass", "airport lounge" → "lounge_access"
- Airport: "airport", "airport benefits", "airport welcome" → "airport_benefits"
- Dining: "dining", "bogo", "restaurant", "meal discount", "dining benefits" → "dining"
- Rewards: "rewards", "points", "cashback", "earning", "reward points" → "rewards"
- Travel: "travel", "international", "global", "foreign", "abroad" → "travel"
- EMI: "emi", "installment", "interest-free", "0%", "no interest" → "emi"
- Insurance: "insurance", "coverage", "death benefit", "accident" → "insurance"
- Credit Limit: "credit limit", "limit", "spending limit" → "credit_limit"
- Annual Fee: "annual fee", "fee waiver", "no fee" → "fee_waiver"

RULE: If query is "i want to know which credit card will be best for me", the LLM should return:
  specific_features: [] (empty array, because no features were explicitly mentioned)

INCOME EXTRACTION (STRICT - NEVER INVENT):
ONLY extract income if query contains BOTH:
  a) A number (35000, 5, 100, etc.)
  b) An income keyword (monthly, /month, salary, lakh, k, annual, /year, income, earn)

Conversion rules:
  Pattern matching order (use FIRST match):
  1. "NUMBER/month" or "NUMBER monthly" or "Nnumber monthly salary" → NUMBER * 12 (convert monthly to annual)
  2. "NUMBER thousand[s] monthly/taka/tk" → NUMBER * 1000 * 12  (e.g., "50 thousands monthly" → 600k/year)
  3. "NUMBER thousands" in income context → NUMBER * 1000 * 12  (assume monthly)
  4. "NUMBER lakh" or "NUMBER lac" → NUMBER * 100000 (e.g., "5 lakh" → 500k)
  5. "NUMBERk" NOT followed by "annual/yearly" → NUMBERk assumed MONTHLY → NUMBER * 1000 * 12
     (e.g., "50k" in income answer = 600k/year, not 50k/year)
  6. "NUMBERk annual" or "NUMBERk/year" → NUMBER * 1000 (only multiply by 1000, NOT by 12)
  7. "NUMBER annual" or "NUMBER/year" → NUMBER (as-is, already annual)
  8. "salary/income of NUMBER" → NUMBER * 12 (assume monthly)
  9. Plain "NUMBER" in income context (risky but OK) → assume monthly → NUMBER * 12

EXAMPLES:
  "50 thousands monthly" → 50 * 1000 * 12 = 600,000
  "50k" (answering income question) → 50 * 1000 * 12 = 600,000
  "50k annual" → 50 * 1000 = 50,000 (don't multiply by 12, it's annual)
  "5 lakh" → 5 * 100,000 = 500,000
  "600000" (when asked income) → 600,000 * 12 = 7,200,000 (assume monthly)
  "600000 annual" → 600,000 (don't multiply, it's annual)
  "35,000/month" → 35,000 * 12 = 420,000
  "salary 100000" → 100,000 * 12 = 1,200,000

If no clear number+keyword → RETURN NULL (NEVER GUESS)

OUTPUT FORMAT: Valid JSON only. No explanation.
JSON:"""

        raw = ollama_chat(prompt_system, prompt_user, temperature=0.0, max_tokens=500)
        parsed = parse_json(raw)

        if not parsed or "category" not in parsed:
            print(f"⚠️ Intent parse failed: {raw[:200]}")
            return IntentClassifier._fallback_intent(query, previous_intent)

        category = str(parsed.get("category", "banking")).strip().lower()

        if category == "banking":
            print(f"🔍 Intent: {parsed.get('intent_type')} | banking_type={parsed.get('banking_type')} | tier={parsed.get('tier')}")

        is_social = category in ("greeting", "small_talk")

        def carry(field: str, default: str = "unknown") -> str:
            if is_social:
                return default
            val = str(parsed.get(field) or default).strip().lower()
            if val in ("", "null", "none"):
                val = default
            return val if val != default else default

        intent_type = str(parsed.get("intent_type", "product_info")).strip().lower()
        banking_type = str(parsed.get("banking_type", "unknown")).strip().lower()
        specific_product = str(parsed.get("specific_product") or "").strip()
        specific_features = parsed.get("specific_features") or []
        
        # VALIDATION: banking_type must be a single value (never pipe-separated)
        # If LLM outputs "conventional|islamic" or similar, treat as "unknown"
        if "|" in banking_type or "," in banking_type:
            banking_type = "unknown"
        
        # VALIDATION: feature_inquiry requires BOTH specific_product AND specific_features
        # If LLM classified as feature_inquiry but missing either → reclass as product_info (vague) + DON'T mark as needs_clarification
        # The ClarificationBuilder in main.py will handle profiling questions
        if intent_type == "feature_inquiry" and (not specific_product or not specific_features):
            intent_type = "product_info"
            needs_clarification = False  # Let ClarificationBuilder handle it
        else:
            # Clarification needed for specific intents or if LLM says so
            # For existing_cardholder, never needs clarification from intent classifier
            if intent_type in ("product_info", "product_search_by_income", "eligibility_check", "eligibility_matching", "existing_cardholder"):
                needs_clarification = False
            else:
                needs_clarification = bool(parsed.get("needs_clarification", False))

        # SPECIAL CASE: If user asks "how to apply?" and recently shown a product, treat as product_info
        # This handles cases like: "Great! Based on your profile...Visa Gold Credit Card..." → "how to apply?"
        if (intent_type == "eligibility_check" and 
            query.lower() in ("how to apply?", "how do i apply?", "how to apply", "how do i apply", "how can i apply?", "let me apply", "apply now", "how do i apply for it?") and
            not specific_product):
            # Search history for recently mentioned product names
            product_names = ["visa gold", "visa platinum", "jcb gold", "jcb platinum", "mastercard gold", "mastercard platinum", "mastercard world"]
            for msg in reversed(history[-8:] if history else []):  # Look back in last 8 messages
                if msg.get("role") == "assistant":
                    content_lower = msg.get("content", "").lower()
                    for product in product_names:
                        if product in content_lower:
                            # Found recently recommended product
                            specific_product = product.replace(" ", " ").title()  # "Visa Gold" format
                            intent_type = "product_info"
                            break
                    if specific_product:
                        break

        intent = {
            "category": category,
            "intent_type": intent_type,
            "product_type": "credit_card" if not is_social else "general",
            "banking_type": banking_type,
            "specific_product": "" if is_social else str(parsed.get("specific_product") or specific_product or "").strip(),
            "specific_features": [] if is_social else (parsed.get("specific_features") or []),  # Array of features
            "search_dimension": "" if is_social else str(parsed.get("search_dimension") or "relevance").strip(),
            "needs_clarification": needs_clarification,
            "clarification_question": "" if needs_clarification is False else "Could you tell me more about what you're looking for?",
            "customer_age": None if is_social else parsed.get("customer_age"),
            "customer_income": None if is_social else parsed.get("customer_income"),
            "customer_tenure_months": None if is_social else parsed.get("customer_tenure_months"),
        }

        return intent

    @staticmethod
    def _fallback_intent(query: str, previous_intent: dict) -> dict:
        return {
            "category": "banking",
            "intent_type": "product_info",
            "product_type": "credit_card",
            "banking_type": "unknown",
            "specific_product": "",
            "specific_features": [],
            "search_dimension": "relevance",
            "needs_clarification": True,
            "clarification_question": "Could you tell me more about what you're looking for?",
            "customer_age": None,
            "customer_income": None,
            "customer_tenure_months": None,
        }
