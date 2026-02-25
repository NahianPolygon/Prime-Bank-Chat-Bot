"""Simplified chatbot pipeline — 3 focused LLM calls instead of CrewAI agents."""

import requests
import re
import json


# Eligibility conversation configuration
ELIGIBILITY_REQUIRED = ['age', 'employment', 'tenure', 'income', 'etin']
ELIGIBILITY_OPTIONAL = ['credit_history']


class SessionState:
    """Tracks conversation state across turns."""
    def __init__(self):
        self.products_text = None
        self.product_names = []
        self.intent = {}
        
        # Eligibility multi-turn conversation
        self.eligibility_active = False
        self.eligibility_chat = []
        self.eligibility_collected = {}
        self.eligibility_product = None

    def has_products(self):
        return bool(self.products_text)

    def reset_products(self):
        self.products_text = None
        self.product_names = []

    def reset_eligibility(self):
        self.eligibility_active = False
        self.eligibility_chat = []
        self.eligibility_collected = {}
        self.eligibility_product = None


class Pipeline:
    """Main chatbot pipeline with direct Ollama calls and vector search."""

    def __init__(self, vector_db=None):
        self.vector_db = vector_db
        self.sessions = {}

    def _get_state(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def rag_respond(self, query: str, intent_type: str, intent: dict,
                    customer_profile: str, state: SessionState, stream: bool = False):
        """
        Single LLM call combining retrieval, reasoning, and formatting.
        Returns (response_text, retrieved_products_text)
        """
        if not self.vector_db:
            return "Vector DB not initialized", ""
        
        # Build search query from intent
        search_terms = [
            intent.get('tier', ''),
            intent.get('product_type', ''),
            intent.get('banking_type', ''),
            intent.get('use_case', '')
        ]
        search_query = " ".join(filter(None, search_terms)).strip() or query

        # Build metadata filters for the vector DB call
        where = {}
        if intent.get('banking_type') not in ('unknown', ''):
            where['banking_type'] = intent.get('banking_type')
        if intent.get('tier') not in ('unknown', ''):
            where['tier'] = intent.get('tier')
        if intent.get('product_type') not in ('unknown', 'general', ''):
            where['product_type'] = intent.get('product_type')

        print(f"🔍 Vector search: {search_query}  filters: {where or None}")
        search_results = self.vector_db.search(search_query, top_k=3, filters=where or None)

        products_text = "\n\n---\n\n".join([
            f"**{r['metadata'].get('product_name', 'Product')}** ({r['metadata'].get('section', 'Info')})\n{r['content']}"
            for r in (search_results or [])
        ]) if search_results else "No matching products found."

        state.product_names = [
            r['metadata'].get('product_name', 'Product')
            for r in (search_results or [])
        ]

        # Build a focused system prompt based on intent
        system = self._build_rag_system_prompt(intent_type)

        user_msg = f"""PRODUCT DATA:
{products_text}

CUSTOMER QUERY: {query}"""

        if customer_profile:
            user_msg += f"\n\nCUSTOMER PROFILE: {customer_profile}"
        if intent.get('banking_type') not in ('unknown', ''):
            user_msg += f"\nBANKING PREFERENCE: {intent['banking_type']}"
        if intent.get('tier') not in ('unknown', ''):
            user_msg += f"\nPREFERRED TIER: {intent['tier']}"

        if stream:
            # return a generator for streaming LLM output plus the products_text
            return self._ollama_stream(system=system, user=user_msg, temperature=0.2, max_tokens=400), products_text

        response = self._ollama_call(system=system, user=user_msg, temperature=0.2, max_tokens=400)
        return response or "I couldn't generate a response. Please try again.", products_text

    def _ollama_stream(self, system: str, user: str, temperature: float = 0.1, max_tokens: int = 150):
        """Stream response from Ollama chat API as a generator of text chunks.

        Yields raw text chunks (not SSE-formatted). Caller wraps into SSE or websocket.
        """
        try:
            with requests.post(
                "http://ollama:11434/api/chat",
                json={
                    "model": "qwen3:1.7b",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    "stream": True,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                    "think": False
                },
                stream=True,
                timeout=120
            ) as resp:
                resp.raise_for_status()
                # iterate over streaming lines; each line is expected to be JSON
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    try:
                        payload = json.loads(line)
                        # Ollama streaming may include 'message' or 'response' fragments
                        text = ""
                        if isinstance(payload, dict):
                            # try different fields
                            if 'message' in payload and isinstance(payload['message'], dict):
                                text = payload['message'].get('content', '')
                            elif 'response' in payload:
                                text = payload.get('response', '')
                        if text:
                            yield text
                            continue
                    except Exception:
                        # not JSON — yield raw line
                        yield line
                # finished
                return
        except Exception as e:
            yield f"[stream-error] {e}"
            return

    def _build_rag_system_prompt(self, intent_type: str) -> str:
        prompts = {
            'product_info': (
                "You are a Prime Bank assistant. Using ONLY the product data provided:\n"
                "1. Recommend the best matching product\n2. List top 3 benefits\n3. State credit limit and key fees\n4. Give 2 next steps to apply\nMaximum 150 words."
            ),
            'eligibility_check': (
                "You are a Prime Bank eligibility analyst. Using the product requirements AND customer profile:\n"
                "1. State verdict: ✅ Eligible / ⚠️ Likely Eligible / ❌ Not Currently Eligible\n"
                "2. Give reason in 1 sentence\n3. List required documents\n4. Give 3 next steps\nMaximum 200 words."
            ),
            'feature_query': (
                "You are a Prime Bank assistant. Answer the specific question using ONLY the product data provided.\n"
                "Be concise and precise. Maximum 150 words."
            ),
            'comparison': (
                "You are a Prime Bank analyst. Compare the products provided.\n"
                "Format: Feature | Product A | Product B\nThen give a 2-sentence recommendation.\nMaximum 250 words."
            ),
        }
        return prompts.get(intent_type, prompts['product_info'])

    # NOTE: old full-history extractor removed — we now extract only from the
    # current user message to avoid duplicate LLM calls and improve reliability.

    def _extract_from_message(self, user_message: str, already_collected: dict) -> dict:
        """
        Extract ALL eligibility fields from a single user message.
        Handles: single answer, multiple answers at once, out-of-order answers.
        Only extracts fields not already confirmed.
        """
        if not user_message:
            return {}

        known_summary = (
            ", ".join(f"{k}={v}" for k, v in already_collected.items())
            or "nothing yet"
        )

        raw = self._ollama_call(
            system=("You are a data extractor. Output ONLY the exact 6 lines shown. No explanation."),
            user=f"""Extract eligibility fields from this message.
Already confirmed (skip these): {known_summary}

MESSAGE: "{user_message}"

RULES:
- AGE: number only. "I'm 28", "28 years old" → 28. Else → unknown
- EMPLOYMENT: "engineer","developer","manager","employee","salaried" → salaried | "freelancer","contractor" → self_employed | "business owner","entrepreneur","founder" → business_owner | "student" → student | else → unknown
- TENURE: duration. "3 years","since 2021","2 years 6 months" → as stated. Else → unknown
- INCOME: amount. "80k","80,000","1.5 lakh","eighty thousand taka" → normalize to number + BDT. Else → unknown
- ETIN: "yes","have it","yeah","i do" → yes | "no","don't have","nope" → no | else → unknown
- CREDIT_HISTORY: "yes","used before","have loans" → yes | "no","never","first time" → no | else → unknown

Output EXACTLY these 6 lines:
AGE: [value or unknown]
EMPLOYMENT: [value or unknown]
TENURE: [value or unknown]
INCOME: [value or unknown]
ETIN: [value or unknown]
CREDIT_HISTORY: [value or unknown]""",
            temperature=0.0,
            max_tokens=80
        )

        extracted = {}
        for line in (raw or "").strip().split('\n'):
            if ':' in line:
                k, _, v = line.partition(':')
                key = k.strip().upper()
                val = v.strip().lower()
                mapping = {
                    'AGE': 'age', 'EMPLOYMENT': 'employment', 'TENURE': 'tenure',
                    'INCOME': 'income', 'ETIN': 'etin', 'CREDIT_HISTORY': 'credit_history'
                }
                if key in mapping and val and val != 'unknown':
                    field = mapping[key]
                    if field not in already_collected:
                        extracted[field] = val
                        print(f"✓ Extracted {field}: {val}")

        return extracted

    def _get_missing_fields(self, collected: dict) -> list:
        return [f for f in ELIGIBILITY_REQUIRED if f not in collected]

    def _run_eligibility_conversation(self, query: str, state: SessionState) -> dict | None:
        """Multi-turn eligibility Q&A using a single extraction per user turn.

        Returns None when all required fields are collected.
        """
        newly_extracted = {}
        if query:
            state.eligibility_chat.append({'role': 'user', 'content': query})

            # Single extraction call — scans for ALL fields in this message
            newly_extracted = self._extract_from_message(query, state.eligibility_collected)
            if newly_extracted:
                state.eligibility_collected.update(newly_extracted)

        missing = self._get_missing_fields(state.eligibility_collected)
        collected_summary = ", ".join(f"{k}={v}" for k, v in state.eligibility_collected.items()) or "nothing yet"
        print(f"Collected: {state.eligibility_collected} | Missing: {missing}")

        if not missing:
            return None

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in state.eligibility_chat[-6:]
        )

        field_hints = {
            'age': 'their age in years',
            'employment': 'employment type: salaried, self-employed, or business owner',
            'tenure': 'how long they have been in their current job or running their business',
            'income': 'approximate monthly income (salaried) or annual revenue (self-employed) in BDT',
            'etin': 'whether they have a valid E-TIN certificate — yes or no',
            'credit_history': 'whether they have any prior credit card or loan history — yes or no',
        }

        next_field = missing[0]
        user_just_answered = bool(newly_extracted)
        remaining = len(missing)

        response = self._ollama_call(
            system=f"""You are a friendly Prime Bank eligibility assistant.
Checking eligibility for: {state.eligibility_product or 'a banking product'}.
Already confirmed: {collected_summary}.
{remaining} question(s) remaining.
Be warm and conversational. Ask ONE field at a time. Max 2 sentences.
Do not repeat or re-ask anything already confirmed.""",
            user=(f"Conversation so far:\n{history_text}\n\n"
                  f"{'Acknowledge their answer briefly if they just provided information.' if user_just_answered else 'They didn\'t answer clearly — politely re-ask in a different way.'}\n"
                  f"Now ask for: {field_hints.get(next_field, next_field)}"),
            temperature=0.5,
            max_tokens=80
        )

        if not response:
            fallbacks = {
                'age': "Could you tell me your age?",
                'employment': "Are you salaried, self-employed, or a business owner?",
                'tenure': "How long have you been in your current job or business?",
                'income': "What's your approximate monthly income (or annual revenue if self-employed)?",
                'etin': "Do you have a valid E-TIN certificate? (yes/no)",
                'credit_history': "Have you used a credit card or loan before? (yes/no)",
            }
            response = fallbacks.get(next_field, f"Could you share your {next_field}?")

        state.eligibility_chat.append({'role': 'assistant', 'content': response})

        return {
            'response': response,
            'agent_chain': ['Eligibility Conversation'],
            'products_found': [],
            'needs_clarification': True,
            'detected_intent': state.intent
        }

    def _format_eligibility_profile(self, collected: dict, intent: dict) -> str:
        parts = []
        label_map = {
            'age': 'Age', 'employment': 'Employment Type', 'tenure': 'Job/Business Tenure',
            'income': 'Monthly Income', 'etin': 'Has E-TIN', 'credit_history': 'Credit History',
        }
        
        for key, label in label_map.items():
            val = collected.get(key)
            if val:
                parts.append(f"{label}: {val}")
        
        if intent.get('banking_type') not in ('unknown', ''):
            parts.append(f"Banking Preference: {intent['banking_type']}")
        if intent.get('tier') not in ('unknown', ''):
            parts.append(f"Preferred Tier: {intent['tier']}")
        
        return "; ".join(parts) if parts else "No profile data collected"

    def run(self, query: str, customer_info: dict = None,
            conversation_history: list = None, session_id: str = None, stream: bool = False):
        """Run pipeline with focused LLM calls."""
        
        history = conversation_history or []
        session_id = session_id or "default"
        state = self._get_state(session_id)

        # ① Eligibility flow intercept
        if state.eligibility_active:
            result = self._run_eligibility_conversation(query, state)
            
            if result:
                return result
            
            print(f"✅ Eligibility info complete: {state.eligibility_collected}")
            profile = self._format_eligibility_profile(state.eligibility_collected, state.intent)
            
            response, retrieved_products = self.rag_respond(
                query=f"Check eligibility for {state.eligibility_product}",
                intent_type='eligibility_check',
                intent=state.intent,
                customer_profile=profile,
                state=state
            )
            
            if retrieved_products:
                state.products_text = retrieved_products
            state.reset_eligibility()
            
            return {
                'response': response,
                'agent_chain': ['Eligibility Conversation', 'RAG Responder'],
                'products_found': state.product_names,
                'needs_clarification': False,
                'detected_intent': state.intent
            }

        # ② Intent detection
        intent = self._detect_intent(query, history, previous_intent=state.intent)

        # ③ Instant responses
        if intent.get('intent_type') == 'greeting':
            return {
                'response': "Hello! 👋 Welcome to Prime Bank. How can I help you today?",
                'agent_chain': [],
                'products_found': [],
                'needs_clarification': False,
                'detected_intent': intent
            }

        # ④ Small talk — use LLM to generate a short, friendly redirect
        if intent.get('intent_type') == 'small_talk':
            small_talk_reply = self._ollama_call(
                system=("You are a friendly Prime Bank assistant. Reply in 1-2 sentences, be warm, "
                        "and gently redirect to banking topics (cards, loans, accounts)."),
                user=(f"Customer said: \"{query}\". Reply briefly (1-2 sentences), then offer: "
                      "'Would you like help with cards, loans, or accounts?'"),
                temperature=0.7,
                max_tokens=60
            )
            return {
                'response': small_talk_reply or "I'm here to help with your banking needs! Would you like help with cards, loans, or accounts?",
                'agent_chain': [],
                'products_found': [],
                'needs_clarification': False,
                'detected_intent': intent
            }

        # ⑤ Comparison needs criteria
        if intent.get('intent_type') == 'comparison_needs_criteria':
            criteria_reply = self._ollama_call(
                system=("You are a helpful banking assistant. In 1-2 sentences, ask a focused question "
                        "to elicit comparison criteria (e.g., travel, dining, international usage, insurance)."),
                user=(f"Customer expressed they want to compare {intent.get('product_type','products')}. "
                      "Ask which of these matters most: travel, dining, international use, or insurance?"),
                temperature=0.6,
                max_tokens=60
            )
            return {
                'response': criteria_reply or "What matters most to you — travel perks, dining benefits, international use, or insurance coverage?",
                'agent_chain': [],
                'products_found': [],
                'needs_clarification': True,
                'detected_intent': intent
            }

        # Filter change check
        if state.has_products() and self._filters_changed(intent, state.intent):
            print("⚠️  Filters changed — resetting cached products")
            state.reset_products()

        # Clarification needed?
        if intent.get('needs_clarification'):
            state.intent = intent
            questions = self._generate_clarifying_questions(
                detected_product=intent.get('product_type', 'general'),
                detected_info=intent,
                history=history
            )
            return {
                'response': questions,
                'agent_chain': [],
                'products_found': [],
                'needs_clarification': True,
                'detected_intent': intent
            }

        intent_type = intent.get('intent_type', 'product_info')

        # ⑥ Start eligibility flow
        if intent_type == 'eligibility_check':
            state.intent = intent
            state.eligibility_active = True
            state.eligibility_product = (
                f"{intent.get('tier', '')} {intent.get('product_type', 'credit card')} "
                f"({intent.get('banking_type', 'conventional')} banking)"
            ).strip()
            
            opening = self._ollama_call(
                system="Friendly Prime Bank assistant. 1-2 sentences max.",
                user=f"Customer wants to check eligibility for: {state.eligibility_product}. Warmly acknowledge and ask their age.",
                temperature=0.6,
                max_tokens=50
            )
            opening = opening or f"Happy to check your eligibility for the {state.eligibility_product}! Could you start by telling me your age?"
            
            state.eligibility_chat.append({'role': 'assistant', 'content': opening})
            
            return {
                'response': opening,
                'agent_chain': ['Eligibility Conversation'],
                'products_found': [],
                'needs_clarification': True,
                'detected_intent': intent
            }

        # ⑦ Everything else: single RAG call
        state.intent = intent
        profile = self._format_customer_profile(customer_info) if customer_info else ""

        # If streaming requested, propagate to rag_respond and return generator
        response, retrieved_products = None, None
        if stream:
            rag_result = self.rag_respond(
                query=query,
                intent_type=intent_type,
                intent=intent,
                customer_profile=profile,
                state=state,
                stream=True
            )
            # rag_result is (generator, products_text)
            return {
                'stream_generator': rag_result[0],
                'products_text': rag_result[1],
                'agent_chain': ['RAG Responder'],
                'detected_intent': intent
            }

        response, retrieved_products = self.rag_respond(
            query=query,
            intent_type=intent_type,
            intent=intent,
            customer_profile=profile,
            state=state
        )

        if retrieved_products:
            state.products_text = retrieved_products

        return {
            'response': response,
            'agent_chain': ['RAG Responder'],
            'products_found': state.product_names,
            'needs_clarification': False,
            'detected_intent': intent
        }

    def _filters_changed(self, new_intent: dict, old_intent: dict) -> bool:
        if not old_intent:
            return False
        for key in ('product_type', 'banking_type', 'tier'):
            old_val = old_intent.get(key, 'unknown')
            new_val = new_intent.get(key, 'unknown')
            both_known = old_val not in ('unknown', 'general', '') and new_val not in ('unknown', 'general', '')
            if both_known and old_val != new_val:
                print(f"Filter changed: {key}: {old_val} → {new_val}")
                return True
        return False

    def _ollama_call(self, system: str, user: str, temperature: float = 0.1, max_tokens: int = 150) -> str:
        try:
            response = requests.post(
                "http://ollama:11434/api/chat",
                json={
                    "model": "qwen3:1.7b",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ],
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens, "stop": ["\n\n\n"]},
                    "think": False
                },
                timeout=60
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "").strip()
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            print(f"Ollama: [{content[:150]}]")
            return content
        except Exception as e:
            print(f"Ollama error: {e}")
            return ""

    def _detect_intent(self, query: str, history: list, previous_intent: dict = None) -> dict:
        history_text = ""
        if history:
            for msg in history[-6:]:
                history_text += f"{msg['role'].upper()}: {msg['content']}\n"

        prev = previous_intent or {}
        prev_product = prev.get('product_type', 'general')
        prev_banking = prev.get('banking_type', 'unknown')
        prev_tier = prev.get('tier', 'unknown')
        prev_use_case = prev.get('use_case', 'unknown')
        prev_employment = prev.get('employment', 'unknown')

        raw = self._ollama_call(
            system="You are an intent extraction parser. Extract user intent fields and output EXACTLY 7 lines. Be precise and literal with KEYWORD MATCHING.",
            user=f"""TASK: Extract intent fields from this message using exact keyword matching.

MESSAGE: "{query}"
{f'CONVERSATION HISTORY:{chr(10)}{history_text}' if history_text else ''}

EXTRACTION RULES - Apply these in order, check the EXACT MESSAGE TEXT:

STEP 1: TIER - Search for these EXACT words in message:
- If contains "gold" → TIER: gold
- Else if contains "platinum" → TIER: platinum  
- Else if contains "silver" → TIER: silver
- Else → TIER: unknown

STEP 2: BANKING_TYPE - Search for these EXACT words:
- If contains "conventional" → BANKING_TYPE: conventional
- Else if contains "islami" OR "islamic" → BANKING_TYPE: islami
- Else → BANKING_TYPE: unknown

STEP 3: PRODUCT_TYPE - Search for these EXACT words:
- If contains "credit" → PRODUCT_TYPE: credit_card
- Else if contains "debit" → PRODUCT_TYPE: debit_card
- Else if contains "loan" → PRODUCT_TYPE: loan
- Else if contains "savings" → PRODUCT_TYPE: savings_account
- Else → PRODUCT_TYPE: general

STEP 4: USE_CASE - Search for these EXACT words:
- If contains "travel" → USE_CASE: travel
- Else if contains "shopping" → USE_CASE: shopping
- Else if contains "dining" → USE_CASE: dining
- Else if contains "business" → USE_CASE: business
- Else → USE_CASE: unknown

STEP 5: EMPLOYMENT - Search for EXACT job titles:
- If contains "salaried", "engineer", "employee" → EMPLOYMENT: salaried
- Else if contains "freelancer" → EMPLOYMENT: self_employed
- Else if contains "business owner" → EMPLOYMENT: business_owner
- Else → EMPLOYMENT: unknown

STEP 6: INTENT_TYPE - Search for EXACT intent keywords:
- If contains "eligible", "qualify", "requirements" → INTENT_TYPE: eligibility_check
- Else if contains "compare", "versus", "vs" → INTENT_TYPE: comparison
- Else if contains "feature", "benefit" → INTENT_TYPE: feature_query
- Else → INTENT_TYPE: product_info

OUTPUT - Exactly these 7 lines:
QUERY_TYPE: banking
PRODUCT_TYPE: [your extracted value]
BANKING_TYPE: [your extracted value]
TIER: [your extracted value]
USE_CASE: [your extracted value]
EMPLOYMENT: [your extracted value]
INTENT_TYPE: [your extracted value]""",
            temperature=0.0,
            max_tokens=100
        )

        if not raw:
            return {
                'product_type': prev_product,
                'banking_type': prev_banking,
                'tier': prev_tier,
                'use_case': prev_use_case,
                'employment': prev_employment,
                'intent_type': 'product_info',
                'needs_clarification': False if prev_product != 'general' else True
            }

        parsed = self._parse_intent(raw, query)
        
        result = {
            'product_type': parsed.get('product_type') if parsed.get('product_type') != 'unknown' else prev_product,
            'banking_type': parsed.get('banking_type') if parsed.get('banking_type') != 'unknown' else prev_banking,
            'tier': parsed.get('tier') if parsed.get('tier') != 'unknown' else prev_tier,
            'use_case': parsed.get('use_case') if parsed.get('use_case') != 'unknown' else prev_use_case,
            'employment': parsed.get('employment') if parsed.get('employment') != 'unknown' else prev_employment,
            'intent_type': parsed.get('intent_type', 'product_info'),
        }
        
        product_known = result['product_type'] not in ('general', 'unknown', '')
        banking_known = result['banking_type'] not in ('unknown', '')
        tier_known = result['tier'] not in ('unknown', '')
        use_case_known = result['use_case'] not in ('unknown', '')
        employment_known = result['employment'] not in ('unknown', '')
        
        intent_type = result['intent_type']
        
        if intent_type == 'eligibility_check':
            has_enough = product_known
        elif intent_type == 'comparison':
            has_enough = product_known and banking_known and tier_known
        elif result['product_type'] in ('credit_card', 'loan'):
            has_enough = product_known and banking_known and tier_known and employment_known
        else:
            has_enough = product_known and banking_known and tier_known and use_case_known
        
        result['needs_clarification'] = not has_enough
        
        print(f"Intent: {result['product_type']} {result['banking_type']} {result['tier']} {result['intent_type']}")
        
        return result

    def _parse_intent(self, raw: str, query: str = "") -> dict:
        parsed = {}
        for line in str(raw).strip().split('\n'):
            if ':' in line:
                k, _, v = line.partition(':')
                parsed[k.strip().upper()] = v.strip().lower()

        product_type = parsed.get('PRODUCT_TYPE', 'general')
        banking_type = parsed.get('BANKING_TYPE', 'unknown')
        if banking_type == 'islamic':
            banking_type = 'islami'
        tier = parsed.get('TIER', 'unknown')
        
        VALID_BANKING_TYPES = ('conventional', 'islami', 'unknown', '')
        if banking_type not in VALID_BANKING_TYPES:
            banking_type = 'unknown'
        
        VALID_TIERS = ('gold', 'platinum', 'silver', 'unknown', '')
        if tier not in VALID_TIERS:
            tier = 'unknown'
        
        VALID_PRODUCTS = ('credit_card', 'debit_card', 'loan', 'savings_account', 'general', 'unknown', '')
        if product_type not in VALID_PRODUCTS:
            product_type = 'general'
        
        use_case = parsed.get('USE_CASE', 'unknown')
        employment = parsed.get('EMPLOYMENT', 'unknown')
        intent_type = parsed.get('INTENT_TYPE', 'product_info')

        if intent_type not in ('product_info', 'comparison', 'eligibility_check', 'feature_query'):
            intent_type = 'product_info'

        if 'greeting' in parsed.get('QUERY_TYPE', ''):
            return {
                'product_type': 'general', 'banking_type': 'unknown', 'tier': 'unknown',
                'use_case': 'unknown', 'employment': 'unknown',
                'intent_type': 'greeting', 'needs_clarification': False
            }
        if 'small' in parsed.get('QUERY_TYPE', ''):
            return {
                'product_type': 'general', 'banking_type': 'unknown', 'tier': 'unknown',
                'use_case': 'unknown', 'employment': 'unknown',
                'intent_type': 'small_talk', 'needs_clarification': False
            }

        product_known = product_type not in ('general', 'unknown', '')
        banking_known = banking_type not in ('unknown', '')
        tier_known = tier not in ('unknown', '')
        use_case_known = use_case not in ('unknown', '')
        employment_known = employment not in ('unknown', '')

        if product_type in ('credit_card', 'loan'):
            has_enough = product_known and banking_known and tier_known and employment_known
        else:
            has_enough = product_known and banking_known and tier_known and use_case_known

        comparison_criteria_known = use_case_known or employment_known
        if intent_type == 'comparison' and not comparison_criteria_known:
            intent_type = 'comparison_needs_criteria'
            has_enough = False

        return {
            'product_type': product_type, 'banking_type': banking_type,
            'tier': tier, 'use_case': use_case, 'employment': employment,
            'intent_type': intent_type, 'needs_clarification': not has_enough
        }

    def _generate_clarifying_questions(self, detected_product: str, detected_info: dict, history: list) -> str:
        missing = []
        if detected_info.get('banking_type') == 'unknown':
            missing.append("Islamic or Conventional banking")
        if detected_info.get('use_case') == 'unknown':
            missing.append("main purpose: travel, shopping, dining, or business")
        if detected_info.get('tier') == 'unknown':
            missing.append("preferred tier: Gold, Platinum, or Silver")
        if detected_info.get('employment') == 'unknown' and detected_product in ('credit_card', 'loan'):
            missing.append("employment type: salaried, self-employed, or business owner")

        if not missing:
            return self._fallback_questions(detected_product, detected_info)

        # Provide a richer clarifying question using the LLM with context
        history_text = "\n".join(h['content'] for h in (history or [])[-4:])
        user_prompt = (
            f"You are a helpful banking assistant. The customer is looking for a {detected_product.replace('_',' ')}. "
            f"We are missing: {', '.join(missing)}. Conversation so far:\n{history_text}\n\n"
            f"Ask one concise, polite question to collect the top missing item. Keep it to one sentence."
        )

        raw = self._ollama_call(
            system="Polite bank assistant. 1 sentence.",
            user=user_prompt,
            temperature=0.6,
            max_tokens=40
        )
        return raw if raw else self._fallback_questions(detected_product, detected_info)

    def _fallback_questions(self, product_type: str, detected_info: dict) -> str:
        q = [f"I'd love to help you find the right {product_type.replace('_', ' ')}! "]
        if detected_info.get('banking_type') == 'unknown':
            q.append("Do you prefer Islamic (Shariah-compliant) or Conventional banking?")
        if detected_info.get('use_case') == 'unknown':
            q.append("What will you mainly use it for — travel, shopping, dining, or business?")
        if detected_info.get('tier') == 'unknown':
            q.append("Are you interested in Gold, Platinum, or Silver tier?")
        return " ".join(q)

    @staticmethod
    def _format_customer_profile(info: dict) -> str:
        parts = []
        if 'employment' in info and info['employment']:
            parts.append(f"Employment: {info['employment']}")
        if 'income' in info and info['income']:
            parts.append(f"Monthly Income: {info['income']}")
        if 'credit_score' in info and info['credit_score']:
            parts.append(f"Credit Score: {info['credit_score']}")
        return "; ".join(parts) if parts else ""


__all__ = ["Pipeline", "SessionState"]
