"""CrewAI pipeline — fully dynamic agent selection based on session state."""

import requests
import re
from crewai import Crew
from agents.agents import BankAgents, get_ollama_llm
from agents.tasks import BankTasks


# Eligibility conversation configuration
ELIGIBILITY_REQUIRED = ['age', 'employment', 'tenure', 'income', 'etin']
ELIGIBILITY_OPTIONAL = ['credit_history']  # Nice to have but not blocking


class SessionState:
    """Tracks what has been done in a session."""
    def __init__(self):
        self.products_text = None        # Raw product retrieval output
        self.product_names = []          # List of product names retrieved
        self.comparison_done = False
        self.eligibility_done = False
        self.intent = {}                 # Last known intent (banking_type, tier, etc.)
        
        # Eligibility multi-turn state
        self.eligibility_active = False          # Are we in eligibility flow?
        self.eligibility_chat = []               # Conversation history for this flow
        self.eligibility_collected = {}          # Extracted answers so far
        self.eligibility_product = None          # Which product they're asking about

    def has_products(self):
        return bool(self.products_text)

    def reset_products(self):
        """Call when filters change — need fresh retrieval."""
        self.products_text = None
        self.product_names = []
        self.comparison_done = False
        self.eligibility_done = False

    def reset_eligibility(self):
        """Reset eligibility flow state after assessment."""
        self.eligibility_active = False
        self.eligibility_chat = []
        self.eligibility_collected = {}
        self.eligibility_product = None


class BankChatbotCrew:
    """Runs only the agents needed based on session state."""

    def __init__(self):
        self.llm = get_ollama_llm()
        self.agents_factory = BankAgents()
        self.tasks_factory = BankTasks()

    def run_agents(self, query: str, intent_type: str,
                   state: SessionState, customer_profile: str = "") -> tuple:
        """
        Dynamically select and run agents.
        Returns (response_text, retrieved_products_text)
        """
        agents = []
        tasks = []
        retrieved_products = None

        needs_retrieval = (
            not state.has_products() or
            intent_type == 'product_info' or
            intent_type == 'eligibility_check' or
            (intent_type == 'comparison' and not state.has_products())
        )

        needs_comparison = (
            intent_type == 'comparison'
        )

        needs_eligibility = (
            intent_type == 'eligibility_check'
        )

        print(f"\n🎯 intent={intent_type} | needs_retrieval={needs_retrieval} | "
              f"needs_comparison={needs_comparison} | needs_eligibility={needs_eligibility}")

        # --- RETRIEVAL AGENT ---
        if needs_retrieval:
            retriever = self.agents_factory.product_retriever_agent()
            # For comparisons, explicitly ask to retrieve multiple banking types
            retrieval_context = query
            if needs_comparison:
                retrieval_context += "\n\n⚠️ COMPARISON REQUEST: User wants to compare products. Search for BOTH Islamic and Conventional versions if user mentions both, or explicitly request both variants."
            retrieval_task = self.tasks_factory.retrieve_products_task(
                retriever, intent_type, retrieval_context
            )
            agents.append(retriever)
            tasks.append(retrieval_task)

        # --- COMPARISON AGENT ---
        if needs_comparison and state.has_products():
            comparator = self.agents_factory.feature_comparator_agent()
            products_input = state.products_text or query
            comparison_task = self.tasks_factory.compare_features_task(
                comparator, products_input
            )
            agents.append(comparator)
            tasks.append(comparison_task)

        # --- ELIGIBILITY AGENT ---
        # Run if eligibility check is requested AND either:
        # 1. Products already cached, OR
        # 2. Retrieval is being triggered now (will have products after)
        if needs_eligibility and (state.has_products() or needs_retrieval):
            eligibility = self.agents_factory.eligibility_analyzer_agent()
            products_input = state.products_text or query
            eligibility_task = self.tasks_factory.analyze_eligibility_task(
                eligibility, products_input, customer_profile or "General"
            )
            agents.append(eligibility)
            tasks.append(eligibility_task)

        # --- FORMATTER AGENT (always last) ---
        formatter = self.agents_factory.response_formatter_agent()
        formatting_task = self.tasks_factory.format_response_task(
            formatter,
            products_info=state.products_text or "from_retrieval",
            eligibility_info="from_previous" if needs_eligibility else "not_requested",
            comparison_info="from_previous" if needs_comparison else "not_requested",
            original_query=query
        )
        agents.append(formatter)
        tasks.append(formatting_task)

        print(f"Running {len(agents)} agents: {[a.role for a in agents]}\n")

        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            max_iter=3,  # Allow multiple tool calls for small models
            memory=False,
        )
        result = crew.kickoff()
        response = str(result)

        # Extract retrieval output for caching
        if needs_retrieval and tasks:
            retrieval_task_obj = tasks[0]
            retrieved_products = str(getattr(retrieval_task_obj, 'output', '')) or response

        return response, retrieved_products


