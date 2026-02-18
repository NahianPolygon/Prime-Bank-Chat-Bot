"""CrewAI pipeline — fully dynamic agent selection based on session state."""

import requests
import re
from crewai import Crew
from agents.agents import BankAgents, get_ollama_llm
from agents.tasks import BankTasks


class SessionState:
    """Tracks what has been done in a session."""
    def __init__(self):
        self.products_text = None        # Raw product retrieval output
        self.product_names = []          # List of product names retrieved
        self.comparison_done = False
        self.eligibility_done = False
        self.intent = {}                 # Last known intent (banking_type, tier, etc.)

    def has_products(self):
        return bool(self.products_text)

    def reset_products(self):
        """Call when filters change — need fresh retrieval."""
        self.products_text = None
        self.product_names = []
        self.comparison_done = False
        self.eligibility_done = False


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
            intent_type == 'product_info'
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
            retrieval_task = self.tasks_factory.retrieve_products_task(
                retriever, intent_type, query
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
        if needs_eligibility and state.has_products():
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
            max_iter=1,
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

    def run(self, query: str, customer_info: dict = None,
            conversation_history: list = None, session_id: str = None) -> dict:
        """Run pipeline with dynamic agent selection and product caching."""
        
        history = conversation_history or []
        session_id = session_id or "default"
        state = self._get_state(session_id)

        # Step 1: Detect intent
        intent = self._detect_intent(query, history)

        # Step 2: Check if filters changed — if so, reset cached products
        if state.has_products() and self._filters_changed(intent, state.intent):
            print("⚠️  Filters changed — resetting cached products")
            state.reset_products()

        # Step 3: Clarification needed?
        if intent.get('needs_clarification'):
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

        # Step 4: Run dynamic agents
        enriched_query = self._build_enriched_query(query, history, intent, state)
        profile = self._format_customer_profile(customer_info) if customer_info else ""
        intent_type = intent.get('intent_type', 'product_info')

        response, retrieved_products = self.crew.run_agents(
            query=enriched_query,
            intent_type=intent_type,
            state=state,
            customer_profile=profile
        )

        # Step 5: Update session state
        if retrieved_products:
            state.products_text = retrieved_products
        if intent_type == 'comparison':
            state.comparison_done = True
        if intent_type == 'eligibility_check':
            state.eligibility_done = True
        state.intent = intent

        print(f"📦 Session state: products={'✅' if state.has_products() else '❌'} "
              f"comparison={'✅' if state.comparison_done else '❌'} "
              f"eligibility={'✅' if state.eligibility_done else '❌'}")

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
            if old_val != 'unknown' and new_val != 'unknown' and old_val != new_val:
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

    def _detect_intent(self, query: str, history: list) -> dict:
        """Detect intent with 5-line structured output."""
        history_text = ""
        if history:
            history_text = "Previous conversation:\n"
            for msg in history[-6:]:
                history_text += f"{msg['role'].upper()}: {msg['content']}\n"

        raw = self._ollama_call(
            system="You are an intent parser. Output ONLY the 5 labeled lines. No assumptions or defaults. No prose. No thinking.",
            user=f"""{history_text}Current message: "{query}"

Output ONLY these 5 lines with detected values:
PRODUCT_TYPE: credit_card
BANKING_TYPE: unknown
TIER: unknown
USE_CASE: unknown
EMPLOYMENT: unknown

Options:
- PRODUCT_TYPE: credit_card | debit_card | loan | savings_account | general
- BANKING_TYPE: conventional | islami | unknown (ONLY if explicitly mentioned)
- TIER: gold | platinum | silver | unknown (ONLY if explicitly mentioned)
- USE_CASE: shopping | travel | dining | business | lifestyle | rewards | unknown (ONLY if explicitly mentioned)
- EMPLOYMENT: salaried | self_employed | business_owner | student | unknown (ONLY if explicitly mentioned)

CRITICAL RULES:
1. BANKING_TYPE = unknown UNLESS user explicitly says "islamic", "shariah", "conventional", "non-islamic"
2. TIER = unknown UNLESS user explicitly says "gold", "platinum", "silver"
3. USE_CASE = unknown UNLESS user explicitly says their PURPOSE
4. EMPLOYMENT = unknown UNLESS user explicitly states job type
5. Do NOT assume defaults. Do NOT infer from keywords like "professional" or "business"
6. Carry forward values from history ONLY if previously confirmed

Example: "I want a professional platinum credit card"
→ PRODUCT_TYPE: credit_card (explicit)
→ TIER: platinum (explicit)
→ BANKING_TYPE: unknown (NOT stated explicitly)
→ USE_CASE: unknown (NOT stated - "professional" is not a use case)
→ EMPLOYMENT: unknown (NOT stated)
""",
            temperature=0.0,
            max_tokens=80
        )

        if not raw:
            return {
                'product_type': 'general', 'banking_type': 'unknown', 'tier': 'unknown',
                'use_case': 'unknown', 'employment': 'unknown',
                'intent_type': 'product_info', 'needs_clarification': True
            }

        return self._parse_intent(raw, query)

    def _parse_intent(self, raw: str, query: str = "") -> dict:
        """Parse structured intent response."""
        parsed = {}
        for line in str(raw).strip().split('\n'):
            if ':' in line:
                k, _, v = line.partition(':')
                parsed[k.strip().upper()] = v.strip().lower()

        product_type = parsed.get('PRODUCT_TYPE', 'general')
        banking_type = parsed.get('BANKING_TYPE', 'unknown')
        if banking_type == 'islamic':
            banking_type = 'islami'  # Normalize to database spelling
        tier = parsed.get('TIER', 'unknown')
        use_case = parsed.get('USE_CASE', 'unknown')
        employment = parsed.get('EMPLOYMENT', 'unknown')

        # Detect intent type from keywords
        q = query.lower()
        if any(w in q for w in ['compare', 'vs', 'versus', 'difference', 'which is better', 'which one', 'best for me']):
            intent_type = 'comparison'
        elif any(w in q for w in ['eligible', 'qualify', 'can i get', 'do i qualify', 'requirements', 'documents', 'eligibility']):
            intent_type = 'eligibility_check'
        elif any(w in q for w in ['feature', 'benefit', 'fee', 'rate', 'interest', 'limit', 'reward']):
            intent_type = 'feature_query'
        else:
            intent_type = 'product_info'

        # Compute has_enough info — stricter requirements
        product_known = product_type not in ('general', 'unknown', '')
        banking_known = banking_type not in ('unknown', '')
        tier_known = tier not in ('unknown', '')
        use_case_known = use_case not in ('unknown', '')
        employment_known = employment not in ('unknown', '')

        # For credit_card/loan: require banking_type, tier, AND employment confirmation
        # For other products: require banking_type, tier, use_case
        if product_type in ('credit_card', 'loan'):
            has_enough = product_known and banking_known and tier_known and employment_known
        else:
            has_enough = product_known and banking_known and tier_known and use_case_known

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
            system="You are a friendly bank assistant. Be warm and concise. No bullet points. No thinking.",
            user=f"""{history_text}Customer wants: {detected_product.replace('_', ' ')}
Ask naturally about ONLY these missing details: {', '.join(missing)}
Write 2-3 friendly sentences maximum.""",
            temperature=0.7,
            max_tokens=150
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
