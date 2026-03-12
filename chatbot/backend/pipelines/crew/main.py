from core import SessionState
from intent import IntentClassifier
from pipelines.crew.orchestrator import BankChatbotCrew
from pipelines.crew.clarification import DynamicClarificationBuilder
from pipelines.crew.comparator import ProductComparator
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

_clarification_builder = DynamicClarificationBuilder()
_comparator = ProductComparator()


class CrewPipeline:

    def __init__(self):
        self.crew = BankChatbotCrew()
        self.sessions: dict[str, SessionState] = {}
        self.clarification_builder = _clarification_builder

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
                matched_cards = self.clarification_builder.find_matching_cards(
                    banking_type=state.collected_profile.get("banking_type"),
                    use_case=state.collected_profile.get("primary_use_case"),
                    annual_income=state.collected_profile.get("annual_income"),
                    employment_type=state.collected_profile.get("employment_type"),
                    preferred_tier=state.preferred_tier,
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
                    
                    # Set first (best match) product as recommended, store others as alternatives
                    if product_names:
                        state.recommended_product = product_names[0]
                        state.alternative_products = product_names[1:] if len(product_names) > 1 else []
                        state.shown_products_context = matched_cards
                        
                        if state.alternative_products:
                            print(f"📌 Recommended: {state.recommended_product} | Alternatives: {state.alternative_products}")
                        else:
                            print(f"📌 Recommended product set to: {state.recommended_product}")
                    
                    # Clean and format product output
                    cleaned_cards = self._format_product_display(matched_cards)
                    msg = f"Great! Based on your profile, here are the best credit cards for you:\n\n{cleaned_cards}"
                    return self._respond(msg, ["Smart Profiler", "RAG Search"], state.intent)
            else:
                # Still missing info, request next field (with context of what we know)
                clarification_msg = self.clarification_builder.get_dynamic_clarification_message(
                    state.missing_profile_fields,
                    collected_profile=state.collected_profile,
                    intent_type=state.intent.get("intent_type", "product_info")
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
        
        # If just completed eligibility, directly return how-to-apply for that product
        # (don't ask to clarify - they already selected it during eligibility)
        if has_apply_phrase and state.eligibility_done and state.recommended_product:
            print(f"✏️  Just completed eligibility for: {state.recommended_product}")
            print(f"🔎 Detected 'how to apply' query, retrieving from knowledge base")
            how_to_apply = self._get_how_to_apply(state.recommended_product, state.products_text)
            if how_to_apply:
                print(f"✅ Returning 'How to Apply?' section")
                state.eligibility_done = False  # Clear the flag since we're moving forward
                return self._respond(
                    how_to_apply,
                    ["Product Info Retriever", "Formatter"],
                    {"intent_type": "product_info", "category": "product_info"},
                )
        
        # If multiple alternatives exist and user wants to apply - ask which card
        if has_apply_phrase and state.alternative_products and len(state.alternative_products) > 0:
            # Multiple products shown and user wants to apply - ask which one
            clarification = (
                f"Which card would you like to know the application process for?\n\n"
                f"1. **{state.recommended_product}** (our recommendation for your profile)\n"
            )
            for i, alt in enumerate(state.alternative_products, start=2):
                clarification += f"{i}. **{alt}**\n"
            clarification += "\nLet me know which one, or type its name!"
            
            return self._respond(
                clarification,
                ["Intent Classifier"],
                {},
                needs_clarification=True,
            )
        
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

        # Handle product selection if user is responding to "which card for how to apply?" question
        # This handles responses like "1", "2", "Visa Platinum", etc.
        if query_lower.strip() in ("1", "2", "3") and (state.recommended_product or state.alternative_products):
            # User selected option by number
            selection_idx = int(query_lower.strip()) - 1
            all_products = [state.recommended_product] + state.alternative_products
            if 0 <= selection_idx < len(all_products):
                selected_product = all_products[selection_idx]
                print(f"📍 User selected product #{selection_idx+1}: {selected_product}")
                how_to_apply = self._get_how_to_apply(selected_product, state.products_text)
                if how_to_apply:
                    return self._respond(
                        how_to_apply,
                        ["Product Info Retriever", "Formatter"],
                        {"intent_type": "product_info", "category": "product_info"},
                    )

        intent = self._understand_intent(query, history, state.intent)
        print(
            f"📋 Intent detected: type={intent['intent_type']}, banking={intent['banking_type']}, "
            f"features={intent.get('specific_features', [])}, income={intent.get('customer_income')}, "
            f"relevance={intent.get('relevance_score', 0)}"
        )
        
        # Handle off-topic (low relevance) queries
        if intent.get("is_off_topic", False) or intent.get("relevance_score", 100) < 55:
            state.increment_confusion()
            off_topic_response = (
                ollama_chat(
                    system="You are a warm Prime Bank assistant. Gently redirect off-topic queries back to banking.",
                    user=(
                        f'Customer said something off-topic: "{query[:100]}"\n'
                        f'Write 1-2 warm sentences acknowledging it, then redirect to how you can help with banking/credit cards.'
                    ),
                    temperature=0.6,
                    max_tokens=100,
                )
                or "I appreciate that! Is there anything I can help you with at Prime Bank?"
            )
            
            # If confusion is getting high, offer escalation
            if state.confusion_counter > 3 and not state.escalation_offered:
                off_topic_response += (
                    "\n\nI notice we're going in different directions. Would you like to speak with "
                    "one of our support team members who might help you better?"
                )
                state.escalation_offered = True
            
            return self._respond(off_topic_response, [], intent)

        if intent["category"] == "greeting":
            return self._respond(greet(query, history), [], intent)

        if intent["category"] == "small_talk":
            return self._respond(chat(query, history, state), [], intent)

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
        
        # Extract preferred tier/brand if user specified them upfront
        if intent.get("preferred_tier") and intent.get("preferred_tier") != "unknown":
            state.preferred_tier = intent["preferred_tier"]
        if intent.get("card_brand") and intent.get("card_brand") != "unknown":
            state.card_brand = intent["card_brand"]

        # PRIORITY: Handle comparison intent with products already shown
        # When user asks "compare these" or "which is best" - immediately show comparison table 
        if intent_type == "comparison" and state.recommended_product and state.alternative_products:
            products_list = self._extract_products_from_text(state.products_text) if state.products_text else []
            
            if len(products_list) >= 2:
                # Build comparison table immediately - no extra questions
                comparison_table = _comparator.build_comparison_table(
                    products_list[:2],
                    customer_profile=state.collected_profile
                )
                # Extract which product was recommended and store for context in follow-up questions
                recommended = _comparator.extract_recommended_product(comparison_table)
                if recommended:
                    state.recommended_product = recommended
                print(f"🎯 Showing direct comparison of {products_list[0][:20]}... vs {products_list[1][:20]}...")
                return self._respond(comparison_table, ["Comparator"], intent)

        # Check for vague queries that need smart profiling (product_info, product_search_by_income)
        is_vague, missing_profile_fields = self.clarification_builder.needs_clarification(intent_type, intent)
        if is_vague:
            # If user already specified a preferred tier or brand, skip profiling - just search for that
            if (state.preferred_tier and state.preferred_tier != "unknown") or (state.card_brand and state.card_brand != "unknown"):
                # User said "I want platinum" or "I want mastercard" - search for that directly
                search_query = ""
                if state.card_brand and state.card_brand != "unknown":
                    search_query += state.card_brand + " "
                if state.preferred_tier and state.preferred_tier != "unknown":
                    search_query += state.preferred_tier + " "
                search_query += "credit card"
                
                # Use RAG with the specified tier/brand
                matched_cards = rag_search_impl(
                    query=search_query,
                    banking_type=intent.get("banking_type") or "",
                    tier=state.preferred_tier or "",
                    top_k=15,
                    customer_income=None,
                )
                
                if matched_cards and matched_cards != "NO_PRODUCTS_FOUND":
                    state.products_text = matched_cards
                    
                    # Extract product names for context
                    product_names = []
                    for line in matched_cards.split('\n'):
                        if line.startswith('PRODUCT:'):
                            product_name = line.replace('PRODUCT:', '').strip()
                            if product_name:
                                product_names.append(product_name)
                    
                    if product_names:
                        state.recommended_product = product_names[0]
                        if len(product_names) > 1:
                            state.alternative_products = product_names[1:]
                    
                    return self._respond(matched_cards, ["Brand/Tier Aware RAG"], intent)
                else:
                    tier_str = f"{state.preferred_tier} " if state.preferred_tier and state.preferred_tier != "unknown" else ""
                    brand_str = f"{state.card_brand} " if state.card_brand and state.card_brand != "unknown" else ""
                    return self._respond(
                        f"I couldn't find any {brand_str}{tier_str}cards matching your preferences. "
                        f"Could you tell me a bit more about what you're looking for?",
                        ["Brand/Tier Aware RAG"],
                        intent,
                    )
            
            # Store that we need profiling info, will ask next
            state.profiling_needed = True
            state.missing_profile_fields = missing_profile_fields
            clarification_msg = self.clarification_builder.get_dynamic_clarification_message(
                missing_profile_fields,
                collected_profile=state.collected_profile,
                intent_type=intent_type
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
            # If we just recommended a product, use that directly (high confidence that "it" refers to the recommendation)
            if state.recommended_product:
                intent["specific_product"] = state.recommended_product
                intent_type = "eligibility_check"
                intent["intent_type"] = "eligibility_check"
                print(f"🔍 Using recommended product from state: {state.recommended_product}")
            # Check if multiple products were shown - if so, ask for clarification
            elif state.alternative_products and len(state.alternative_products) > 0:
                clarification = (
                    f"I see you're interested in eligibility! Just to clarify, which card would you like to check eligibility for?\n\n"
                    f"1. **{state.recommended_product}** (our recommendation for your profile)\n"
                )
                for i, alt in enumerate(state.alternative_products, start=2):
                    clarification += f"{i}. **{alt}**\n"
                clarification += "\nLet me know which one, or type its name directly!"
                
                return self._respond(
                    clarification,
                    ["Intent Classifier"],
                    intent,
                    needs_clarification=True,
                )
            
            # Single product case: use it directly
            elif state.products_text and "PRODUCT:" in state.products_text:
                # Extract first product name from RAG results
                for line in state.products_text.split('\n'):
                    if line.startswith('PRODUCT:'):
                        specific_product = line.replace('PRODUCT:', '').strip()
                        intent["specific_product"] = specific_product
                        intent_type = "eligibility_check"
                        intent["intent_type"] = "eligibility_check"
                        print(f"🔍 Found recently recommended product in context: {specific_product}")
                        break

        # Handle special cases
        if intent_type == "eligibility_check":
            question = start_eligibility_collection(intent, state)
            state._current_field = "age"  # First field to ask about
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

        # Handle comparison intent with products already shown
        if intent_type == "comparison":
            # If we have shown products, build a comparison table
            if state.recommended_product and state.alternative_products:
                # Extract the 2 products from state
                product1_name = state.recommended_product
                product2_name = state.alternative_products[0] if state.alternative_products else None
                
                if product2_name and state.products_text:
                    # Parse products from the stored text
                    products_list = self._extract_products_from_text(state.products_text)
                    
                    if len(products_list) >= 2:
                        # Build comparison table
                        comparison_table = _comparator.build_comparison_table(
                            products_list[:2],
                            customer_profile=state.collected_profile
                        )
                        return self._respond(comparison_table, ["Comparator"], intent)
        
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
        """
        Process one turn of eligibility field collection.

        State machine:
          state._current_field  = field we ASKED about on the previous turn
          state._confirmed_fields = dict of {field: value} confirmed so far

        Flow per turn:
          1. Find which field we were collecting (state._current_field)
          2. Try to extract that field's value from user's current reply
          3. If extracted → store in _confirmed_fields, advance to next field
          4. If not extracted → re-ask the same field (with gentle retry message)
          5. If all fields done → run assessment immediately
        """
        # Import helpers
        from pipelines.crew.eligibility import (
            _extract_single_field, _build_confirmation, _ask_field_question, get_next_pending_field
        )
        
        # Initialize confirmed fields dict if not present
        if not hasattr(state, '_confirmed_fields'):
            state._confirmed_fields = {}

        # Append the user message to eligibility chat history
        state.eligibility_chat.append({"role": "user", "content": query})

        # ── STEP 1: Which field were we collecting? ───────────────
        current_field = getattr(state, '_current_field', None)

        # If no current field tracked yet, derive from confirmed_fields
        if current_field is None:
            current_field = get_next_pending_field(state)

        # ── STEP 2: Try to extract the current field from user reply ──
        if current_field:
            extracted = _extract_single_field(current_field, query, state._confirmed_fields)

            if extracted is not None:
                # ── STEP 3: Extraction succeeded → confirm and advance ──
                state._confirmed_fields[current_field] = extracted
                state.invalid_attempt_count = 0
                state.confirm_field_value(current_field, extracted, str(extracted))
                
                confirmation = _build_confirmation(current_field, extracted)
                print(f"✓ Confirmed {current_field}={extracted}")

                # Find the next uncollected field
                next_field = get_next_pending_field(state)

                if next_field is None:
                    # ── STEP 5: All fields done → run assessment ──
                    state._current_field = None
                    state.eligibility_chat.append({
                        "role": "assistant",
                        "content": f"{confirmation}\n\n✨ Thank you! Checking your eligibility now..."
                    })
                    return self._run_eligibility_assessment(state)

                # Ask for next field
                state._current_field = next_field
                collected = dict(state._confirmed_fields)
                next_question = _ask_field_question(next_field, collected, state)
                reply = f"{confirmation}\n\n{next_question}"

            else:
                # ── STEP 4: Extraction failed → re-ask same field ──
                state.invalid_attempt_count = (state.invalid_attempt_count or 0) + 1
                print(f"⚠️  Could not extract '{current_field}' from: '{query[:50]}'")
                
                collected = dict(state._confirmed_fields)
                base_question = _ask_field_question(current_field, collected, state)
                
                if state.invalid_attempt_count == 1:
                    reply = f"I didn't quite catch that. {base_question}"
                else:
                    reply = base_question
                
                # current_field stays the same — we're re-asking
                state._current_field = current_field

        else:
            # No pending fields — shouldn't reach here, but handle gracefully
            return self._run_eligibility_assessment(state)

        state.eligibility_chat.append({"role": "assistant", "content": reply})
        return self._respond(reply, ["Eligibility Conversation"], state.intent, needs_clarification=True)

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
        # MUST do this BEFORE reset_eligibility() which clears eligibility_product
        eligibility_product = state.eligibility_product
        if eligibility_product:
            state.recommended_product = eligibility_product
        
        state.eligibility_done = True
        state.reset_eligibility()
        
        # Add follow-up question based on eligibility result
        follow_up = ""
        if "eligible" in response.lower() or "qualify" in response.lower():
            follow_up = (
                "\n\n**Next Steps:**\n"
                "Would you like to:\n"
                "1. Proceed with the application?\n"
                "2. Check eligibility for another card?\n"
                "3. Explore other options?"
            )
        else:
            follow_up = (
                "\n\n**What would you like to do next?**\n"
                "I can help you:\n"
                "1. Explore cards with different eligibility criteria\n"
                "2. Check your eligibility for another card\n"
                "3. Learn about how you can become eligible"
            )
        
        final_response = response + follow_up

        return self._respond(
            final_response,
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
        context_msg = f"""TASK: Extract customer profile information from their response. BE THOROUGH.

Missing fields to extract: {', '.join(state.missing_profile_fields)}
Already have: {state.collected_profile}

CUSTOMER SAID: "{query}"

EXTRACTION INSTRUCTIONS:
====================================

**CRITICAL: Extract EVERY field you can find, even if mixed with other info. Don't skip because of word order.**

1. BANKING_TYPE (highest priority - MUST search aggressively):
   - ANY mention of: "conventional", "traditional", "regular", "standard", "normal", "banking", "cards"
   - ANY mention of: "Islamic", "Shariah", "Hasanah", "faith-based"
   - Examples that MUST be caught:
     * "conventional cards" → "conventional"
     * "wants dining and conventional" → "conventional"
     * "traditional banking" → "conventional"
     * "Islamic cards" → "islamic"
   - Output: "conventional" or "islamic" (lowercase) or null
   
2. PRIMARY_USE_CASE:
   - Search for: "travel", "dining", "business", "shopping", "everyday", "rewards", "lifestyle"
   - Output: "travel" | "dining" | "business" | "rewards" | "lifestyle" or null

3. ANNUAL_INCOME (aggressive extraction with explicit calculation):
   - STEP 1: Search for ANY number: "300k", "5 lakh", "500000", any digit
   - STEP 2: Convert to base number:
     * If has "k": multiply by 1,000 → "300k" = 300,000
     * If has "lakh": multiply by 100,000 → "5 lakh" = 500,000
     * If plain number: use as is → "500000" = 500,000
   - STEP 3: Determine if monthly or annual:
     * IF phrase says "monthly", "per month", "month", or "/month": IT'S MONTHLY
     * IF phrase says "annual", "per year", "yearly": IT'S ANNUAL
   - STEP 4: Calculate annual income:
     * IF monthly: Multiply result from STEP 2 by 12
     * IF annual: Keep result from STEP 2 as is
   - EXAMPLES:
     * "300k monthly" → 300,000 * 12 = 3,600,000 annual
     * "5 lakh per month" → 500,000 * 12 = 6,000,000 annual
     * "50 lakh annual" → 5,000,000 (no *12)
     * "monthly income 300k" → 300,000 * 12 = 3,600,000 annual
   - Output: calculated annual number in BDT or null

4. EMPLOYMENT_TYPE:
   - Search for: "salaried", "employee", "business owner", "self-employed", "freelance"
   - Output: "salaried" | "business_owner" or null

RETURN JSON (must include all 4 fields, use null if not found):
{{"banking_type": "conventional"|"islamic"|null, "primary_use_case": "travel"|"dining"|"business"|"rewards"|"lifestyle"|null, "annual_income": <number>|null, "employment_type": "salaried"|"business_owner"|null}}

**IMPORTANT: This is customer input - be flexible with phrasing, typos, and word order.**
"""
        
        income_classifier = ollama_chat(
            system="You are a meticulous data extraction specialist. The user provides personal info. Extract EVERYTHING including performing income calculations. Output ONLY valid JSON, no explanations.",
            user=context_msg,
            temperature=0.5,  # Higher to encourage calculation
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
            else:
                # Fallback: try pattern matching for common patterns like "300k" or "300k monthly"
                import re
                # Pattern: number + optional "k"/"lakh" + optional "monthly"/"per month"
                pattern = r'(\d+)\s*(?:k|lakh)?\s*(?:monthly|per\s+month|/month)?'
                matches = re.findall(r'(\d+)\s*k(?:[\s,]|$)', query.lower())  # Look for "300k"
                if matches:
                    try:
                        amount = int(matches[0]) * 1000  # Convert "300k" to 300000
                        # If query says "monthly", multiply by 12
                        if any(word in query.lower() for word in ["monthly", "per month", "/month", "month"]):
                            amount *= 12
                        state.collected_profile["annual_income"] = amount
                        state.missing_profile_fields.remove("annual_income")
                    except (ValueError, IndexError):
                        pass
        
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
            # Extract banking_type from products_text to narrow search (case-insensitive)
            banking_type = None  # Default to None for no filtering
            if products_text:
                products_lower = products_text.lower()
                if "islamic" in products_lower or "hasanah" in products_lower:
                    banking_type = "islami"
                elif "conventional" in products_lower:
                    banking_type = "conventional"
            
            print(f"🔍 Searching Chroma for 'How to Apply?' section of {product_name} (banking_type={banking_type})")
            
            # Search specifically for the application/how to apply process
            # Include product name to help embeddings find the exact product
            # Be VERY explicit about what we want
            search_query = f"{product_name} How to Apply Required Documents Application Process"
            
            results = rag_search_impl(
                query=search_query,
                banking_type=banking_type or "",  # Pass None as empty string for rag_search_impl
                top_k=5  # Increased from 3 to get more chunks
            )
            
            if not results or "ERROR" in results or "NO_PRODUCTS_FOUND" in results:
                print(f"❌ No results from RAG search")
                return None
            
            # Look for "How to Apply?" section in the results (case-insensitive search)
            results_lower = results.lower()
            
            # Try different variations of the section header
            section_markers = ["how to apply", "required documents", "application process", "applying for", "apply for", "document"]
            section_idx = -1
            section_marker = ""
            
            for marker in section_markers:
                idx = results_lower.find(marker)
                if idx >= 0:
                    section_idx = idx
                    section_marker = marker
                    break
            
            if section_idx < 0:
                print(f"⚠️  'How to Apply' section not found in primary search. Trying broad fallback...")
                # Fallback 1: search with product name only, no banking type filter
                fallback_query = f"{product_name}"
                fallback_results = rag_search_impl(
                    query=fallback_query,
                    banking_type="",  # No filter
                    top_k=15  # Get many more results
                )
                if fallback_results and "how to apply" in fallback_results.lower():
                    results = fallback_results
                    results_lower = results.lower()
                    section_idx = results_lower.find("how to apply")
                    print(f"✅ Found in broad fallback search")
                else:
                    print(f"⚠️  'How to Apply' section still not found. Trying generic application query...")
                    # Fallback 2: search for just "how to apply" without product name
                    generic_query = "How to Apply Required Documents Application Process"
                    generic_results = rag_search_impl(
                        query=generic_query,
                        banking_type="",  # No filter
                        top_k=10
                    )
                    if generic_results and "how to apply" in generic_results.lower():
                        # Try to find this product in the generic results
                        if product_name.lower() in generic_results.lower():
                            results = generic_results
                            results_lower = results.lower()
                            # Find "how to apply" section that comes after this product
                            prod_idx = results_lower.find(product_name.lower())
                            apply_idx = results_lower.find("how to apply", prod_idx if prod_idx >= 0 else 0)
                            if apply_idx >= 0:
                                section_idx = apply_idx
                                print(f"✅ Found in generic search for this product")
                    
                    if section_idx < 0:
                        print(f"⚠️  'How to Apply' section still not found after all fallbacks. Raw content length: {len(results)}")
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

    def _extract_products_from_text(self, products_text: str) -> list:
        """
        Split products_text into individual product blocks.
        Each product starts with 'PRODUCT:' marker.
        
        Returns:
            List of product text blocks
        """
        products = []
        current_product_lines = []
        
        for line in products_text.split('\n'):
            if line.startswith('PRODUCT:'):
                # If we have a current product, save it
                if current_product_lines:
                    products.append('\n'.join(current_product_lines))
                    current_product_lines = []
                # Start new product
                current_product_lines.append(line)
            else:
                if current_product_lines:  # Only add if we're in a product
                    current_product_lines.append(line)
        
        # Don't forget the last product
        if current_product_lines:
            products.append('\n'.join(current_product_lines))
        
        return products
    
    def _clean_product_output(self, products_text: str) -> str:
        """
        Remove separator lines and format products professionally.
        Replace '=============' with clean headers using bold.
        
        Args:
            products_text: Raw product text from RAG
        
        Returns:
            Cleaned, professionally formatted text
        """
        lines = products_text.split('\n')
        cleaned = []
        
        for line in lines:
            # Skip the separator lines
            if line.strip() and all(c == '=' for c in line.strip()):
                continue
            # Skip multiple consecutive empty lines
            if not line.strip():
                if cleaned and not cleaned[-1].strip():
                    continue
                cleaned.append(line)
            else:
                cleaned.append(line)
        
        return '\n'.join(cleaned)
    
    def _format_product_display(self, products_text: str) -> str:
        """
        Format product output professionally for chat display.
        Shows only essential info: name + highlights (5-6 key features).
        Robustly extracts ✅ features from anywhere in product block.
        """
        products = self._extract_products_from_text(products_text)
        formatted = []

        for product in products[:2]:  # Show max 2 products
            lines = product.split('\n')
            product_name = ""
            key_features = []
            overview = ""

            for line in lines:
                stripped = line.strip()

                if stripped.startswith('PRODUCT:'):
                    product_name = stripped.replace('PRODUCT:', '').strip()

                elif 'Tagline:' in stripped:
                    overview = stripped.replace('Tagline:', '').strip()

                elif stripped.startswith('✅') and len(key_features) < 5:
                    feature = stripped.replace('✅', '').strip()
                    if ' - ' in feature:
                        feature = feature.split(' - ')[0].strip()
                    if feature:
                        key_features.append(feature)

            if not product_name:
                continue

            if len(formatted) > 0:
                formatted.append("\n---\n")
            formatted.append(f"**{product_name}**")
            if overview:
                formatted.append(f"_{overview}_")
            formatted.append("")
            formatted.append("**✨ Key Highlights:**")

            if key_features:
                for feat in key_features:
                    formatted.append(f"• {feat}")
            else:
                formatted.append("• Premium credit card with exclusive benefits")

            formatted.append("")
            formatted.append("_Need detailed information? Ask me!_")

        if not formatted:
            return products_text

        result = "\n".join(formatted)
        result += "\n\n---\n\n**What would you like to do?**\n• Compare these cards\n• Check eligibility\n• Get full details about a specific card"
        return result

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