class CrewPipeline:
    """Main pipeline — fully dynamic based on session state."""

    def __init__(self):
        self.crew = BankChatbotCrew()
        self.llm = get_ollama_llm()
        self.sessions = {}  # session_id -> SessionState

    def _get_state(self, session_id: str) -> SessionState:
        """Get or create session state."""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def _extract_eligibility_info(self, chat: list) -> dict:
        """Extract structured eligibility info from conversation history."""
        if not chat:
            return {}
        
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in chat
        )
        
        raw = self._ollama_call(
            system="Extract data from conversation. Output ONLY the exact format shown. No extra text.",
            user=f"""Extract eligibility information from this conversation.

CONVERSATION:
{history_text}

Output EXACTLY these lines (use "unknown" if not mentioned):
AGE: [number only, e.g. 28, or unknown]
EMPLOYMENT: [salaried/self_employed/business_owner/student or unknown]
TENURE: [e.g. "2 years" / "8 months" or unknown]
INCOME: [amount in BDT or unknown]
ETIN: [yes/no or unknown]
CREDIT_HISTORY: [yes/no or unknown]""",
            temperature=0.0,
            max_tokens=100
        )
        
        result = {}
        for line in raw.strip().split('\n'):
            if ':' in line:
                k, _, v = line.partition(':')
                key = k.strip().upper()
                val = v.strip().lower()
                mapping = {
                    'AGE': 'age', 'EMPLOYMENT': 'employment', 'TENURE': 'tenure',
                    'INCOME': 'income', 'ETIN': 'etin', 'CREDIT_HISTORY': 'credit_history'
                }
                if key in mapping and val != 'unknown':
                    result[mapping[key]] = val
        
        return result

    def _get_missing_fields(self, collected: dict) -> list:
        """Return list of required fields not yet collected."""
        return [f for f in ELIGIBILITY_REQUIRED if f not in collected]

    def _run_eligibility_conversation(self, query: str, state: SessionState) -> dict | None:
        """
        Conduct natural multi-turn eligibility conversation.
        Returns response dict if still collecting, None if ready to assess.
        """
        # Add user message to eligibility chat
        if query:
            state.eligibility_chat.append({'role': 'user', 'content': query})
        
        # Extract what we know so far
        state.eligibility_collected = self._extract_eligibility_info(state.eligibility_chat)
        missing = self._get_missing_fields(state.eligibility_collected)
        
        print(f"Eligibility collected: {state.eligibility_collected}")
        print(f"Missing fields: {missing}")
        
        if not missing:
            # All required info collected — ready for agent assessment
            return None
        
        # Build conversation history for context
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" 
            for m in state.eligibility_chat[-6:]
        )
        
        # Map field names to human-readable questions
        field_hints = {
            'age': 'their age',
            'employment': 'employment type (salaried, self-employed, or business owner)',
            'tenure': 'how long they have been in their current job or business',
            'income': 'approximate monthly income or annual revenue in BDT',
            'etin': 'whether they have a valid E-TIN certificate (yes or no)',
            'credit_history': 'whether they have prior credit history (loans or cards)',
        }
        
        next_field = missing[0]  # Ask one at a time
        hint = field_hints.get(next_field, next_field)
        
        response = self._ollama_call(
            system=f"""You are a friendly Prime Bank eligibility assistant.
You are collecting information to check if the customer qualifies for: {state.eligibility_product or 'a credit card'}.
Be conversational and warm. Ask for ONE piece of information at a time. Keep it under 2 sentences.""",
            user=f"""Conversation so far:
{history_text}

Now naturally ask for: {hint}
Do not repeat questions already answered. Be friendly and brief.""",
            temperature=0.5,
            max_tokens=80
        )
        
        if not response:
            # Hardcoded fallback
            fallbacks = {
                'age': "Could you please tell me your age?",
                'employment': "Are you salaried, self-employed, or a business owner?",
                'tenure': "How long have you been in your current job or business?",
                'income': "What's your approximate monthly income (or annual revenue if self-employed)?",
                'etin': "Do you have a valid E-TIN certificate? (yes/no)",
                'credit_history': "Do you have any prior credit card or loan history? (yes/no)",
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
        """Format collected answers into a profile string for the agent."""
        parts = []
        
        label_map = {
            'age': 'Age',
            'employment': 'Employment Type',
            'tenure': 'Job/Business Tenure', 
            'income': 'Monthly Income',
            'etin': 'Has E-TIN',
            'credit_history': 'Credit History',
        }
        
        for key, label in label_map.items():
            val = collected.get(key)
            if val:
                parts.append(f"{label}: {val}")
        
        # Also include intent-detected info
        if intent.get('banking_type') not in ('unknown', ''):
            parts.append(f"Banking Preference: {intent['banking_type']}")
        if intent.get('tier') not in ('unknown', ''):
            parts.append(f"Preferred Tier: {intent['tier']}")
        
        return "; ".join(parts) if parts else "No profile data collected"

    def run(self, query: str, customer_info: dict = None,
            conversation_history: list = None, session_id: str = None) -> dict:
        """Run pipeline with dynamic agent selection and product caching."""
        
        history = conversation_history or []
        session_id = session_id or "default"
        state = self._get_state(session_id)

        # --- ELIGIBILITY FLOW: intercept BEFORE intent detection ---
        if state.eligibility_active:
            result = self._run_eligibility_conversation(query, state)
            
            if result:
                # Still collecting info
                return result
            
            # All info collected — run the agent
            print(f"✅ Eligibility info complete: {state.eligibility_collected}")
            profile = self._format_eligibility_profile(
                state.eligibility_collected, state.intent
            )
            enriched_query = (
                f"Customer Query: Check eligibility for {state.eligibility_product}\n"
                f"Customer Profile: {profile}\n"
                f"Product to check: {state.eligibility_product}"
            )
            
            response, retrieved_products = self.crew.run_agents(
                query=enriched_query,
                intent_type='eligibility_check',
                state=state,
                customer_profile=profile
            )
            
            if retrieved_products:
                state.products_text = retrieved_products
            state.eligibility_done = True
            state.reset_eligibility()  # Clean up flow state
            
            return {
                'response': response,
                'agent_chain': ['Eligibility Conversation', 'Product Retriever', 
                              'Eligibility Analyzer', 'Formatter'],
                'products_found': state.product_names,
                'needs_clarification': False,
                'detected_intent': state.intent
            }

        # --- NORMAL FLOW: intent detection ---
        intent = self._detect_intent(query, history, previous_intent=state.intent)

        # Handle greeting
        if intent.get('intent_type') == 'greeting':
            greeting_reply = self._ollama_call(
                system="You are a friendly Prime Bank assistant. Give a warm, brief greeting.",
                user=f'Customer said: "{query}". Greet them warmly and offer to help with banking products in 1-2 sentences.',
                temperature=0.7,
                max_tokens=80
            )
            return {
                'response': greeting_reply or "Hello! 👋 Welcome to Prime Bank. How can I assist you today?",
                'agent_chain': [],
                'products_found': [],
                'needs_clarification': False,
                'detected_intent': intent
            }

        # Handle small talk
        if intent.get('intent_type') == 'small_talk':
            small_talk_reply = self._ollama_call(
                system="You are a Prime Bank assistant. Respond briefly and redirect to banking help.",
                user=f'Customer said: "{query}". Give a short friendly response and gently redirect to banking services.',
                temperature=0.7,
                max_tokens=100
            )
            return {
                'response': small_talk_reply or "I'm here to help with your banking needs! Feel free to ask about our cards, loans, or accounts.",
                'agent_chain': [],
                'products_found': [],
                'needs_clarification': False,
                'detected_intent': intent
            }

        # Handle comparison clarification — need to know what to optimize for
        if intent.get('intent_type') == 'comparison_needs_criteria':
            criteria_reply = self._ollama_call(
                system="Friendly bank assistant. 2 sentences max.",
                user=f"""Customer wants to compare products.
Ask them ONE question: what matters most — travel perks, dining benefits, international use, or insurance coverage?""",
                temperature=0.7,
                max_tokens=80
            )
            return {
                'response': criteria_reply or "To find the best match, what matters most to you — travel perks, dining benefits, international use, or insurance coverage?",
                'agent_chain': ['Intent Detector'],
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
                'agent_chain': ['Intent Detector'],
                'products_found': [],
                'needs_clarification': True,
                'detected_intent': intent
            }

        intent_type = intent.get('intent_type', 'product_info')

        # --- START ELIGIBILITY FLOW ---
        if intent_type == 'eligibility_check':
            state.intent = intent
            state.eligibility_active = True
            state.eligibility_product = (
                f"{intent.get('tier', '')} {intent.get('product_type', 'credit card')} "
                f"({intent.get('banking_type', 'conventional')} banking)"
            ).strip()
            
            # Start conversation with opening message
            opening = self._ollama_call(
                system="Friendly Prime Bank assistant. 1-2 sentences max.",
                user=f"Customer wants to check eligibility for: {state.eligibility_product}. "
                     f"Warmly acknowledge and ask their age to begin the eligibility check.",
                temperature=0.6,
                max_tokens=60
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

        # --- NON-ELIGIBILITY: run agents normally ---
        enriched_query = self._build_enriched_query(query, history, intent, state)
        profile = self._format_customer_profile(customer_info) if customer_info else ""

        response, retrieved_products = self.crew.run_agents(
            query=enriched_query,
            intent_type=intent_type,
            state=state,
            customer_profile=profile
        )

        if retrieved_products:
            state.products_text = retrieved_products
        if intent_type == 'comparison':
            state.comparison_done = True
        state.intent = intent

        return {
            'response': response,
            'agent_chain': self._describe_agents(intent_type, state),
            'products_found': state.product_names,
            'needs_clarification': False,
            'detected_intent': intent
        }

    def _filters_changed(self, new_intent: dict, old_intent: dict) -> bool:
        """Detect if user changed banking type, tier, or product — needs fresh retrieval."""
        if not old_intent:
            return False
        for key in ('product_type', 'banking_type', 'tier'):
            old_val = old_intent.get(key, 'unknown')
            new_val = new_intent.get(key, 'unknown')
            # Only reset if BOTH are known AND they differ
            both_known = old_val not in ('unknown', 'general', '') and new_val not in ('unknown', 'general', '')
            if both_known and old_val != new_val:
                print(f"Filter changed: {key}: {old_val} → {new_val}")
                return True
        return False

    def _describe_agents(self, intent_type: str, state: SessionState) -> list:
        """Describe which agents were executed."""
        agents = []
        if not state.has_products():
            agents.append('Product Retriever')
        if intent_type == 'comparison':
            agents.append('Comparator')
        if intent_type == 'eligibility_check':
            agents.append('Eligibility Analyzer')
        agents.append('Formatter')
        return agents

    def _build_enriched_query(self, query: str, history: list,
                               intent: dict, state: SessionState) -> str:
        """Build enriched query with context, intent, and cached products."""
        parts = [f"Customer Query: {query}"]
        if intent.get('product_type') not in ('general', 'unknown'):
            parts.append(f"Product Interest: {intent['product_type'].replace('_', ' ')}")
        if intent.get('banking_type') not in ('unknown', ''):
            parts.append(f"Banking Type: {intent['banking_type']}")
        if intent.get('tier') not in ('unknown', ''):
            parts.append(f"Tier: {intent['tier']}")
        if intent.get('use_case') not in ('unknown', ''):
            parts.append(f"Use Case: {intent['use_case']}")
        if intent.get('employment') not in ('unknown', ''):
            parts.append(f"Employment: {intent['employment']}")

        # Inject cached products so agents don't need to re-retrieve
        if state.has_products():
            parts.append(f"\nPreviously Retrieved Products:\n{state.products_text[:1000]}")

        if history:
            parts.append("\nConversation context:")
            for msg in history[-6:]:
                parts.append(f"  {msg['role'].upper()}: {msg['content']}")

        return "\n".join(parts)

    def _ollama_call(self, system: str, user: str,
                     temperature: float = 0.1, max_tokens: int = 150) -> str:
        """Call Ollama API directly."""
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
            print(f"Ollama raw: [{content[:200]}]")
            return content
        except Exception as e:
            print(f"Ollama call error: {e}")
            return ""

    def _detect_intent(self, query: str, history: list, previous_intent: dict = None) -> dict:
        """Single LLM call to classify and extract all intent fields."""
        history_text = ""
        if history:
            for msg in history[-6:]:
                history_text += f"{msg['role'].upper()}: {msg['content']}\n"

        # Get previously confirmed values for fallback
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
- If contains "gold" (including "gold card", "visa gold") → TIER: gold
- Else if contains "platinum" (including "platinum card") → TIER: platinum  
- Else if contains "silver" (including "silver card") → TIER: silver
- Else → TIER: unknown

STEP 2: BANKING_TYPE - Search for these EXACT words:
- If contains "conventional" → BANKING_TYPE: conventional
- Else if contains "islami" OR "islamic" → BANKING_TYPE: islami
- Else → BANKING_TYPE: unknown

STEP 3: PRODUCT_TYPE - Search for these EXACT words:
- If contains "credit card" OR "credit" → PRODUCT_TYPE: credit_card
- Else if contains "debit card" OR "debit" → PRODUCT_TYPE: debit_card
- Else if contains "loan" → PRODUCT_TYPE: loan
- Else if contains "savings" → PRODUCT_TYPE: savings_account
- Else → PRODUCT_TYPE: general

STEP 4: USE_CASE - Search for these EXACT words:
- If contains "travel" → USE_CASE: travel
- Else if contains "shopping" → USE_CASE: shopping
- Else if contains "dining" → USE_CASE: dining
- Else if contains "business" → USE_CASE: business
- Else if contains "lifestyle" → USE_CASE: lifestyle
- Else if contains "reward" → USE_CASE: rewards
- Else → USE_CASE: unknown

STEP 5: EMPLOYMENT - Search for EXACT job titles:
- If contains "engineer", "developer", "consultant", "employee", "manager", "officer", "salaried" → EMPLOYMENT: salaried
- Else if contains "freelancer", "contractor" → EMPLOYMENT: self_employed
- Else if contains "business owner", "entrepreneur", "founder" → EMPLOYMENT: business_owner
- Else if contains "student" → EMPLOYMENT: student
- Else → EMPLOYMENT: unknown

STEP 6: INTENT_TYPE - Search for EXACT intent keywords (check in this order):
- If contains "eligible", "qualify", "qualify for", "requirements", "can i apply", "do i meet" → INTENT_TYPE: eligibility_check
- Else if contains "compare", "versus", "vs", "which is better", "difference" → INTENT_TYPE: comparison
- Else if contains "feature", "benefit", "how does", "tell me about" → INTENT_TYPE: feature_query
- Else (contains "want", "need", "looking for", "recommend") → INTENT_TYPE: product_info

OUTPUT - Exactly these 7 lines, one per line:
QUERY_TYPE: banking
PRODUCT_TYPE: [your extracted value]
BANKING_TYPE: [your extracted value]
TIER: [your extracted value]
USE_CASE: [your extracted value]
EMPLOYMENT: [your extracted value]
INTENT_TYPE: [your extracted value]

IMPORTANT: For message "{query}" extract ONLY what you find in the message text itself.""",
            temperature=0.0,
            max_tokens=100
        )

        if not raw:
            # Return previous intent on failure — don't lose context
            return {
                'product_type': prev_product,
                'banking_type': prev_banking,
                'tier': prev_tier,
                'use_case': prev_use_case,
                'employment': prev_employment,
                'intent_type': 'product_info',
                'needs_clarification': False if prev_product != 'general' else True
            }

        # Parse extracted values
        parsed = self._parse_intent(raw, query)
        
        # Now apply persistence: fill in missing values from previous intent
        result = {
            'product_type': parsed.get('product_type') if parsed.get('product_type') != 'unknown' else prev_product,
            'banking_type': parsed.get('banking_type') if parsed.get('banking_type') != 'unknown' else prev_banking,
            'tier': parsed.get('tier') if parsed.get('tier') != 'unknown' else prev_tier,
            'use_case': parsed.get('use_case') if parsed.get('use_case') != 'unknown' else prev_use_case,
            'employment': parsed.get('employment') if parsed.get('employment') != 'unknown' else prev_employment,
            'intent_type': parsed.get('intent_type', 'product_info'),
        }
        
        # Recalculate needs_clarification based on PERSISTED values
        product_known = result['product_type'] not in ('general', 'unknown', '')
        banking_known = result['banking_type'] not in ('unknown', '')
        tier_known = result['tier'] not in ('unknown', '')
        use_case_known = result['use_case'] not in ('unknown', '')
        employment_known = result['employment'] not in ('unknown', '')
        
        # Different clarification requirements based on intent type
        intent_type = result['intent_type']
        
        if intent_type == 'eligibility_check':
            # Eligibility check only needs product type
            # Tier, banking type, and employment will be asked by the eligibility agent
            has_enough = product_known
        elif intent_type == 'comparison':
            # Comparison needs product, banking type, and tier
            has_enough = product_known and banking_known and tier_known
        elif result['product_type'] in ('credit_card', 'loan'):
            has_enough = product_known and banking_known and tier_known and employment_known
        else:
            has_enough = product_known and banking_known and tier_known and use_case_known
        
        result['needs_clarification'] = not has_enough
        
        print(f"After persistence: product={result['product_type']} banking={result['banking_type']} tier={result['tier']} "
              f"use_case={result['use_case']} employment={result['employment']} type={result['intent_type']} enough={has_enough}")
        
        return result

    def _parse_intent(self, raw: str, query: str = "") -> dict:
        """Parse structured intent response."""
        parsed = {}
        for line in str(raw).strip().split('\n'):
            if ':' in line:
                k, _, v = line.partition(':')
                parsed[k.strip().upper()] = v.strip().lower()

        query_type = parsed.get('QUERY_TYPE', 'banking')
        product_type = parsed.get('PRODUCT_TYPE', 'general')
        banking_type = parsed.get('BANKING_TYPE', 'unknown')
        if banking_type == 'islamic':
            banking_type = 'islami'  # Normalize to database spelling
        tier = parsed.get('TIER', 'unknown')
        
        # Validate extracted values — reject LLM hallucinations
        VALID_BANKING_TYPES = ('conventional', 'islami', 'unknown', '')
        if banking_type not in VALID_BANKING_TYPES:
            banking_type = 'unknown'  # Reject garbage like "gold"
        
        VALID_TIERS = ('gold', 'platinum', 'silver', 'unknown', '')
        if tier not in VALID_TIERS:
            tier = 'unknown'
        
        VALID_PRODUCTS = ('credit_card', 'debit_card', 'loan', 'savings_account', 'general', 'unknown', '')
        if product_type not in VALID_PRODUCTS:
            product_type = 'general'
        use_case = parsed.get('USE_CASE', 'unknown')
        employment = parsed.get('EMPLOYMENT', 'unknown')
        intent_type = parsed.get('INTENT_TYPE', 'product_info')

        # Validate intent_type
        if intent_type not in ('product_info', 'comparison', 'eligibility_check', 'feature_query'):
            intent_type = 'product_info'

        # Handle greeting/small_talk from the same parse
        if 'greeting' in query_type:
            return {
                'product_type': 'general', 'banking_type': 'unknown', 'tier': 'unknown',
                'use_case': 'unknown', 'employment': 'unknown',
                'intent_type': 'greeting', 'needs_clarification': False
            }
        if 'small_talk' in query_type or 'small' in query_type:
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

        # For comparisons: need to know optimization criteria
        comparison_criteria_known = use_case_known or employment_known
        if intent_type == 'comparison' and not comparison_criteria_known:
            intent_type = 'comparison_needs_criteria'
            has_enough = False

        print(f"Intent: product={product_type} banking={banking_type} tier={tier} "
              f"use_case={use_case} employment={employment} type={intent_type} enough={has_enough}")

        return {
            'product_type': product_type, 'banking_type': banking_type,
            'tier': tier, 'use_case': use_case, 'employment': employment,
            'intent_type': intent_type, 'needs_clarification': not has_enough
        }

    def _generate_clarifying_questions(self, detected_product: str,
                                        detected_info: dict, history: list) -> str:
        """Generate clarifying questions for missing info."""
        missing = []
        if detected_info.get('banking_type') == 'unknown':
            missing.append("Islamic or Conventional banking preference")
        if detected_info.get('use_case') == 'unknown':
            missing.append("main purpose: travel, shopping, dining, or business")
        if detected_info.get('tier') == 'unknown':
            missing.append("preferred tier: Gold, Platinum, or Silver")
        if (detected_info.get('employment') == 'unknown'
                and detected_product in ('credit_card', 'loan')):
            missing.append("employment type: salaried, self-employed, or business owner")

        if not missing:
            return self._fallback_questions(detected_product, detected_info)

        history_text = "".join(
            f"{m['role'].upper()}: {m['content']}\n" for m in history[-4:]
        )

        raw = self._ollama_call(
            system="Friendly bank assistant. 2 sentences max. No lists.",
            user=f'Ask customer for: {", ".join(missing)}. They want: {detected_product.replace("_", " ")}.',
            temperature=0.7,
            max_tokens=80
        )
        return raw if raw else self._fallback_questions(detected_product, detected_info)

    def _fallback_questions(self, product_type: str, detected_info: dict) -> str:
        """Hardcoded fallback if LLM fails."""
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
        """Format customer info into string."""
        parts = []
        if 'employment' in info and info['employment']:
            parts.append(f"Employment: {info['employment']}")
        if 'income' in info and info['income']:
            parts.append(f"Monthly Income: {info['income']}")
        if 'credit_score' in info and info['credit_score']:
            parts.append(f"Credit Score: {info['credit_score']}")
        if 'banking_preference' in info and info['banking_preference']:
            parts.append(f"Banking Preference: {info['banking_preference']}")
        return "; ".join(parts) if parts else ""


__all__ = ["CrewPipeline", "BankChatbotCrew", "SessionState"]
