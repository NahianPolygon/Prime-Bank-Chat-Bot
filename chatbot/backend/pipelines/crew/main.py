from core import SessionState
from intent import IntentClassifier
from pipelines.crew.orchestrator import BankChatbotCrew
from pipelines.crew.clarification import ClarificationBuilder
from pipelines.crew.eligibility import (
    start_eligibility_collection,
    check_eligibility_completeness,
    ask_for_next_field,
    build_eligibility_profile,
)
from pipelines.crew.helpers import greet, chat, build_context_block
from pipelines.crew.eligibility_matching import run_eligibility_matching
from pipelines.rag.search import rag_search_impl
from utils.ollama import ollama_chat, parse_json


class CrewPipeline:

    def __init__(self):
        self.crew = BankChatbotCrew()
        self.sessions: dict[str, SessionState] = {}

    def _get_state(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState()
        return self.sessions[session_id]

    def run(
        self,
        query: str,
        conversation_history: list | None = None,
        session_id: str | None = None,
        customer_info: dict | None = None,
    ) -> dict:

        history = conversation_history or []
        session_id = session_id or "default"
        state = self._get_state(session_id)

        if state.eligibility_active:
            return self._eligibility_turn(query, state, history)

        # When profiling mode active, collect profile info from user response
        if state.profiling_needed:
            self._collect_profile_info(query, state, history)
            
            # Check if all profile fields are now collected
            if not state.missing_profile_fields:
                # All profile info collected - use it for smart search
                matched_cards = ClarificationBuilder.find_matching_cards(
                    banking_type=state.collected_profile.get("banking_type"),
                    use_case=state.collected_profile.get("primary_use_case"),
                    annual_income=state.collected_profile.get("annual_income"),
                    employment_type=state.collected_profile.get("employment_type"),
                )
                
                if matched_cards:
                    state.products_text = matched_cards
                    state.profiling_needed = False
                    
                    # Extract product names from matched_cards for context preservation
                    # Look for "PRODUCT: " sections which is how RAG returns data
                    product_names = []
                    for line in matched_cards.split('\n'):
                        if line.startswith('PRODUCT:'):
                            product_name = line.replace('PRODUCT:', '').strip()
                            if product_name:
                                product_names.append(product_name)
                    
                    # Set first (best match) product as recommended
                    if product_names:
                        state.recommended_product = product_names[0]
                        print(f"📌 Recommended product set to: {state.recommended_product}")
                    
                    msg = f"Great! Based on your profile, here are the best credit cards for you:\n\n{matched_cards}"
                    return self._respond(msg, ["Smart Profiler", "RAG Search"], state.intent)
            else:
                # Still missing info, request next field (with context of what we know)
                clarification_msg = ClarificationBuilder.get_clarification_questions(
                    state.missing_profile_fields,
                    collected_profile=state.collected_profile
                )
                return self._respond(
                    clarification_msg,
                    ["Smart Profiler"],
                    state.intent,
                    needs_clarification=True,
                )

        # Check for "how to apply?" query with product context preserved
        query_lower = query.lower()
        has_apply_phrase = any(phrase in query_lower for phrase in ["how to apply", "apply for", "application process", "apply process"])
        
        if state.recommended_product:
            print(f"✏️  Recommended product available: {state.recommended_product}")
            if has_apply_phrase:
                print(f"🔎 Detected 'how to apply' query, retrieving from knowledge base")
                how_to_apply = self._get_how_to_apply(state.recommended_product, state.products_text)
                if how_to_apply:
                    print(f"✅ Returning 'How to Apply?' section")
                    return self._respond(
                        how_to_apply,
                    ["Product Info Retriever", "Formatter"],
                    {"intent_type": "product_info", "category": "product_info"},
                )

        intent = self._understand_intent(query, history, state.intent)
        print(
            f"📋 Intent detected: type={intent['intent_type']}, banking={intent['banking_type']}, "
            f"features={intent.get('specific_features', [])}, income={intent.get('customer_income')}"
        )

        if intent["category"] == "greeting":
            return self._respond(greet(query, history), [], intent)

        if intent["category"] == "small_talk":
            return self._respond(chat(query, history), [], intent)

        if state.has_products() and intent.get("preferences_changed"):
            state.reset_products()

        if intent.get("needs_clarification"):
            state.intent = intent
            return self._respond(
                intent["clarification_question"],
                ["Intent Classifier"],
                intent,
                needs_clarification=True,
            )

        intent_type = intent["intent_type"]
        state.intent = intent

        # Check for vague queries that need smart profiling (product_info, product_search_by_income)
        is_vague, missing_profile_fields = ClarificationBuilder.needs_clarification(intent_type, intent)
        if is_vague:
            # Store that we need profiling info, will ask next
            state.profiling_needed = True
            state.missing_profile_fields = missing_profile_fields
            clarification_msg = ClarificationBuilder.get_clarification_questions(
                missing_profile_fields,
                collected_profile=state.collected_profile
            )
            return self._respond(
                clarification_msg,
                ["Smart Profiler"],
                intent,
                needs_clarification=True,
            )

        # If user asks about eligibility for a specific product, route to eligibility_check
        if intent.get("specific_product") and ("eligible" in query.lower() or "qualify" in query.lower()):
            intent_type = "eligibility_check"
            intent["intent_type"] = "eligibility_check"
        
        # Handle "am i eligible for it?" when referred to recently recommended product
        elif ("eligible" in query.lower() or "qualify" in query.lower()) and not intent.get("specific_product"):
            # Check if a product was recently recommended (look for PRODUCT: in state.products_text)
            if state.products_text and "PRODUCT:" in state.products_text:
                # Extract first product name from RAG results
                for line in state.products_text.split('\n'):
                    if line.startswith('PRODUCT:'):
                        recommended = line.replace('PRODUCT:', '').strip()
                        intent["specific_product"] = recommended
                        intent_type = "eligibility_check"
                        intent["intent_type"] = "eligibility_check"
                        print(f"🔍 Found recently recommended product in context: {recommended}")
                        break
            # Also check state.recommended_product if it's set
            elif state.recommended_product:
                intent["specific_product"] = state.recommended_product
                intent_type = "eligibility_check"
                intent["intent_type"] = "eligibility_check"
                print(f"🔍 Using recommended product from state: {state.recommended_product}")

        # Handle special cases
        if intent_type == "eligibility_check":
            question = start_eligibility_collection(intent, state)
            return self._respond(
                question,
                ["Eligibility Conversation"],
                intent,
                needs_clarification=True,
            )

        # Handle eligibility_matching (feature + income)
        if intent_type == "eligibility_matching":
            income = intent.get("customer_income")
            features = intent.get("specific_features", [])
            
            if not (income and features):
                clarification = "To find matching products, I need:\n"
                if not income:
                    clarification += "- Your monthly salary or annual income (in BDT)\n"
                if not features:
                    clarification += "- Specific feature you need (lounge, dining, rewards, airport, EMI, insurance, etc.)\n"
                return self._respond(
                    clarification,
                    ["Intent Classifier"],
                    intent,
                    needs_clarification=True,
                )
            
            # Use first feature for matching (classifier detected this was primary)
            feature = features[0] if isinstance(features, list) else features
            
            # Ensure income is annual
            if income < 50000:
                income = income * 12
            
            age = intent.get("customer_age") or 25
            tenure = intent.get("customer_tenure_months") or 6
            banking_type = intent.get("banking_type", "")
            
            result = run_eligibility_matching(
                customer_age=int(age),
                customer_annual_income=int(income),
                customer_tenure_months=int(tenure),
                requested_feature=str(feature),
                banking_type=banking_type,
            )
            
            return self._respond(
                result["result"],
                ["Eligibility Matcher", "RAG Search", "Eligibility Extractor"],
                intent,
            )

        # For all other intent types (feature_inquiry, product_search_by_income, product_info, comparison)
        # Use RAG-based search with different search strategies
        enriched = build_context_block(query, history, intent, state)
        response, retrieved = self.crew.run_agents(
            enriched_query=enriched,
            intent_type=intent_type,
            intent=intent,
            state=state,
        )

        if retrieved:
            state.products_text = retrieved
        if intent_type == "comparison":
            state.comparison_done = True

        chain = self._chain_label(intent_type)
        return self._respond(response, chain, intent)

    def _understand_intent(
        self, query: str, history: list, previous_intent: dict
    ) -> dict:
        return IntentClassifier.classify(query, history, previous_intent)

    def _eligibility_turn(
        self, query: str, state: SessionState, history: list
    ) -> dict:
        state.eligibility_chat.append({"role": "user", "content": query})
        status = check_eligibility_completeness(state)

        if status["complete"]:
            return self._run_eligibility_assessment(state)

        reply = ask_for_next_field(status["next_field"], status["collected"], state)
        state.eligibility_chat.append({"role": "assistant", "content": reply})
        return self._respond(
            reply,
            ["Eligibility Conversation"],
            state.intent,
            needs_clarification=True,
        )

    def _run_eligibility_assessment(self, state: SessionState) -> dict:
        profile = build_eligibility_profile(state)

        enriched = (
            f"Customer Query: Check eligibility for {state.eligibility_product}\n"
            f"Customer Profile:\n{profile}"
        )

        response, retrieved = self.crew.run_agents(
            enriched_query=enriched,
            intent_type="eligibility_check",
            intent=state.intent,
            state=state,
            customer_profile=profile,
        )

        if retrieved:
            state.products_text = retrieved
        
        # Preserve the product being checked for eligibility as recommended_product
        # so "how to apply?" queries can use it
        if state.eligibility_product and not state.recommended_product:
            state.recommended_product = state.eligibility_product
        
        state.eligibility_done = True
        state.reset_eligibility()

        return self._respond(
            response,
            ["Eligibility Conversation", "Retriever", "Eligibility Analyzer", "Formatter"],
            state.intent,
        )

    def _collect_profile_info(self, query: str, state: SessionState, history: list) -> None:
        """
        Extract profile information from user's response using LLM classification.
        Uses the intent classifier to extract values, not regex.
        Updates state.collected_profile with detected info and removes fields from missing_profile_fields.
        """
        # Use LLM for ALL extractions (consistent with classifier approach)
        # Build context about what we're asking for
        context_msg = f"""Customer is answering profiling questions. Extract ANY information they provide:
        
Missing profile fields: {', '.join(state.missing_profile_fields)}
Already collected: {state.collected_profile}

Customer's response: "{query}"

IMPORTANT: Look for ANY mention of numbers with k, lakh, thousand, or plain digits that could be income.
Extract the following IF present in the response:
1. banking_type: "conventional" or "islamic" (if they mention either)
2. primary_use_case: "travel", "dining", "business", "rewards", or "lifestyle" (if they describe their use case)
3. annual_income: annual income in BDT (AGGRESSIVELY search for numbers - see rules below)
4. employment_type: "salaried" or "business_owner" (if they mention employment type)

Return JSON with these fields (null if not mentioned):
{{
  "banking_type": "conventional" | "islamic" | null,
  "primary_use_case": "travel" | "dining" | "business" | "rewards" | "lifestyle" | null,
  "annual_income": <number in BDT> | null,
  "employment_type": "salaried" | "business_owner" | null
}}

AGGRESSIVE INCOME EXTRACTION RULES (must follow all):
1. Look for any number + unit: "50k", "5 lakh", "500000", "50 thousand"
2. IF number has "k" or "thousand": multiply by 1000
3. IF number has "lakh": multiply by 100,000
4. IF result < 100,000 OR phrase mentions "monthly/month/"month: multiply annual result by 12
5. IF phrase says "annual" or "per year": do NOT multiply by 12 (already annual)
6. EXAMPLES:
   - "200k" alone → 200*1000 = 200,000 < 100k threshold → 200,000*12 = 2,400,000 annual ✓
   - "200k/month" → 200*1000*12 = 2,400,000 annual ✓
   - "50 lakh annual" → 50*100,000 = 5,000,000 (no *12 because "annual") ✓
   - "300000 monthly" → 300,000*12 = 3,600,000 annual ✓
7. If no number found, return null (NEVER invent)

Output ONLY valid JSON. No explanations."""
        
        income_classifier = ollama_chat(
            system="You are a data extraction system. Output only JSON. Be strict.",
            user=context_msg,
            temperature=0.0,
            max_tokens=200,
        )
        
        extracted = parse_json(income_classifier) or {}
        
        print(f"📊 Profile extraction from '{query[:50]}...': {extracted}")
        
        # Banking type
        if "banking_type" in state.missing_profile_fields:
            if extracted.get("banking_type"):
                state.collected_profile["banking_type"] = extracted["banking_type"]
                state.missing_profile_fields.remove("banking_type")
        
        # Primary use case
        if "primary_use_case" in state.missing_profile_fields:
            if extracted.get("primary_use_case"):
                state.collected_profile["primary_use_case"] = extracted["primary_use_case"]
                state.missing_profile_fields.remove("primary_use_case")
        
        # Annual income (via LLM extraction)
        if "annual_income" in state.missing_profile_fields:
            income = extracted.get("annual_income")
            if income and isinstance(income, (int, float)) and income > 0:
                state.collected_profile["annual_income"] = int(income)
                state.missing_profile_fields.remove("annual_income")
        
        # Employment type
        if "employment_type" in state.missing_profile_fields:
            if extracted.get("employment_type"):
                state.collected_profile["employment_type"] = extracted["employment_type"]
                state.missing_profile_fields.remove("employment_type")

    def _chain_label(self, intent_type: str) -> list:
        """Map intent type to processing chain labels"""
        if intent_type == "eligibility_matching":
            return ["Eligibility Matcher", "RAG Search", "Eligibility Extractor"]
        elif intent_type == "comparison":
            return ["RAG Search", "Comparator"]
        elif intent_type == "feature_inquiry":
            return ["RAG Search", "Feature Analyst"]
        elif intent_type == "product_search_by_income":
            return ["RAG Search", "Income Filter"]
        elif intent_type == "eligibility_check":
            return ["Eligibility Analyzer", "Information Provider"]
        else:  # product_info and others
            return ["RAG Search", "Product Analyst"]

    def _get_how_to_apply(self, product_name: str, products_text: str | None) -> str | None:
        """
        Retrieve the "How to Apply?" section for a recommended product from knowledge base.
        
        Args:
            product_name: Name of the product (e.g., "Visa Platinum Credit Card")
            products_text: Previously retrieved products text to extract banking_type
            
        Returns:
            Formatted "How to Apply?" section or None if not found
        """
        try:
            # Extract banking_type from products_text to narrow search
            banking_type = ""
            if products_text:
                if "Islamic" in products_text or "Hasanah" in products_text:
                    banking_type = "islami"
                elif "Conventional" in products_text:
                    banking_type = "conventional"
            
            print(f"🔍 Searching Chroma for 'How to Apply?' section of {product_name}")
            
            # Search specifically for the application/how to apply process
            # Include product name to help embeddings find the exact product
            search_query = f"{product_name} how to apply application process documents required"
            
            results = rag_search_impl(
                query=search_query,
                banking_type=banking_type,
                top_k=3
            )
            
            if not results or "ERROR" in results or "NO_PRODUCTS_FOUND" in results:
                print(f"❌ No results from RAG search")
                return None
            
            # Look for "How to Apply?" section in the results (case-insensitive search)
            results_lower = results.lower()
            
            # Try different variations of the section header
            section_markers = ["how to apply", "application process", "applying for"]
            section_idx = -1
            section_marker = ""
            
            for marker in section_markers:
                idx = results_lower.find(marker)
                if idx >= 0:
                    section_idx = idx
                    section_marker = marker
                    break
            
            if section_idx < 0:
                print(f"⚠️  'How to Apply' section not found in results. Raw content length: {len(results)}")
                # Try to return at least the beginning of product info
                return None
            
            # Extract the section
            section = results[section_idx:]
            
            # Find the end of this section (next major heading or end of product data)
            end_markers = ["\n## ", "\n---", "PRODUCT:"]
            end_idx = len(section)
            
            for marker in end_markers:
                idx = section.find(marker)
                if idx > 0:
                    end_idx = min(end_idx, idx)
            
            section = section[:end_idx].strip()
            
            # Limit to reasonable length
            max_length = 2500
            if len(section) > max_length:
                section = section[:max_length] + "\n\n[... See complete details at Prime Bank branch ...]"
            
            if section.strip():
                formatted = f"**How to Apply for {product_name}**\n\n{section}"
                print(f"✅ Found and formatted 'How to Apply?' section")
                return formatted
            else:
                print(f"⚠️  Section was empty after extraction")
                return None
            
        except Exception as e:
            print(f"❌ Error retrieving 'How to Apply?' for {product_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _respond(
        self,
        response: str,
        agent_chain: list,
        intent: dict,
        needs_clarification: bool = False,
    ) -> dict:
        return {
            "response": response,
            "agent_chain": agent_chain,
            "needs_clarification": needs_clarification,
            "detected_intent": intent,
        }
